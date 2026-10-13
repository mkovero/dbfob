#!/usr/bin/env python3
"""Host test of firmware/src/dsp.c - the exact file the firmware builds.

  python3 firmware/test/test_dsp.py

1. CIC: the closed-form byte step equals a bit-by-bit order-4 integrator/comb reference, for
   random data fed in uneven chunks.
2. log: dsp_db10_q8 against 10*log10.
3. Frequency response: sines from a simulated PDM mic (2nd-order sigma-delta at 1.5 MHz)
   through the whole chain, against IEC 61672 A-weighting.
4. Linearity over 60 dB at 1 kHz, and headroom at -3 dBFS at 50 Hz and 3 kHz (no wrap-around).
Exits nonzero on any failure.
"""
import ctypes, math, os, subprocess, sys, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'src')
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
from design_filters import a_weight_db

fails = []


def check(name, ok, msg):
    print(f"{'ok  ' if ok else 'FAIL'} {name}: {msg}")
    if not ok: fails.append(name)


def build(extra=()):
    so = os.path.join(tempfile.mkdtemp(), 'libdsp.so')
    subprocess.run(['gcc', '-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                    '-fno-sanitize-recover', '-shared', '-fPIC', '-DDSP_TEST_HOOK', *extra, '-I', SRC,
                    os.path.join(SRC, 'dsp.c'), os.path.join(HERE, 'host.c'), '-lm', '-o', so], check=True)
    lib = ctypes.CDLL(so)
    lib.run_sine.restype = ctypes.c_int32
    lib.run_sine.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_uint32,
                             ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32)]
    lib.run_bytes.restype = ctypes.c_uint32
    lib.run_bytes.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]
    lib.db10_q8.restype = ctypes.c_int32
    lib.db10_q8.argtypes = [ctypes.c_uint64]
    return lib


def cic_reference(data):
    bits = np.unpackbits(np.frombuffer(data, np.uint8)).astype(np.uint64)
    i = [0, 0, 0, 0]; d = [0, 0, 0, 0]; out = []
    M = (1 << 32) - 1
    for k, x in enumerate(bits):
        i[0] = (i[0] + int(x)) & M
        i[1] = (i[1] + i[0]) & M
        i[2] = (i[2] + i[1]) & M
        i[3] = (i[3] + i[2]) & M
        if k % 64 == 63:
            c = i[3]
            for s in range(4):
                c, d[s] = (c - d[s]) & M, c
            out.append(c)
    return out


def main():
    lib = build()

    rng = np.random.default_rng(1)
    data = rng.integers(0, 256, 8 * 400, dtype=np.uint8).tobytes()   # 400 output samples
    out = (ctypes.c_uint32 * 400)()
    n = lib.run_bytes(data, len(data), out, 400)
    ref = cic_reference(data)
    check('CIC closed form', n == len(ref) and list(out[:n]) == ref, f'{n} samples compared')

    errs = [abs(lib.db10_q8(x) / 256 - 10 * math.log10(x)) for x in [1, 2, 3, 10, 1000, 12345, 2**27, 2**40, 10**15]]
    check('log', max(errs) < 0.05, f'worst {max(errs):.3f} dB')

    peak, pcm = ctypes.c_int32(), ctypes.c_int32()
    skip = 4000                                   # ~170 ms: filter settling, as the firmware does

    def level(f, amp, sec=0.6):
        q = lib.run_sine(f, amp, sec, skip, ctypes.byref(peak), ctypes.byref(pcm))
        return q / 256

    # Digital silence (an idle 0101 stream) must read far below any room. The board's first
    # quiet-room readings sat at exactly -81.3 dBFS: the mean square was rounded to whole LSB^2.
    # (The simulated 2nd-order modulator's own noise is about -75 dBFS, so it can't test below that.)
    floor = level(1000, 0.0)
    check('silence floor', floor < -110, f'{floor:.1f} dBFS')

    amp = 0.25                                    # -12 dBFS
    print('\n  f/Hz   expect    got    err')
    worst_mid = worst_edge = 0
    for f in [31.5, 50, 63, 100, 200, 500, 1000, 2000, 3150, 4000, 6300, 8000, 10000]:
        exp = 20 * math.log10(amp) + float(a_weight_db(f))
        got = level(f, amp)
        e = got - exp
        print(f'{f:7.1f} {exp:7.2f} {got:7.2f} {e:+6.2f}')
        if 50 <= f <= 8000: worst_mid = max(worst_mid, abs(e))
        else: worst_edge = max(worst_edge, abs(e))
    check('A-weighting 50 Hz - 8 kHz', worst_mid < 0.5, f'worst {worst_mid:.2f} dB')
    check('A-weighting 31.5 Hz and 10 kHz', worst_edge < 1.0, f'worst {worst_edge:.2f} dB')

    lin = []
    for db in [-60, -40, -20, -6]:
        a = 10 ** (db / 20)
        lin.append(level(1000, a) - db)
    check('linearity -60..-6 dBFS at 1 kHz', max(map(abs, lin)) < 0.3,
          ' '.join(f'{x:+.2f}' for x in lin))

    for f in (50, 3000):
        a = 10 ** (-3 / 20)
        e = level(f, a) - (-3 + float(a_weight_db(f)))
        check(f'headroom -3 dBFS {f} Hz', abs(e) < 0.5,
              f'err {e:+.2f} dB, peak |y| {peak.value} (int32 products need < 2^17 = 131072)')
        check(f'headroom margin {f} Hz', peak.value < 131072, f'{peak.value}')

    diag_tests()

    print('\nFAILED: ' + ', '.join(fails) if fails else '\nall passed')
    return 1 if fails else 0


def diag_tests():
    """The diagnostic build (make DIAG=1): band levels and the 3 MHz clock path."""
    lib = build(['-DDSP_DIAG'])
    lib.run_sine_diag.restype = ctypes.c_int32
    lib.run_sine_diag.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                  ctypes.c_uint32, ctypes.POINTER(ctypes.c_int32)]
    diag = (ctypes.c_int32 * 3)()
    print('\n  diag: clock    f/Hz      A   A<8k   A<2k      Z   (dBFS)')
    res = {}
    for fs in (1.5e6, 3e6):
        for f in (0, 1000, 5000, 10000):
            a = lib.run_sine_diag(f, 0.25 if f else 0.0, 0.6, fs, 4000, diag) / 256
            d = [v / 256 for v in diag]
            res[fs, f] = (a, *d)
            print(f'        {fs / 1e6:.1f} MHz {f:6d} {a:6.1f} {d[0]:6.1f} {d[1]:6.1f} {d[2]:6.1f}')
    for fs in (1.5e6, 3e6):
        a1k = res[fs, 1000]
        check(f'diag {fs / 1e6:.1f} MHz: 1 kHz in every band', max(abs(a1k[0] - v) for v in a1k[1:3]) < 0.5
              and abs(a1k[0] - (-12)) < 0.5, f'A {a1k[0]:.1f} A<8k {a1k[1]:.1f} A<2k {a1k[2]:.1f}')
        a10 = res[fs, 10000]
        check(f'diag {fs / 1e6:.1f} MHz: 10 kHz cut below 8 kHz', a10[0] - a10[1] > 6,
              f'A {a10[0]:.1f} A<8k {a10[1]:.1f}')


if __name__ == '__main__':
    sys.exit(main())
