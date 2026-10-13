#!/usr/bin/env python3
"""Spectrum of the fob's input from the DIAG=1 raw dump: where the quiet-room floor lives.

    sudo make monitor | tee floor.log          # DIAG=1 PRINTF=swio build, double click
    python3 tools/floor_spectrum.py floor.log

For each mic clock: the A-weighted and unweighted level per octave band (dB SPL with the firmware's
calibration), the total A level rebuilt from the spectrum (compare with the dBA line), and the
strongest narrow peaks (tones: electrical interference shows up as these).
"""
import collections, math, re, sys
import numpy as np

sys.path.insert(0, __import__('os').path.dirname(__file__))
from design_filters import FS, a_weight_db, cic_db

CAL_DB = 130.0                                   # CAL_DB_Q8: 0 dBFS = 130 dB SPL
MS_FS = 2.0 ** 31                                # a full-scale sine's mean square (amplitude 2^16)
OCTAVES = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000]


def frames(path):
    rx = re.compile(r'raw clk=(\S+) f=(\d+) i=(\d+) ([0-9a-f]+)')
    acc = collections.defaultdict(dict)
    for line in open(path, errors='replace'):
        m = rx.search(line)
        if m:
            clk, f, i, hx = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            v = [int(hx[k:k + 4], 16) for k in range(0, len(hx) - 3, 4)]
            acc[clk, f][i] = [x - 65536 if x >= 32768 else x for x in v]
    out = collections.defaultdict(list)
    for (clk, f), parts in sorted(acc.items()):
        x = [v for i in sorted(parts) for v in parts[i]]
        if len(x) >= 256:
            out[clk].append(np.array(x, float))
    return out


def psd(fr):
    """Mean-square density per bin, averaged over frames: sum over bins = mean square."""
    n = min(len(x) for x in fr)
    w = np.hanning(n)
    p = np.zeros(n // 2 + 1)
    for x in fr:
        x = x[:n] - x[:n].mean()
        X = np.fft.rfft(x * w)
        p += np.abs(X) ** 2 / (np.sum(w ** 2) * n)
    p /= len(fr)
    p[1:-1] *= 2                                 # one-sided
    return np.fft.rfftfreq(n, 1 / FS), p


def db(ms):
    return 10 * math.log10(max(ms, 1e-30) / MS_FS) + CAL_DB


def main():
    fr = frames(sys.argv[1])
    if not fr:
        sys.exit('no raw lines: DIAG=1 build, double click, and log the monitor output')
    for clk, xs in sorted(fr.items()):
        f, p = psd(xs)
        f1 = np.maximum(f, 1.0)
        # undo the CIC droop (the raw samples are straight after the CIC), then weight
        p_flat = p / 10 ** (cic_db(f1) / 10)
        pa = p_flat * 10 ** (a_weight_db(f1) / 10)
        pa[0] = p_flat[0] = 0
        print(f'\n{clk} MHz clock: {len(xs)} frames of {len(xs[0])} samples, {f[1]:.1f} Hz bins')
        print(f'  rebuilt from the spectrum: {db(pa.sum()):.1f} dBA, {db(p_flat[f > 20].sum()):.1f} dBZ (> 20 Hz)')
        print('  octave    dBA    dBZ   share of the A energy')
        for c in OCTAVES:
            m = (f >= c / math.sqrt(2)) & (f < c * math.sqrt(2))
            share = 100 * pa[m].sum() / pa.sum()
            print(f'  {c:6g} {db(pa[m].sum()):6.1f} {db(p_flat[m].sum()):6.1f}   {share:5.1f} % {"#" * int(share / 2)}')
        top = f >= 8000 * math.sqrt(2)
        print(f'  >11.3k {db(pa[top].sum()):6.1f} {db(p_flat[top].sum()):6.1f}   {100 * pa[top].sum() / pa.sum():5.1f} %')
        # narrow peaks: bins well above the median of their neighbourhood
        med = np.array([np.median(p_flat[max(0, k - 8):k + 9]) for k in range(len(p_flat))])
        peaks = [k for k in range(2, len(p_flat) - 1)
                 if p_flat[k] > 10 * med[k] and p_flat[k] >= p_flat[k - 1] and p_flat[k] >= p_flat[k + 1]]
        peaks.sort(key=lambda k: -pa[k])
        if peaks:
            print('  tones (> 10 dB above their neighbourhood), strongest A first:')
            for k in peaks[:8]:
                print(f'    {f[k]:7.0f} Hz  {db(pa[k - 1:k + 2].sum()):5.1f} dBA  {db(p_flat[k - 1:k + 2].sum()):5.1f} dBZ')


if __name__ == '__main__':
    main()
