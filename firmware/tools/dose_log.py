#!/usr/bin/env python3
"""Decode the dosimeter log the fob keeps in its last 1 KB of flash (see dose_log_* in dbfob.c).

    sudo ch32fun/minichlink/minichlink -r dose.bin 0x08003C00 1024   # cell out, programmer on
    python3 tools/dose_log.py dose.bin [--all] [--svg night.svg [--note 6.4=drums ...]]

Prints the run length, LAeq, the noise dose (NIOSH, 85 dBA / 8 h, 3 dB exchange) and a table in
10-minute rows, or every sample (one per AWU period x ticks per sample, about a minute) with --all.
--svg draws the levels and the running dose; each --note H=TEXT labels the hour H.
"""
import argparse, math, struct, sys

MAGIC, HDR = 0xDB01, 12
OVERLOAD, LOW_BATT, STOPPED, AUTO_OFF, EMPTY = 0xFB, 0xFC, 0xFD, 0xFE, 0xFF
PLUG_DB = 12
BANDS = ((40, 84, '#e3f4e1'), (84, 91, '#fdf6d3'), (91, 97, '#fde6d0'), (97, 200, '#fad9d9'))  # dBA


def leq(levels):
    return 10 * math.log10(sum(10 ** (l / 10) for l in levels) / len(levels))


def svg(path, levels, period, notes, ovl=()):
    W, H, L, R, T, B = 820, 340, 52, 62, 36, 40          # size and margins
    hours = len(levels) * period / 3600
    xmax = max(1, math.ceil(hours - 0.05))                 # 12.01 h -> 12
    xstep = 0.5 if xmax <= 3 else 1 if xmax <= 12 else 2
    if xstep < 1:
        xmax = max(1, math.ceil(hours / xstep - 0.05) * xstep)  # 2.25 h -> 2.5
    ymin = 40
    ymax = max(100, math.ceil(max((l for l in levels if l is not None), default=0) / 10) * 10)
    x = lambda h: L + (W - L - R) * h / xmax
    y = lambda db: T + (H - T - B) * (ymax - min(max(db, ymin), ymax)) / (ymax - ymin)
    dose, plug, run, run_p = [], [], 0.0, 0.0             # running dose, bare ear and with plugs
    for l in levels:
        run += 0 if l is None else 100 * 10 ** ((l - 85) / 10) * period / (8 * 3600)
        run_p += 0 if l is None else 100 * 10 ** ((l - PLUG_DB - 85) / 10) * period / (8 * 3600)
        dose.append(run); plug.append(run_p)
    dstep = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000) if 4 * s >= run)
    dmax = 4 * dstep                                       # four round ticks
    yd = lambda d: T + (H - T - B) * (1 - d / dmax)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" '
         f'font-size="12">', f'<rect width="{W}" height="{H}" fill="#fff"/>']
    for lo, hi, c in BANDS:
        if lo < ymax:
            o.append(f'<rect x="{L}" y="{y(min(hi, ymax)):.1f}" width="{W - L - R}" '
                     f'height="{y(lo) - y(min(hi, ymax)):.1f}" fill="{c}"/>')
    for db in range(ymin, ymax + 1, 10):
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{y(db):.1f}" y2="{y(db):.1f}" stroke="#ccc" '
                 f'stroke-width="0.5"/><text x="{L - 6}" y="{y(db) + 4:.1f}" text-anchor="end">{db}</text>')
    for i in range(int(xmax / xstep) + 1):
        o.append(f'<text x="{x(i * xstep):.1f}" y="{H - B + 16}" text-anchor="middle">{i * xstep:g}</text>')
    for i in range(5):
        d = dstep * i
        o.append(f'<text x="{W - R + 6}" y="{yd(d) + 4:.1f}" fill="#1f5fbf">{d:g} %</text>')
    if dmax >= 100:                                        # the daily allowance
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{yd(100):.1f}" y2="{yd(100):.1f}" stroke="#1f5fbf" '
                 f'stroke-width="0.8" stroke-dasharray="5,4"/>')
    pts, segs = [], []
    for i, l in enumerate(levels):                        # break the line at invalid samples
        if l is None:
            segs.append(pts); pts = []
        else:
            pts.append(f'{x((i + 0.5) * period / 3600):.1f},{y(l):.1f}')
    segs.append(pts)
    for s in segs:
        if s:
            o.append(f'<polyline points="{" ".join(s)}" fill="none" stroke="#333" stroke-width="1"/>')
    for ds, style, name in ((dose, '', 'bare ear'), (plug, ' stroke-dasharray="6,3"', f'plugs -{PLUG_DB} dB')):
        o.append('<polyline points="' + ' '.join(f'{x((i + 1) * period / 3600):.1f},{yd(d):.1f}'
                 for i, d in enumerate(ds)) + f'" fill="none" stroke="#1f5fbf" stroke-width="2"{style}/>')
        o.append(f'<text x="{x(len(ds) * period / 3600) + 4:.1f}" y="{min(yd(ds[-1]) - 4, H - B - 4):.1f}" '
                 f'text-anchor="end" fill="#1f5fbf">{name} {ds[-1]:.0f} %</text>')
    for i in ovl:                                          # overloaded: the level is a lower bound
        o.append(f'<circle cx="{x((i + 0.5) * period / 3600):.1f}" cy="{y(levels[i]):.1f}" r="3.5" '
                 f'fill="#d22"/>')
    for h, text in notes:
        o.append(f'<line x1="{x(h):.1f}" x2="{x(h):.1f}" y1="{T}" y2="{H - B}" stroke="#888" '
                 f'stroke-dasharray="3,3"/><text x="{x(h) + 4:.1f}" y="{T + 12}">{text}</text>')
    o.append(f'<text x="{L}" y="{T - 14}" font-weight="bold">dBA, a 1 s sample a minute (red dot = overload)  ·  '
             f'running dose, % of a day: bare ear (solid), with plugs (dashed)</text>')
    o.append(f'<text x="{(L + W - R) / 2}" y="{H - 8}" text-anchor="middle">hours since start</text>')
    o.append('</svg>')
    open(path, 'w').write('\n'.join(o) + '\n')


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument('dump')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--svg')
    ap.add_argument('--note', action='append', default=[])
    a = ap.parse_args()
    data = open(a.dump, 'rb').read()
    magic, cal, tick_ms, tps, sample_ms = struct.unpack_from('<HHIHH', data)
    if magic != MAGIC:
        sys.exit(f'no dose log (magic {magic:#06x}): no run since this firmware was flashed?')
    period = tick_ms * tps / 1000
    levels, ovl, end = [], set(), 'still running (or the cell was pulled)'
    for b in data[HDR:]:
        if b == OVERLOAD: ovl.add(len(levels)); continue  # flags the sample that follows
        if b == EMPTY: break
        if b == LOW_BATT: end = 'stopped: low battery'; break
        if b == STOPPED: end = 'stopped by long press'; break
        if b == AUTO_OFF: end = 'auto-off at 12 h'; break
        levels.append(None if b == 0 else b / 2 + 20)
    valid = [l for l in levels if l is not None]
    print(f'cal {cal / 256:.1f} dB, tick {tick_ms} ms, a {sample_ms} ms sample every {period:.1f} s')
    print(f'{len(levels)} samples ({len(valid)} valid), {len(levels) * period / 3600:.2f} h, {end}')
    if not valid:
        return
    laeq = leq(valid)
    hours = len(levels) * period / 3600
    for name, off in (('bare ear', 0), ('with plugs', PLUG_DB)):
        dose = 100 * 10 ** ((laeq - off - 85) / 10) * hours / 8
        print(f'LAeq {laeq - off:.1f} dBA  dose {dose:.1f} %  ({name})')
    print(f'min {min(valid):.1f}  max {max(valid):.1f} dBA')
    ovl = {i for i in ovl if i < len(levels)}
    print(f'{len(ovl)} overloaded samples' + (' (their levels, and so the dose, are lower bounds)' if ovl else ''))
    if a.svg:
        notes = [(float(h), t) for h, t in (n.split('=', 1) for n in a.note)]
        svg(a.svg, levels, period, notes, sorted(ovl))
        print(f'wrote {a.svg}')
    step = 1 if a.all else max(1, round(600 / period))   # else ~10 min rows
    print('\n  time    LAeq over the row (dBA)')
    for i in range(0, len(levels), step):
        row = [l for l in levels[i:i + step] if l is not None]
        t = i * period
        lv = f'{leq(row):5.1f}' if row else '  -'
        n = sum(1 for j in range(i, i + step) if j in ovl)
        print(f'{int(t // 3600):3d}:{int(t % 3600 // 60):02d}  {lv}' + (f'  overload x{n}' if n else ''))


if __name__ == '__main__':
    main()
