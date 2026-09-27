#!/usr/bin/env python3
"""Verify production/cpl_jlc.csv the way JLC will use it.

JLC places every part with the EasyEDA footprint of its LCSC number, at the CPL position and
rotation. This script does the same: it takes each EasyEDA footprint (cached in jlc_footprints/,
fetched from easyeda.com on first use), puts it where the CPL says, and checks that

  - every EasyEDA pad centre lands inside the KiCad pad of the same pin (LEDs by K/A name,
    since their pad numbers disagree between vendors),
  - a footprint's through hole (MK1's sound port) lands on the board's hole,
  - BT1's opening (the side of its outline with the arc notches) faces the board edge.

Exit status 1 on any failure. Run by fab.py after it writes the CPL.
"""
import csv, json, math, os, re, sys, urllib.request
import pcbnew

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jlc_footprints')
PCB = os.path.join(HERE, 'dbfob.kicad_pcb')
PROD = os.path.join(HERE, 'production')
MIL10 = 0.254                  # EasyEDA units: 10 mil
TOL_HOLE = 0.15                # mm

# EasyEDA pad number -> KiCad pad number where the two numberings differ
PAD_MAP = {
    'BatteryHolder_Keystone_3034_1x20mm': {'1': '1', '3': '1', '2': '2'},
    'SW_Push_1P1T_XKB_TS-1187A': {'1': '1', '2': '1', '3': '2', '4': '2'},
}
BY_NAME = {'LED_0603_1608Metric': {'K': '1', 'A': '2'}}   # KiCad LED: 1 = K, 2 = A


def easyeda(lcsc):
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, lcsc + '.json')
    if not os.path.exists(f):
        url = f'https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5'
        req = urllib.request.Request(url, headers={'User-Agent': 'curl/8'})   # default UA gets 403
        data = urllib.request.urlopen(req, timeout=30).read()
        open(f, 'wb').write(data)
    r = json.load(open(f))['result']
    pk = r['packageDetail']['dataStr']
    hx, hy = float(pk['head']['x']), float(pk['head']['y'])
    names = {}
    for sh in r['dataStr'].get('shape', []):
        if sh.startswith('P~'):
            parts = sh.split('^^')
            num = parts[0].split('~')[3]
            for q in parts[1:]:
                qq = q.split('~')
                if len(qq) > 4 and qq[0] in ('0', '1') and qq[4] and not qq[4].replace('.', '').isdigit():
                    names[num] = qq[4]; break
    pads, holes, arcs_y = [], [], []
    for sh in pk['shape']:
        t = sh.split('~')
        if t[0] == 'PAD':
            pads.append((t[8], (float(t[2]) - hx) * MIL10, (float(t[3]) - hy) * MIL10))
            if float(t[9] or 0) > 0: holes.append(((float(t[2]) - hx) * MIL10, (float(t[3]) - hy) * MIL10))
        elif t[0] == 'HOLE':
            holes.append(((float(t[1]) - hx) * MIL10, (float(t[2]) - hy) * MIL10))
        elif t[0] == 'ARC' and t[2] == '3':          # silkscreen arcs
            m = re.match(r'M\s*([-\d.]+)[ ,]([-\d.]+)', t[4])
            if m: arcs_y.append((float(m.group(2)) - hy) * MIL10)
    return r['packageDetail']['title'], names, pads, holes, arcs_y


def main():
    board = pcbnew.LoadBoard(PCB)
    org = board.GetDesignSettings().GetAuxOrigin()
    ox, oy = pcbnew.ToMM(org.x), pcbnew.ToMM(org.y)
    to_board = lambda x, y: pcbnew.VECTOR2I(pcbnew.FromMM(ox + x), pcbnew.FromMM(oy - y))
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    lcsc = {}
    for r in csv.DictReader(open(os.path.join(PROD, 'bom_jlc.csv'))):
        for d in r['Designator'].split(','): lcsc[d.strip()] = r['LCSC Part #']
    bad = 0
    for r in csv.DictReader(open(os.path.join(PROD, 'cpl_jlc.csv'))):
        ref = r['Designator']; fp = fps[ref]
        fpname = str(fp.GetFPID().GetLibItemName())
        cx, cy = float(r['Mid X'][:-2]), float(r['Mid Y'][:-2])
        a = math.radians(float(r['Rotation']))
        # EasyEDA frame (y down) turned by the CPL angle (CCW), into CPL coordinates (y up)
        place = lambda ex, ey: (cx + ex * math.cos(a) + ey * math.sin(a), cy + ex * math.sin(a) - ey * math.cos(a))
        title, names, pads, holes, arcs_y = easyeda(lcsc[ref])
        kpads = {}
        for p in fp.Pads(): kpads.setdefault(p.GetNumber(), []).append(p)
        errs = []
        for num, ex, ey in pads:
            want = BY_NAME.get(fpname, {}).get(names.get(num, ''), None) or PAD_MAP.get(fpname, {}).get(num, num)
            pt = to_board(*place(ex, ey))
            if not any(p.HitTest(pt) for p in kpads.get(want, [])):
                hit = [p.GetNumber() for ps in kpads.values() for p in ps if p.HitTest(pt)]
                errs.append(f'EasyEDA pad {num}{"/" + names[num] if num in names else ""} -> '
                            f'{"KiCad pad " + ",".join(hit) if hit else "no pad"} (want {want})')
        for ex, ey in holes:
            x, y = place(ex, ey)
            near = [p for ps in kpads.values() for p in ps if p.GetDrillSize().x > 0 and
                    math.dist((pcbnew.ToMM(p.GetPosition().x) - ox, oy - pcbnew.ToMM(p.GetPosition().y)), (x, y)) < TOL_HOLE]
            if not near: errs.append(f'hole at ({x:.2f}, {y:.2f}) is not on a board hole')
        if fpname.startswith('BatteryHolder_Keystone_3034') and arcs_y:
            side = -1 if sum(arcs_y) / len(arcs_y) < 0 else 1          # EasyEDA y of the notched side
            _, ny = place(0, side * 10)
            if ny > cy: errs.append('holder opening faces into the board, not the bottom edge')
        print(f"{'ok ' if not errs else 'BAD'} {ref:4s} {lcsc[ref]:9s} rot {float(r['Rotation']):5.0f}  {title}")
        for e in errs: print('      ', e)
        bad += bool(errs)
    if bad:
        sys.exit(f'{bad} part(s) would be placed wrong')


if __name__ == '__main__':
    main()
