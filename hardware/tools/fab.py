#!/usr/bin/env python3
"""JLCPCB fabrication + assembly outputs, adapted from studer-vca/tools/fab.py:

  hardware/production/gerbers/*          Gerbers + Excellon drill, origin = board bottom-left
  hardware/production/dbfob-gerbers.zip  upload this as the PCB
  hardware/production/bom_jlc.csv        Comment, Designator, Footprint, LCSC Part #
  hardware/production/cpl_jlc.csv        pick-and-place, machine-placed parts only
  hardware/production/bom_manual.csv     parts with no LCSC number (not machine-placed)
  hardware/production/render-top.png / render-bottom.png

A part without an LCSC number is not machine-placed (J1 is pads for pogo pins or a hand-fitted
header, H1 is the keyring hole), so the CPL's exclusion set is read back from the BOM rather than
written here (etofab.md §6).

JLC places parts with the EasyEDA footprint of each LCSC number, whose rotation and origin can
differ from KiCad's. JLC_FRAME holds the correction per footprint and check_cpl.py verifies the
written CPL against the EasyEDA footprints (pin identity and position, BT1's opening direction);
fab.py fails if that check does.
"""
import csv, json, math, os, shutil, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(HERE, 'dbfob.kicad_pcb')
SCH = os.path.join(HERE, 'dbfob.kicad_sch')
OUT = os.path.join(HERE, 'production')

# JLC places each part with the EasyEDA footprint of its LCSC number, so the CPL has to be written
# in that footprint's frame, not KiCad's. Measured by comparing pad positions of both footprints
# (tools/check_cpl.py re-verifies every run against the EasyEDA data):
#   TSSOP-20  EasyEDA = KiCad rotated +90 (pin 1 bottom-left)      -> +270
#   MK1       EasyEDA = KiCad rotated -90                          -> +90, and EasyEDA's origin
#             sits 0.13 mm towards the pads from the package centre (datasheet fig. 11 agrees
#             with KiCad's footprint), so the CPL point moves with it
#   BT1 3034  EasyEDA = KiCad rotated 180 (pads are symmetric; the outline's opening is not -
#             uncorrected, the holder's opening would face U1 and no cell could go in)
#   0603 LEDs cathode on the left in both, whatever the pad numbers say -> 0
# footprint -> (degrees, (dx, dy) of the CPL point in KiCad footprint coordinates, mm)
JLC_FRAME = {
    'TSSOP-20_4.4x6.5mm_P0.65mm': (270, (0, 0)),
    'Infineon_PG-LLGA-5-1': (90, (-0.13, 0)),
    'BatteryHolder_Keystone_3034_1x20mm': (180, (0, 0)),
}


def run(*a): subprocess.run(['kicad-cli', *a], check=True, capture_output=True)


def preflight():
    """ERC, DRC and schematic parity must be clean before anything is written. Returns problems."""
    out = []
    with tempfile.TemporaryDirectory() as td:
        erc = os.path.join(td, 'erc.json')
        subprocess.run(['kicad-cli', 'sch', 'erc', '--severity-all', '--format', 'json', '-o', erc, SCH],
                       capture_output=True)
        for sheet in json.load(open(erc))['sheets']:
            for v in sheet['violations']:
                items = ' '.join(i['description'] for i in v.get('items', []))
                if v['type'] in ('lib_symbol_issues', 'footprint_link_issues'):
                    continue            # no global library tables for kicad-cli on this machine
                # the one justified item: MIC_VDD is powered by a GPIO, flagged with PWR_FLAG #FLG03
                if v['type'] == 'pin_to_pin' and '#FLG03' in items and 'U1' in items and 'PC6' in items:
                    continue
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
        run('sch', 'export', 'bom', '-o', raw, '--fields', 'Reference,Value,Footprint,LCSC,MPN,Note',
            '--group-by', 'LCSC,Value,Footprint', '--ref-range-delimiter', '', '--exclude-dnp', SCH)
        rows = list(csv.DictReader(open(raw)))
    hand, machine = set(), set()
    with open(os.path.join(out_dir, 'bom_jlc.csv'), 'w', newline='') as f, \
         open(os.path.join(out_dir, 'bom_manual.csv'), 'w', newline='') as g:
        a = csv.writer(f); a.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        b = csv.writer(g); b.writerow(['Designator', 'Value', 'MPN', 'Footprint', 'Note'])
        for r in rows:
            fp = r['Footprint'].split(':')[-1]
            if r['LCSC']:
                a.writerow([f"{r['Value']} {r['MPN']}".strip(), r['Reference'], fp, r['LCSC']])
                machine |= {d for d in r['Reference'].split(',') if d}
            else:
                b.writerow([r['Reference'], r['Value'], r['MPN'], fp, r['Note']])
                hand |= {d for d in r['Reference'].split(',') if d}
    return rows, hand, machine


def main():
    problems = preflight()
    for p in problems: print('  ', p)
    if problems: sys.exit(f'{len(problems)} preflight problem(s): nothing written')
    # Everything is built in a staging directory and only replaces production/ once every check
    # has passed, so a failing run can never leave an uploadable-looking release behind.
    stage = OUT + '.staging'
    shutil.rmtree(stage, ignore_errors=True)
    g = os.path.join(stage, 'gerbers'); os.makedirs(g)
    run('pcb', 'export', 'gerbers', '--layers', 'F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts',
        '--subtract-soldermask', '--no-protel-ext', '--use-drill-file-origin', '-o', g, PCB)
    run('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '--generate-map',
        '--drill-origin', 'plot', '--map-format', 'gerberx2', '-o', g + '/', PCB)
    z = os.path.join(stage, 'dbfob-gerbers.zip')
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
            # only what has a part to feed: H1 is not in the BOM at all, J1 has no LCSC number
            if r['Ref'] not in machine: hand.add(r['Ref']); continue
            off, (dx, dy) = JLC_FRAME.get(r['Package'], (0, (0, 0)))
            a = math.radians(float(r['Rot']))
            # footprint frame (y down) -> CPL frame (y up), turned by the part's rotation
            x = float(r['PosX']) + dx * math.cos(a) + dy * math.sin(a)
            y = float(r['PosY']) + dx * math.sin(a) - dy * math.cos(a)
            rot = (float(r['Rot']) + off) % 360
            w.writerow([r['Ref'], f"{x:.3f}mm", f"{y:.3f}mm",
                        'Top' if r['Side'] == 'top' else 'Bottom', f'{rot:.0f}'])
            n += 1
    chk = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'check_cpl.py'), stage],
                         capture_output=True, text=True)
    print(chk.stdout.rstrip())
    if chk.returncode:
        sys.exit('CPL check failed, production/ left untouched: ' + chk.stderr[-500:])
    back = [r['Ref'] for r in placed if r['Side'] != 'top']
    for side in ('top', 'bottom'):
        run('pcb', 'render', '--side', side, '--width', '1000', '--height', '1400', '--quality', 'high',
            '-o', os.path.join(stage, f'render-{side}.png'), PCB)
    shutil.rmtree(OUT, ignore_errors=True)
    os.rename(stage, OUT)
    print('gerbers:', len(os.listdir(os.path.join(OUT, 'gerbers'))), 'files ->', os.path.join(OUT, 'dbfob-gerbers.zip'))
    print('cpl:', n, 'placements; not machine-placed:', ', '.join(sorted(hand)) or '-')
    print('back-side parts:', ', '.join(back) or 'none (single-sided assembly)')


if __name__ == '__main__':
    main()
