#!/usr/bin/env python3
"""Generate hardware/dbfob.kicad_sch from the tables below.

The tables are the source of truth (etofab.md §1): hand edits to the sheet are lost on the next
run. Every symbol connects by net labels placed on its pin tips, so the drawing is a set of tidy
blocks rather than a wire diagram; UUIDs derive from the reference designator, so a re-run with
unchanged tables writes a byte-identical file.

  python3 hardware/tools/gen_sch.py && kicad-cli sch erc hardware/dbfob.kicad_sch
"""
import os, re, uuid

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'dbfob.kicad_sch')
LIB = '/usr/share/kicad/symbols'
NS = uuid.UUID('b3a0d7e2-5c1f-4e8a-9d2b-7f6e1c0a4d35')
ROOT = str(uuid.uuid5(NS, 'root'))


def uid(*k): return str(uuid.uuid5(NS, '/'.join(map(str, k))))


# ---------------------------------------------------------------------------------------------
# Parts. LCSC numbers checked against JLC's parts API on 2026-09-27; each belongs to its package
# (etofab.md §2). CH32V002/V006 were out of stock at JLC and LCSC, so U1 is loaded with the
# pin-compatible CH32V003F4P6 (same TSSOP-20 pinout, pin table checked against the V002 datasheet
# table 2-1). Swap the LCSC number when V002/V006 stock returns; the board does not change.
#
# ref: lib_id, value, footprint, LCSC, MPN, note, (x, y, rot) on the sheet, {pin: net}
# ---------------------------------------------------------------------------------------------
LED_FP = 'LED_SMD:LED_0603_1608Metric'
R_FP = 'Resistor_SMD:R_0603_1608Metric'
C_FP = 'Capacitor_SMD:C_0603_1608Metric'

PARTS = {
    'U1': ('MCU_WCH_RiscV:CH32V003FxPx', 'CH32V003F4P6', 'Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm',
           'C5187096', 'CH32V003F4P6', 'drop-in: CH32V002F4P6 / CH32V006F8P6 (same TSSOP-20 pinout)',
           (127, 95, 0),
           {'9': 'VBAT', '7': 'GND',
            '15': 'MIC_CLK',     # PC5 SPI_SCK: PDM clock out
            '17': 'MIC_DATA',    # PC7 SPI_MISO: PDM data in
            '16': 'MIC_VDD',     # PC6 GPIO: mic supply, off between presses
            '20': 'LED_G',       # PD3 TIM2_CH2
            '19': 'LED_Y',       # PD2 TIM1_CH1
            '14': 'LED_O',       # PC4 TIM1_CH4
            '13': 'LED_R',       # PC3 TIM1_CH3
            '10': 'BTN',         # PC0 EXTI wake
            '18': 'SWIO',        # PD1 programming / debug
            '2': 'TX',           # PD5 USART1_TX: dB readout for calibration
            }),
    'MK1': ('Sensor_Audio:IM69D130', 'IM69D130', 'Sensor_Audio:Infineon_PG-LLGA-5-1',
            'C536262', 'IM69D130V01XTSA1', 'bottom port: the NPTH in the footprint is the sound inlet',
            (200, 90, 0),
            {'2': 'MIC_VDD', '5': 'GND', '3': 'MIC_CLK', '1': 'MIC_DATA', '4': 'GND'}),
    'C3': ('Device:C', '100n', C_FP, 'C14663', 'CC0603KRX7R9BB104', 'mic decoupling, next to MK1',
           (220, 90, 0), {'1': 'MIC_VDD', '2': 'GND'}),
    'C1': ('Device:C', '100n', C_FP, 'C14663', 'CC0603KRX7R9BB104', 'U1 decoupling, next to pin 9',
           (95, 130, 0), {'1': 'VBAT', '2': 'GND'}),
    'C2': ('Device:C', '10u', C_FP, 'C19702', 'CL10A106KP8NNNC', 'bulk: coin cell ESR vs LED + mic current',
           (80, 130, 0), {'1': 'VBAT', '2': 'GND'}),
    'BT1': ('Device:Battery_Cell', 'CR2032', 'Battery:BatteryHolder_Keystone_3034_1x20mm',
            'C5213768', 'Keystone 3034TR', 'negative contact is the PCB pad under the cell',
            (60, 130, 0), {'1': 'VBAT', '2': 'GND'}),
    'SW1': ('Switch:SW_Push', 'measure', 'Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A',
            'C318884', 'TS-1187A-B-A-B', 'internal pull-up on PC0',
            (200, 135, 0), {'1': 'BTN', '2': 'GND'}),
    'J1': ('Connector_Generic:Conn_01x04', 'PROG', 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
           '', '', 'not fitted: WCH-LinkE pogo/pins; 1 VBAT, 2 SWIO, 3 GND, 4 TX',
           (45, 95, 0), {'1': 'VBAT', '2': 'SWIO', '3': 'GND', '4': 'TX'}),
    'H1': ('Mechanical:MountingHole', 'keyring', 'MountingHole:MountingHole_3.2mm_M3',
           '', '', 'keyring hole', (240, 150, 0), {}),
}
# LED bar: four low-Vf AlInGaP/GaP parts (1.6-2.6 V) so every colour still lights on a coin cell
# near end of life; InGaN green/blue need ~3 V and would not. Current ~2 mA from a 3.0 V cell.
LEDS = [  # ref, colour, LCSC, MPN, R, R LCSC
    ('D1', 'LED_G', 'yellow-green 575nm', 'C89809', 'NCD0603C3', '220', 'C22962'),
    ('D2', 'LED_Y', 'yellow 590nm', 'C2287', 'KT-0603Y', '470', 'C23179'),
    ('D3', 'LED_O', 'orange 605nm', 'C111340', 'KT-0603O', '470', 'C23179'),
    ('D4', 'LED_R', 'red 625nm', 'C2286', 'KT-0603R', '470', 'C23179'),
]
for i, (d, net, col, lcsc, mpn, rv, rl) in enumerate(LEDS):
    x = 45 + 30 * i
    PARTS['R%d' % (i + 4)] = ('Device:R', rv, R_FP, rl, '', 'LED current', (x, 40, 0),
                              {'1': net, '2': net + '_A'})
    # Device:LED pin 1 = K, pin 2 = A
    PARTS[d] = ('Device:LED', col, LED_FP, lcsc, mpn, '', (x, 62, 90), {'2': net + '_A', '1': 'GND'})

# MIC_VDD is driven by a GPIO, which ERC cannot know: flag it rather than leave the error standing
FLAGS = {'#FLG01': ('VBAT', (60, 115)), '#FLG02': ('GND', (70, 150)), '#FLG03': ('MIC_VDD', (230, 75))}
NOCONNECT = {'U1': ['1', '3', '4', '5', '6', '8', '11', '12']}
TEXT = [
    ('dbfob - keyfob sound level indicator', (20, 20), 2.5),
    ('PDM mic on SPI: PC5 SCK -> CLK, PC7 MISO <- DATA, mic powered from PC6 only while measuring.', (20, 175), 1.5),
    ('LEDs on timer channels for PWM: D1 PD3 T2C2, D2 PD2 T1C1, D3 PC4 T1C4, D4 PC3 T1C3.', (20, 180), 1.5),
    ('U1 fitted as CH32V003F4P6 (in stock); CH32V002F4P6 / CH32V006F8P6 are drop-in on this footprint.', (20, 185), 1.5),
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
    if lib not in _libs: _libs[lib] = open(os.path.join(LIB, lib + '.kicad_sym')).read()
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


def symbol(ref, lib_id, value, fp, lcsc, mpn, note, x, y, r, in_bom=True, on_board=True):
    p = pins(lib_id)
    power = ref.startswith('#')
    out = (f'\t(symbol\n\t\t(lib_id "{lib_id}")\n\t\t(at {fmt(x)} {fmt(y)} {r})\n\t\t(unit 1)\n'
           f'\t\t(exclude_from_sim no)\n\t\t(in_bom {"yes" if in_bom else "no"})\n'
           f'\t\t(on_board {"yes" if on_board else "no"})\n\t\t(dnp no)\n\t\t(uuid "{uid("sym", ref)}")\n')
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
    out += (f'\t\t(instances (project "dbfob" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n\t)\n')
    return out


def tip(lib_id, pin, x, y, r):
    px, py, pa = pins(lib_id)[pin]
    dx, dy = rot(px, py, r)
    return x + dx, y - dy, (pa + r) % 360


def label(net, x, y, pin_angle):
    # the pin's angle points from its tip into the body; the label points the other way
    a = (pin_angle + 180) % 360
    just = 'left bottom' if a in (0, 90) else 'right bottom'
    return (f'\t(label "{net}"\n\t\t(at {fmt(x)} {fmt(y)} {a})\n\t\t(fields_autoplaced yes)\n'
            f'\t\t(effects (font (size 1.27 1.27)) (justify {just}))\n\t\t(uuid "{uid("label", net, fmt(x), fmt(y))}")\n\t)\n')


def main():
    used = sorted({p[0] for p in PARTS.values()} | {'power:PWR_FLAG'})
    body = ''
    wired = {}       # nets drawn as a wire between their pin tips instead of labels
    for ref in sorted(PARTS, key=lambda k: (re.sub(r'\d', '', k), int(re.sub(r'\D', '', k) or 0))):
        lib_id, value, fp, lcsc, mpn, note, (x, y, r), nets = PARTS[ref]
        x, y = snap(x), snap(y)
        in_bom = ref not in ('H1',)
        body += symbol(ref, lib_id, value, fp, lcsc, mpn, note, x, y, r, in_bom=in_bom)
        for pin, net in nets.items():
            tx, ty, pa = tip(lib_id, pin, x, y, r)
            if net.endswith('_A'): wired.setdefault(net, []).append((tx, ty))
            else: body += label(net, tx, ty, pa)
        for pin in NOCONNECT.get(ref, []):
            tx, ty, _ = tip(lib_id, pin, x, y, r)
            body += f'\t(no_connect\n\t\t(at {fmt(tx)} {fmt(ty)})\n\t\t(uuid "{uid("nc", ref, pin)}")\n\t)\n'
    for net, pts in sorted(wired.items()):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            assert x1 == x2 or y1 == y2, net   # no diagonal wires
            body += (f'\t(wire\n\t\t(pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}))\n'
                     f'\t\t(stroke (width 0) (type default))\n\t\t(uuid "{uid("wire", net)}")\n\t)\n')
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
           f'\t(title_block (title "dbfob") (rev "A") (comment 1 "generated by hardware/tools/gen_sch.py - edit the tables, not this file"))\n'
           f'\t(lib_symbols\n{libs}\t)\n{body}'
           f'\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n')
    open(OUT, 'w').write(out)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
