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

JLC's rotation convention differs from KiCad's for some packages. ROT_OFFSET holds the correction
per footprint; every part of a package carries the same one, so a wrong entry shows up as one
constant offset in JLC's placement preview, not a part-by-part fix. CHECK THE PREVIEW before
paying: U1 (pin 1), MK1 (pin 1 and port), D1-D4 (cathode mark), BT1 (opening to the board edge).
"""
import csv, os, shutil, subprocess, tempfile, zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(HERE, 'dbfob.kicad_pcb')
SCH = os.path.join(HERE, 'dbfob.kicad_sch')
OUT = os.path.join(HERE, 'production')

# footprint name -> degrees added to KiCad's rotation for JLC. TSSOP: JLC's library models are
# pin 1 bottom-left, KiCad's top-left (the usual 270 of the community rotation tables). Everything
# else is taken at KiCad's angle until the preview says otherwise.
ROT_OFFSET = {'TSSOP-20_4.4x6.5mm_P0.65mm': 270}


def run(*a): subprocess.run(['kicad-cli', *a], check=True, capture_output=True)


def bom():
    with tempfile.TemporaryDirectory() as td:
        raw = os.path.join(td, 'bom.csv')
        run('sch', 'export', 'bom', '-o', raw, '--fields', 'Reference,Value,Footprint,LCSC,MPN,Note',
            '--group-by', 'LCSC,Value,Footprint', '--ref-range-delimiter', '', '--exclude-dnp', SCH)
        rows = list(csv.DictReader(open(raw)))
    hand, machine = set(), set()
    with open(os.path.join(OUT, 'bom_jlc.csv'), 'w', newline='') as f, \
         open(os.path.join(OUT, 'bom_manual.csv'), 'w', newline='') as g:
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
    g = os.path.join(OUT, 'gerbers')
    shutil.rmtree(g, ignore_errors=True); os.makedirs(g)
    run('pcb', 'export', 'gerbers', '--layers', 'F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts',
        '--subtract-soldermask', '--no-protel-ext', '--use-drill-file-origin', '-o', g, PCB)
    run('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '--generate-map',
        '--drill-origin', 'plot', '--map-format', 'gerberx2', '-o', g + '/', PCB)
    z = os.path.join(OUT, 'dbfob-gerbers.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(g)): zf.write(os.path.join(g, f), f)
    rows, hand, machine = bom()
    with tempfile.TemporaryDirectory() as td:
        pos = os.path.join(td, 'pos.csv')
        run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both',
            '--use-drill-file-origin', '-o', pos, PCB)
        placed = list(csv.DictReader(open(pos)))
    n = 0
    with open(os.path.join(OUT, 'cpl_jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in placed:
            # only what has a part to feed: H1 is not in the BOM at all, J1 has no LCSC number
            if r['Ref'] not in machine: hand.add(r['Ref']); continue
            rot = (float(r['Rot']) + ROT_OFFSET.get(r['Package'], 0)) % 360
            w.writerow([r['Ref'], f"{float(r['PosX']):.3f}mm", f"{float(r['PosY']):.3f}mm",
                        'Top' if r['Side'] == 'top' else 'Bottom', f'{rot:.0f}'])
            n += 1
    back = [r['Ref'] for r in placed if r['Side'] != 'top']
    for side in ('top', 'bottom'):
        run('pcb', 'render', '--side', side, '--width', '1000', '--height', '1400', '--quality', 'high',
            '-o', os.path.join(OUT, f'render-{side}.png'), PCB)
    print('gerbers:', len(os.listdir(g)), 'files ->', z)
    print('cpl:', n, 'placements; not machine-placed:', ', '.join(sorted(hand)) or '-')
    print('back-side parts:', ', '.join(back) or 'none (single-sided assembly)')


if __name__ == '__main__':
    main()
