#!/usr/bin/env python3
"""Decode the dosimeter log the fob keeps in its last 1 KB of flash (see dose_log_* in dbfob.c).

    sudo ch32fun/minichlink/minichlink -r dose.bin 0x08003C00 1024   # cell out, programmer on
    python3 tools/dose_log.py dose.bin [--plugs] [--all]

Prints the run length, LAeq, the noise dose (NIOSH, 85 dBA / 8 h, 3 dB exchange) and a per-sample
table (one sample per AWU period x ticks per sample, about a minute), or every sample with --all.
"""
import math, struct, sys

MAGIC, HDR = 0xDB01, 12
STOPPED, AUTO_OFF, EMPTY = 0xFD, 0xFE, 0xFF
PLUG_DB = 12


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 1:
        sys.exit(__doc__)
    data = open(args[0], 'rb').read()
    magic, cal, tick_ms, tps, sample_ms = struct.unpack_from('<HHIHH', data)
    if magic != MAGIC:
        sys.exit(f'no dose log (magic {magic:#06x}): no run since this firmware was flashed?')
    period = tick_ms * tps / 1000
    levels, end = [], 'still running (or the cell was pulled)'
    for b in data[HDR:]:
        if b == EMPTY: break
        if b == STOPPED: end = 'stopped by long press'; break
        if b == AUTO_OFF: end = 'auto-off at 12 h'; break
        levels.append(None if b == 0 else b / 2 + 20)
    valid = [l for l in levels if l is not None]
    print(f'cal {cal / 256:.1f} dB, tick {tick_ms} ms, a {sample_ms} ms sample every {period:.1f} s')
    print(f'{len(levels)} samples ({len(valid)} valid), {len(levels) * period / 3600:.2f} h, {end}')
    if not valid:
        return
    laeq = 10 * math.log10(sum(10 ** (l / 10) for l in valid) / len(valid))
    hours = len(levels) * period / 3600
    for name, off in (('bare ear', 0), ('with plugs', PLUG_DB)):
        dose = 100 * 10 ** ((laeq - off - 85) / 10) * hours / 8
        print(f'LAeq {laeq - off:.1f} dBA  dose {dose:.1f} %  ({name})')
    print(f'min {min(valid):.1f}  max {max(valid):.1f} dBA')
    step = 1 if '--all' in sys.argv else max(1, round(600 / period))   # else ~10 min rows
    print('\n  time    LAeq over the row (dBA)')
    for i in range(0, len(levels), step):
        row = [l for l in levels[i:i + step] if l is not None]
        t = i * period
        lv = f'{10 * math.log10(sum(10 ** (l / 10) for l in row) / len(row)):5.1f}' if row else '  -'
        print(f'{int(t // 3600):3d}:{int(t % 3600 // 60):02d}  {lv}')


if __name__ == '__main__':
    main()
