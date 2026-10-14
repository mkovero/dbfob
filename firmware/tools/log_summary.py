#!/usr/bin/env python3
"""How small can a dose log get for readout? Simple compression vs per-block summaries.

    python3 tools/log_summary.py ../docs/dose-example.bin

Backs the numbers in docs/log-readout.md. Prints the size of each scheme and the dose it would give.
"""
import collections, lzma, math, struct, sys, zlib


def load(path):
    d = open(path, 'rb').read()
    _, _, tick_ms, tps, _ = struct.unpack_from('<HHIHH', d)
    codes = []
    for b in d[12:]:
        if b >= 0xFD:
            codes.append(b)                      # end marker: part of what would be sent
            break
        codes.append(b)
    return codes, tick_ms * tps / 1000


def dose(levels, dt):                            # NIOSH: 85 dBA for 8 h, 3 dB exchange
    return sum(dt / (8 * 3600 / 2 ** ((l - 85) / 3)) for l in levels) * 100


def laeq(xs):
    return 10 * math.log10(sum(10 ** (x / 10) for x in xs) / len(xs))


def zigzag(v):
    return 2 * v if v >= 0 else -2 * v - 1


def compression(codes):
    deltas = [b - a for a, b in zip(codes, codes[1:])]
    runs, i = 0, 0
    while i < len(codes):
        j = i
        while j < len(codes) and codes[j] == codes[i] and j - i < 255:
            j += 1
        runs += 1; i = j
    nibble = 8 + sum(4 if -7 <= d <= 7 else 12 for d in deltas)
    rice = min((8 + sum((zigzag(d) >> k) + 1 + k for d in deltas), k) for k in range(4))
    data = bytes(codes)
    return deltas, [
        ('run-length (value, count)', runs * 16),
        ('differences, 4-bit codes', nibble),
        (f'differences, Rice code k={rice[1]}', rice[0]),
        ('zlib -9 (reference)', len(zlib.compress(data, 9)) * 8),
        ('lzma (reference)', len(lzma.compress(data, format=lzma.FORMAT_RAW,
                                               filters=[{'id': lzma.FILTER_LZMA2, 'preset': 9}])) * 8),
    ]


def main():
    codes, period = load(sys.argv[1])
    lv = [c / 2 + 20 for c in codes if 0 < c < 0xFD]
    raw = len(codes) + 12
    print(f'{len(lv)} samples {period:.1f} s apart, {raw} B raw with the header, dose {dose(lv, period):.2f} %')

    deltas, rows = compression(codes)
    c = collections.Counter(deltas)
    print(f'\ncompression: {100 * c[0] / len(deltas):.0f} % of differences are 0, '
          f'{100 * sum(v for k, v in c.items() if abs(k) <= 1) / len(deltas):.0f} % within one 0.5 dB step')
    for name, bits in rows:
        n = (bits + 7) // 8 + 12
        print(f'  {name:32s} {n:4d} B  {100 * n / raw:3.0f} %')

    print('\nper-block summary (LAeq and Lmax, one byte each in 1 dB steps):')
    for minutes in (5, 10, 15, 30):
        n = max(1, round(minutes * 60 / period))
        blocks = [lv[i:i + n] for i in range(0, len(lv), n)]
        q = [round(laeq(b)) for b in blocks]
        d = sum(dose([l], period * len(b)) for l, b in zip(q, blocks))
        dev = sorted(abs(x - l) for l, b in zip(q, blocks) for x in b)
        print(f'  {minutes:2d} min: {len(blocks):3d} blocks, {len(blocks):3d} B LAeq / {2 * len(blocks):3d} B with Lmax, '
              f'dose {d:.2f} %, sample vs block median {dev[len(dev) // 2]:.1f} dB, 90th {dev[int(.9 * len(dev))]:.1f} dB')

    print('\nturning points (a point when the level leaves +-T dB of the last one; 1 B gap + 1 B level):')
    for t in (1.5, 3, 5):
        pts = [(0, lv[0])]
        for i, x in enumerate(lv):
            if abs(x - pts[-1][1]) > t:
                pts.append((i, x))
        rec, j = [], 0
        for i in range(len(lv)):
            while j + 1 < len(pts) and pts[j + 1][0] <= i:
                j += 1
            rec.append(pts[j][1])
        print(f'  T={t}: {len(pts)} points, {2 * len(pts)} B, dose {dose(rec, period):.2f} %')


if __name__ == '__main__':
    main()
