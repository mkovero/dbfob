#!/usr/bin/env python3
"""Generate hardware/nfc-test/nfc-test.kicad_sch from the tables below.

The NFC test board for rev B (B1): an NT3H2111 tag with B1's antenna, over a CR2032 in B1's
holder, so the antenna, the ferrite sheet and the tuning can be measured on the real stack. It
carries no MCU: a phone reads and writes the tag through RF alone, and the header gives any MCU
the I2C bus and the field-detect line. Same method as rev A's gen_sch.py (etofab.md §1): the
tables are the source, labels on pin tips, UUIDs from reference designators.

  python3 hardware/lib/gen_lib.py                 # project symbols / footprints
  python3 hardware/nfc-test/tools/gen_sch.py && kicad-cli sch erc hardware/nfc-test/nfc-test.kicad_sch
"""
import os, re, uuid

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'nfc-test'
OUT = os.path.join(HERE, NAME + '.kicad_sch')
LIBS = {'dbfob': os.path.join(HERE, '..', 'lib', 'dbfob.kicad_sym')}   # project library
LIB = '/usr/share/kicad/symbols'
NS = uuid.UUID('0d7c2f4e-8a1b-4c3d-9e5f-6a7b8c9d0e1f')
ROOT = str(uuid.uuid5(NS, 'root'))


def uid(*k): return str(uuid.uuid5(NS, '/'.join(map(str, k))))


# ---------------------------------------------------------------------------------------------
# Parts. LCSC numbers and stock checked against JLC's parts API on 2026-11-03.
# ref: lib_id, value, footprint, LCSC, MPN, note, (x, y, rot) on the sheet, {pin: net}, dnp
# A part with no LCSC number lands in the manual BOM (etofab.md §2).
# ---------------------------------------------------------------------------------------------
R_FP = 'Resistor_SMD:R_0603_1608Metric'
C_FP = 'Capacitor_SMD:C_0603_1608Metric'

PARTS = {
    # NT3H2111 pinout from the NXP datasheet's table 3 (XQFN8), not from the part name
    'U1': ('dbfob:NT3H2111W0FHK', 'NT3H2111W0FHK', 'dbfob:NXP_XQFN-8_1.6x1.6mm_P0.5mm',
           'C710403', 'NT3H2111W0FHKH', 'NTAG I2C plus 1k; VOUT unused (no energy harvesting)',
           (120, 80, 0),
           {'1': 'LA', '8': 'LB', '2': 'GND', '6': 'VCC', '5': 'SDA', '3': 'SCL', '4': 'FD'}, False),
    # The antenna is copper on the board (make_pcb.py draws it as LA tracks). Its inner end
    # meets LB through this net tie, so the coil is the one place LA and LB are allowed to touch.
    'NT1': ('Device:NetTie_2', 'antenna', 'NetTie:NetTie-2_SMD_Pad0.5mm', '', '',
            'inner end of the PCB coil: 6 turns, 0.25 mm / 0.2 mm, about 2.1 uH in air',
            (75, 60, 0), {'1': 'LA', '2': 'LB'}, False),
    # Tuning: the tag has 50 pF (44-56) inside, so 13.56 MHz wants 2.75 uH. The coil is drawn
    # short of that on purpose (a parallel C can only lower the resonance), and these two pads
    # take C0G trim caps by hand once the coil is measured with the cell and ferrite in place.
    'C1': ('Device:C', 'tune C0G', C_FP, '', '', 'not fitted: antenna trim, C0G, chosen on the bench',
           (75, 80, 0), {'1': 'LA', '2': 'LB'}, True),
    'C2': ('Device:C', 'tune C0G', C_FP, '', '', 'not fitted: second trim position',
           (90, 80, 0), {'1': 'LA', '2': 'LB'}, True),
    'C3': ('Device:C', '100n', C_FP, 'C14663', 'CC0603KRX7R9BB104', 'VCC decoupling, next to U1 pin 6',
           (160, 60, 0), {'1': 'VCC', '2': 'GND'}, False),
    'R1': ('Device:R', '4.7k', R_FP, 'C23162', '0603WAF4701T5E', 'SDA pull-up to VCC',
           (175, 60, 0), {'1': 'VCC', '2': 'SDA'}, False),
    'R2': ('Device:R', '4.7k', R_FP, 'C23162', '0603WAF4701T5E', 'SCL pull-up to VCC',
           (190, 60, 0), {'1': 'VCC', '2': 'SCL'}, False),
    # FD is open drain and works from the RF field with VCC off, as B1 will use it to wake the
    # MCU. Pulled up to the cell, not to VCC, and the LED lights while a reader's field is on:
    # a range check with no MCU and no app.
    'R3': ('Device:R', '10k', R_FP, 'C25804', '0603WAF1002T5E', 'FD pull-up to the cell',
           (175, 100, 0), {'1': 'VBAT', '2': 'FD'}, False),
    'R4': ('Device:R', '1k', R_FP, 'C21190', '0603WAF1001T5E', 'field LED current, ~1 mA',
           (190, 100, 0), {'1': 'VBAT', '2': 'LED_A'}, False),
    'D1': ('Device:LED', 'red', 'LED_SMD:LED_0603_1608Metric', 'C2286', 'KT-0603R', 'on while a field is present',
           (205, 100, 90), {'2': 'LED_A', '1': 'FD'}, False),
    'JP1': ('Jumper:SolderJumper_2_Open', 'VCC=VBAT', 'Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm', '', '',
            'bridge to power the tag from the cell (I2C with no host supply)',
            (60, 120, 0), {'1': 'VBAT', '2': 'VCC'}, False),
    # Same holder as B1, on the back. It is hand-soldered here: two large pads, and it keeps
    # the board a one-sided JLC assembly.
    'BT1': ('Device:Battery_Cell', 'CR2032', 'dbfob:BatteryHolder_MYOUNG_BS-08-B2AA001_CR2032', '',
            'BS-08-B2AA001', 'hand-fit on the back (LCSC C964777); ferrite sheet between holder floor and cell',
            (40, 120, 0), {'1': 'VBAT', '2': 'GND'}, False),
    'J1': ('Connector_Generic:Conn_01x06', 'HOST', 'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',
           '', '', 'not fitted: 1 VBAT, 2 VCC, 3 SDA, 4 FD, 5 SCL, 6 GND (order follows U1 sides)',
           (230, 80, 0), {'1': 'VBAT', '2': 'VCC', '3': 'SDA', '4': 'FD', '5': 'SCL', '6': 'GND'}, False),
}

FLAGS = {'#FLG01': ('VBAT', (40, 100)), '#FLG02': ('GND', (100, 130)), '#FLG03': ('VCC', (140, 45))}
NOCONNECT = {'U1': ['7']}
TEXT = [
    ('dbfob NFC test board (for rev B / B1)', (20, 20), 2.5),
    ('Tag: NT3H2111 (NTAG I2C plus 1k), Type 2. A phone reads/writes it with no MCU and no VCC.', (20, 150), 1.5),
    ('Antenna: PCB coil, LA tracks closed to LB by NT1. Trim with C1/C2 (C0G) on the bench.', (20, 154), 1.5),
    ('FD: open drain, works from the field alone; D1 lights while a reader field is on.', (20, 158), 1.5),
    ('J1 for any host MCU: VBAT VCC SDA FD SCL GND. JP1 powers the tag from the cell.', (20, 162), 1.5),
    ('BT1 on the back, hand-fitted; ferrite sheet between holder floor and cell.', (20, 166), 1.5),
]


# ---------------------------------------------------------------------------------------------
def block(text, start):
    d = 0
    for j in range(start, len(text)):
        if text[j] == '(': d += 1
        elif text[j] == ')':
            d -= 1
            if d == 0: return text[start:j + 1]
    raise ValueError


_libs = {}


def lib_symbol(lib_id):
    """The library symbol, flattened if it extends another, renamed to its lib_id."""
    lib, name = lib_id.split(':')
    if lib not in _libs:
        _libs[lib] = open(LIBS.get(lib, os.path.join(LIB, lib + '.kicad_sym'))).read()
    t = _libs[lib]
    s = block(t, t.index(f'\t(symbol "{name}"\n'))
    m = re.search(r'\(extends "([^"]+)"\)', s)
    if m:
        parent = block(t, t.index(f'\t(symbol "{m.group(1)}"\n'))
        props = dict(re.findall(r'\(property "([^"]+)" "([^"]*)"', s))
        for k, v in props.items():
            parent = re.sub(rf'(\(property "{re.escape(k)}" )"[^"]*"', lambda mm: mm.group(1) + '"' + v.replace('\\', '\\\\') + '"', parent, count=1)
        parent = parent.replace(f'(symbol "{m.group(1)}_', f'(symbol "{name}_')
        s = parent.replace(f'(symbol "{m.group(1)}"', f'(symbol "{name}"', 1)
    return s.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)


def pins(lib_id):
    """pin number -> (x, y, angle) of its connection point in symbol coordinates (y up)."""
    s = lib_symbol(lib_id)
    out = {}
    for m in re.finditer(r'\(pin \w+ \w+\s+\(at ([-\d.]+) ([-\d.]+) (\d+)\)(?:(?!\(pin ).)*?\(number "([^"]*)"', s, re.S):
        out[m.group(4)] = (float(m.group(1)), float(m.group(2)), int(m.group(3)))
    return out


def rot(x, y, r):
    r %= 360
    return {0: (x, y), 90: (-y, x), 180: (-x, -y), 270: (y, -x)}[r]


def fmt(v): return ('%.4f' % v).rstrip('0').rstrip('.')


def prop(name, val, x, y, hide=False, a=0):
    h = ' (hide yes)' if hide else ''
    return (f'\t\t(property "{name}" "{val}"\n\t\t\t(at {fmt(x)} {fmt(y)} {a})\n'
            f'\t\t\t(effects (font (size 1.27 1.27)){h})\n\t\t)\n')


def snap(v, g=2.54): return round(v / g) * g


def symbol(ref, lib_id, value, fp, lcsc, mpn, note, x, y, r, in_bom=True, on_board=True, dnp=False):
    p = pins(lib_id)
    power = ref.startswith('#')
    out = (f'\t(symbol\n\t\t(lib_id "{lib_id}")\n\t\t(at {fmt(x)} {fmt(y)} {r})\n\t\t(unit 1)\n'
           f'\t\t(exclude_from_sim no)\n\t\t(in_bom {"yes" if in_bom else "no"})\n'
           f'\t\t(on_board {"yes" if on_board else "no"})\n\t\t(dnp {"yes" if dnp else "no"})\n'
           f'\t\t(uuid "{uid("sym", ref)}")\n')
    out += prop('Reference', ref, x + 3, y - 6, hide=power)
    out += prop('Value', value, x + 3, y + 6, hide=power)
    out += prop('Footprint', fp, x, y, True)
    out += prop('Datasheet', '', x, y, True)
    if not power:
        out += prop('LCSC', lcsc, x, y, True)
        out += prop('MPN', mpn, x, y, True)
        out += prop('Note', note, x, y, True)
    for n in sorted(p, key=lambda k: (len(k), k)):
        out += f'\t\t(pin "{n}"\n\t\t\t(uuid "{uid("pin", ref, n)}")\n\t\t)\n'
    out += (f'\t\t(instances (project "{NAME}" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n\t)\n')
    return out


def tip(lib_id, pin, x, y, r):
    px, py, pa = pins(lib_id)[pin]
    dx, dy = rot(px, py, r)
    return x + dx, y - dy, (pa + r) % 360


def label(net, x, y, pin_angle):
    a = (pin_angle + 180) % 360
    just = 'left bottom' if a in (0, 90) else 'right bottom'
    return (f'\t(label "{net}"\n\t\t(at {fmt(x)} {fmt(y)} {a})\n\t\t(fields_autoplaced yes)\n'
            f'\t\t(effects (font (size 1.27 1.27)) (justify {just}))\n\t\t(uuid "{uid("label", net, fmt(x), fmt(y))}")\n\t)\n')


def main():
    used = sorted({p[0] for p in PARTS.values()} | {'power:PWR_FLAG'})
    body = ''
    for ref in sorted(PARTS, key=lambda k: (re.sub(r'\d', '', k), int(re.sub(r'\D', '', k) or 0))):
        lib_id, value, fp, lcsc, mpn, note, (x, y, r), nets, dnp = PARTS[ref]
        x, y = snap(x), snap(y)
        in_bom = lib_id not in ('Device:NetTie_2', 'Jumper:SolderJumper_2_Open')   # copper, not parts
        body += symbol(ref, lib_id, value, fp, lcsc, mpn, note, x, y, r, in_bom=in_bom, dnp=dnp)
        for pin, net in nets.items():
            tx, ty, pa = tip(lib_id, pin, x, y, r)
            body += label(net, tx, ty, pa)
        for pin in NOCONNECT.get(ref, []):
            tx, ty, _ = tip(lib_id, pin, x, y, r)
            body += f'\t(no_connect\n\t\t(at {fmt(tx)} {fmt(ty)})\n\t\t(uuid "{uid("nc", ref, pin)}")\n\t)\n'
    for ref, (net, (x, y)) in FLAGS.items():
        x, y = snap(x), snap(y)
        body += symbol(ref, 'power:PWR_FLAG', 'PWR_FLAG', '', '', '', '', x, y, 0, in_bom=False, on_board=False)
        tx, ty, pa = tip('power:PWR_FLAG', '1', x, y, 0)
        body += label(net, tx, ty, pa)
    for s, (x, y), size in TEXT:
        body += (f'\t(text "{s}"\n\t\t(exclude_from_sim no)\n\t\t(at {x} {y} 0)\n'
                 f'\t\t(effects (font (size {size} {size})) (justify left bottom))\n\t\t(uuid "{uid("text", s)}")\n\t)\n')
    libs = ''.join('\t\t' + lib_symbol(u).replace('\n', '\n\t') + '\n' for u in used)
    out = (f'(kicad_sch\n\t(version 20260306)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n'
           f'\t(uuid "{ROOT}")\n\t(paper "A4")\n'
           f'\t(title_block (title "dbfob NFC test") (rev "1") (comment 1 "generated by hardware/nfc-test/tools/gen_sch.py - edit the tables, not this file"))\n'
           f'\t(lib_symbols\n{libs}\t)\n{body}'
           f'\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n')
    open(OUT, 'w').write(out)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
