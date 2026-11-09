#!/usr/bin/env python3
"""JLCPCB outputs for the NFC test board, as rev A's tools/fab.py:

  hardware/nfc-test/production/gerbers/*              Gerbers + Excellon, origin = board bottom-left
  hardware/nfc-test/production/nfc-test-gerbers.zip   upload this as the PCB
  hardware/nfc-test/production/bom_jlc.csv            machine-placed parts
  hardware/nfc-test/production/cpl_jlc.csv            their placements, checked by ../tools/check_cpl.py
  hardware/nfc-test/production/bom_manual.csv         hand-fitted: BT1 contacts (back), C1/C2 trim (DNP); J1 is bare pads
  hardware/nfc-test/production/render-top.png / render-bottom.png

Everything is staged and only replaces production/ once ERC, DRC, parity and the CPL check pass.
"""
import csv, json, math, os, shutil, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'nfc-test'
PCB = os.path.join(HERE, NAME + '.kicad_pcb')
SCH = os.path.join(HERE, NAME + '.kicad_sch')
OUT = os.path.join(HERE, 'production')
CHECK = os.path.join(HERE, '..', 'tools', 'check_cpl.py')

# KiCad footprint -> (CPL rotation offset, (dx, dy) CPL point in footprint mm), against the EasyEDA
# footprint of the part's LCSC number (check_cpl.py re-verifies every pad):
#   NXP_XQFN-8 (C710403): EasyEDA pin 1 top-left, pin 8 top-centre, centred: same frame as ours
#   0603 R/C/LED: as rev A, no correction
JLC_FRAME = {}


def run(*a): subprocess.run(['kicad-cli', *a], check=True, capture_output=True)


def preflight():
    out = []
    with tempfile.TemporaryDirectory() as td:
        erc = os.path.join(td, 'erc.json')
        subprocess.run(['kicad-cli', 'sch', 'erc', '--severity-all', '--format', 'json', '-o', erc, SCH],
                       capture_output=True)
        for sheet in json.load(open(erc))['sheets']:
            for v in sheet['violations']:
                if v['type'] in ('lib_symbol_issues', 'footprint_link_issues'):
                    continue            # no global library tables for kicad-cli on this machine
                items = ' '.join(i['description'] for i in v.get('items', []))
                out.append(f"ERC {v['severity']} {v['type']}: {v['description'][:60]} {items[:80]}")
        drc = os.path.join(td, 'drc.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--schematic-parity', '--severity-all', '--format', 'json',
                        '-o', drc, PCB], capture_output=True)
        d = json.load(open(drc))
    out += [f"DRC {v['severity']} {v['type']}: {v['description'][:70]}" for v in d['violations']
            if v['type'] != 'lib_footprint_issues']
    out += [f"unconnected: {v['description'][:70]}" for v in d.get('unconnected_items', [])]
    out += [f"parity {v['type']}: {v['description'][:70]}" for v in d.get('schematic_parity', [])]
    return out


def bom(out_dir):
    with tempfile.TemporaryDirectory() as td:
        raw = os.path.join(td, 'bom.csv')
        run('sch', 'export', 'bom', '-o', raw, '--fields', 'Reference,Value,Footprint,LCSC,MPN,Note,${DNP}',
            '--labels', 'Reference,Value,Footprint,LCSC,MPN,Note,DNP',
            '--group-by', 'LCSC,Value,Footprint', '--ref-range-delimiter', '', SCH)
        rows = list(csv.DictReader(open(raw)))
    hand, machine = set(), set()
    with open(os.path.join(out_dir, 'bom_jlc.csv'), 'w', newline='') as f, \
         open(os.path.join(out_dir, 'bom_manual.csv'), 'w', newline='') as g:
        a = csv.writer(f); a.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        b = csv.writer(g); b.writerow(['Designator', 'Value', 'MPN', 'Footprint', 'Note'])
        for r in rows:
            fp = r['Footprint'].split(':')[-1]
            refs = {d for d in r['Reference'].split(',') if d}
            if r['LCSC'] and not r.get('DNP'):
                a.writerow([f"{r['Value']} {r['MPN']}".strip(), r['Reference'], fp, r['LCSC']])
                machine |= refs
            else:
                b.writerow([r['Reference'], r['Value'], r['MPN'], fp, r['Note']])
                hand |= refs
    return rows, hand, machine


def main():
    problems = preflight()
    for p in problems: print('  ', p)
    if problems: sys.exit(f'{len(problems)} preflight problem(s): nothing written')
    stage = OUT + '.staging'
    shutil.rmtree(stage, ignore_errors=True)
    g = os.path.join(stage, 'gerbers'); os.makedirs(g)
    run('pcb', 'export', 'gerbers', '--layers', 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts',
        '--subtract-soldermask', '--no-protel-ext', '--use-drill-file-origin', '-o', g, PCB)
    run('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '--generate-map',
        '--drill-origin', 'plot', '--map-format', 'gerberx2', '-o', g + '/', PCB)
    z = os.path.join(stage, NAME + '-gerbers.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(g)): zf.write(os.path.join(g, f), f)
    rows, hand, machine = bom(stage)
    with tempfile.TemporaryDirectory() as td:
        pos = os.path.join(td, 'pos.csv')
        run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both',
            '--use-drill-file-origin', '-o', pos, PCB)
        placed = list(csv.DictReader(open(pos)))
    n = 0
    with open(os.path.join(stage, 'cpl_jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in placed:
            if r['Ref'] not in machine: hand.add(r['Ref']); continue
            off, (dx, dy) = JLC_FRAME.get(r['Package'], (0, (0, 0)))
            a = math.radians(float(r['Rot']))
            x = float(r['PosX']) + dx * math.cos(a) + dy * math.sin(a)
            y = float(r['PosY']) + dx * math.sin(a) - dy * math.cos(a)
            rot = (float(r['Rot']) + off) % 360
            w.writerow([r['Ref'], f"{x:.3f}mm", f"{y:.3f}mm",
                        'Top' if r['Side'] == 'top' else 'Bottom', f'{rot:.0f}'])
            n += 1
    chk = subprocess.run([sys.executable, CHECK, stage, PCB], capture_output=True, text=True)
    print(chk.stdout.rstrip())
    if chk.returncode:
        sys.exit('CPL check failed, production/ left untouched: ' + chk.stderr[-500:])
    back = sorted(r['Ref'] for r in placed if r['Side'] != 'top' and r['Ref'] in machine)
    for side in ('top', 'bottom'):
        run('pcb', 'render', '--side', side, '--width', '1800', '--height', '400', '--zoom', '4.2', '--quality', 'high',
            '-o', os.path.join(stage, f'render-{side}.png'), PCB)
    shutil.rmtree(OUT, ignore_errors=True)
    os.rename(stage, OUT)
    print('gerbers:', len(os.listdir(os.path.join(OUT, 'gerbers'))), 'files ->', os.path.join(OUT, NAME + '-gerbers.zip'))
    print('cpl:', n, 'placements; not machine-placed:', ', '.join(sorted(hand)) or '-')
    print('machine-placed on the back:', ', '.join(back) or 'none (single-sided assembly)')


if __name__ == '__main__':
    main()
