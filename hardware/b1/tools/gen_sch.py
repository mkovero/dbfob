#!/usr/bin/env python3
"""Generate hardware/b1/b1.kicad_sch from the tables below.

B1: rev A done properly, as a stick (docs/rev-b.md, "B1 stick"). 10.5 x 94 mm, an AAA cell on
the back between two spring contacts, a TLV61220 boost converter making 3.0 V from it, the NFC
coil in the tip (../lib/antenna.py, identical to the NFC test board's), and on the parts face:
CH32L103 MCU, IM66D130M PDM mic at the tip, NT3H2111 tag, four LEDs, button.
Same method as rev A's gen_sch.py (etofab.md §1): the tables are the source, labels on pin tips,
UUIDs from reference designators.

  python3 hardware/lib/gen_lib.py
  python3 hardware/b1/tools/gen_sch.py && kicad-cli sch erc hardware/b1/b1.kicad_sch
"""
import os, re, uuid

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'b1'
OUT = os.path.join(HERE, NAME + '.kicad_sch')
LIBS = {'dbfob': os.path.join(HERE, '..', 'lib', 'dbfob.kicad_sym')}   # project library
LIB = '/usr/share/kicad/symbols'
NS = uuid.UUID('8e41b0d2-5c7a-4f13-b6e9-2d0a9c4f7e35')
ROOT = str(uuid.uuid5(NS, 'root'))


def uid(*k): return str(uuid.uuid5(NS, '/'.join(map(str, k))))


# ---------------------------------------------------------------------------------------------
# Parts. LCSC numbers and stock checked against JLC's parts API on 2026-11-09.
# ref: lib_id, value, footprint, LCSC, MPN, note, (x, y, rot) on the sheet, {pin: net}, dnp
# A part with no LCSC number lands in the manual BOM (etofab.md §2).
# ---------------------------------------------------------------------------------------------
R_FP = 'Resistor_SMD:R_0603_1608Metric'
C_FP = 'Capacitor_SMD:C_0603_1608Metric'

LED_FP = 'LED_SMD:LED_0603_1608Metric'

# CH32L103F8U6 pin use (datasheet V2.1 table 2-1-1, QFN20 column). Pins sharing a pad inside the
# chip (note 8) may have only one of the pair as an output.
#   1 PA0 WKUP      BTN. The button goes to VBAT: with EWUP set, WKUP is forced to an input with
#                   pull-down and a rising edge wakes Standby on every lot (RM PWR_CSR). No
#                   external resistor. (PB13 was tried first: it shares the pad with PB6 = CC1,
#                   whose 5.1k pull-down some lots force on in Standby, DS table 3-8-1 note 3.)
#   2 PA1 TIM2_CH2  LED_O    3 PA2 TIM2_CH3 LED_Y    4 PA3 TIM2_CH4 LED_G
#  14 PA8 TIM1_CH1  LED_R    (every LED on its own hardware PWM channel)
#  18 PA10          LED_R_K (D4 cathode: low to light, high + input to sense ambient light).
#                   Shares PB7 = CC2: keep CC2_PD off.
#   5 PA4           MIC_PWR, through R8 + C6 to the mic (also SPI1_NSS: use SSM=1, SSOE=0)
#   6 PA5 SPI1_SCK  MIC_CLK (PDM clock)   20 PA6 SPI1_MISO MIC_DATA
#   7 PA7 ADC7      VCELL: the cell, straight in (0.9-1.8 V, under VDD), for the low-battery lockout
#   8 PB0           FD (EXTI: a phone's field wakes the MCU; Standby wake by EXTI event is
#                   still to be shown on the bench, Stop is the fallback)
#   9 PB10 I2C2_SCL SCL (PB1 shares the pad: keep it an input)    10 PB11 I2C2_SDA SDA
#  15 PA9 USART1_TX TX: the dB stream and a UART bootloader, as rev A's PD5
#  17 PA13 SWDIO, 16 PA14 SWCLK: WCH-LinkE (2-wire SDI)
#  12 PB14          NFC_VCC (tag supply). Not PB13: it shares the pad with PB6 = CC1.
#  11 PB13, 13 PB15: spare.  19 VDD, 21 EP: VSS.  No NRST pin, BOOT0 tied low inside.
#  Firmware: PB2 (no pin on this package) as pull-down input in low power (DS note 5).
MCU = {'1': 'BTN', '2': 'LED_O', '3': 'LED_Y', '4': 'LED_G', '14': 'LED_R', '18': 'LED_R_K',
       '5': 'MIC_PWR', '6': 'MIC_CLK', '20': 'MIC_DATA', '7': 'VCELL', '12': 'NFC_VCC', '8': 'FD',
       '9': 'SCL', '10': 'SDA', '15': 'TX', '17': 'SWDIO', '16': 'SWCLK', '19': 'VDD', '21': 'GND'}

PARTS = {
    'U2': ('dbfob:CH32L103F8U6', 'CH32L103F8U6', 'Package_DFN_QFN:UQFN-20-1EP_3x3mm_P0.4mm_EP1.85x1.85mm',
           'C22467836', 'CH32L103F8U6', 'RV32IMAC, 1.8-3.6 V, Standby < 1 uA', (120, 90, 0), MCU, False),
    'C4': ('Device:C', '100n', C_FP, 'C14663', 'CC0603KRX7R9BB104', 'U2 decoupling, by pin 19',
           (60, 140, 0), {'1': 'VDD', '2': 'GND'}, False),
    'C5': ('Device:C', '10u', C_FP, 'C19702', 'CL10A106KP8NNNC', 'boost output (TLV61220: >= L/2 in uF)',
           (75, 140, 0), {'1': 'VDD', '2': 'GND'}, False),
    # Power: one AAA (Li-FeS2 L92, alkaline or NiMH, 0.9-1.8 V) boosted to 3.0 V. TLV61220 starts
    # from 0.7 V; Iq 0.5 uA from VBAT + 5 uA into VOUT. EN to the cell: always on, the MCU's
    # Standby sets the floor. VOUT = 0.5 V x (1 + R9/R10) = 3.0 V; R10 <= 500k per the datasheet
    # (>= 1 uA in the divider): 1M / 200k draws 2.5 uA.
    'U3': ('dbfob:TLV61220', 'TLV61220', 'Package_TO_SOT_SMD:SOT-23-6', 'C111811', 'TLV61220DBVR',
           'boost 0.7-5.5 V in, 3.0 V out', (300, 140, 0),
           {'6': 'VCELL', '3': 'VCELL', '1': 'SW', '2': 'GND', '5': 'VDD', '4': 'FB'}, False),
    'L1': ('Device:L', '4.7u', 'dbfob:L_0806_2016Metric_MPL2016', 'C98335', 'MPL2016S4R7MHT',
           'boost inductor: 4.7 uH, 1.1 A, 110 mOhm, multilayer (closed field)', (270, 130, 90),
           {'1': 'VCELL', '2': 'SW'}, False),
    'C7': ('Device:C', '10u', C_FP, 'C19702', 'CL10A106KP8NNNC', 'boost input, by U3 pin 6',
           (255, 150, 0), {'1': 'VCELL', '2': 'GND'}, False),
    'R9': ('Device:R', '1M', R_FP, 'C22935', '0603WAF1004T5E', 'feedback top', (330, 130, 0),
           {'1': 'VDD', '2': 'FB'}, False),
    'R10': ('Device:R', '200k', R_FP, 'C25811', '0603WAF2003T5E', 'feedback bottom', (330, 150, 0),
            {'1': 'FB', '2': 'GND'}, False),
    # Mic: IM66D130M at the tip, inside the coil, bottom port through the board. Powered from PA4
    # only while measuring, through R8 + C6 (1.6 kHz): the boost converter's burst ripple at light
    # load stays off the mic's supply. 100 Ohm x 0.54 mA = 54 mV. LR to
    # GND as rev A's SELECT: data valid on the same clock edge. 0 stock at JLC on
    # 2026-11-03, 20 on 2026-11-09: order early, or global sourcing / consignment.
    'MK1': ('dbfob:IM66D130M', 'IM66D130M', 'dbfob:Infineon_IM66D130M_LGA-5_3x2mm', 'C52053030',
            'IM66D130MV01XTMA1', 'bottom port: the 0.5 mm NPTH in the footprint is the sound inlet; '
            '20 at JLC on 2026-11-09, no EasyEDA footprint', (200, 60, 0),
            {'5': 'MIC_VDD', '4': 'MIC_CLK', '2': 'GND', '1': 'MIC_DATA', '3': 'GND'}, False),
    'R8': ('Device:R', '100', R_FP, 'C22775', '0603WAF1000T5E', 'mic supply filter, with C6', (215, 40, 90),
           {'1': 'MIC_PWR', '2': 'MIC_VDD'}, False),
    'C6': ('Device:C', '1u', C_FP, 'C15849', 'CL10A105KB8NNNC', 'mic decoupling, next to MK1 (DS table 5 note 2: 1 uF)',
           (230, 60, 0), {'1': 'MIC_VDD', '2': 'GND'}, False),
    # NFC: NT3H2111 pinout from the NXP datasheet's table 3 (XQFN8). The antenna block (U1, NT1,
    # C1-C3 and the coil) is placed by ../lib/antenna.py exactly as on the NFC test board.
    'U1': ('dbfob:NT3H2111W0FHK', 'NT3H2111W0FHK', 'dbfob:NXP_XQFN-8_1.6x1.6mm_P0.5mm',
           'C710403', 'NT3H2111W0FHKH', 'NTAG I2C plus 1k; VOUT unused', (200, 110, 0),
           {'1': 'LA', '8': 'LB', '2': 'GND', '6': 'NFC_VCC', '5': 'SDA', '3': 'SCL', '4': 'FD'}, False),
    'NT1': ('Device:NetTie_2', 'antenna', 'NetTie:NetTie-2_SMD_Pad0.5mm', '', '',
            'inner end of the PCB coil: 9 turns, 0.15 mm / 0.15 mm, about 2.25 uH in air',
            (160, 90, 0), {'1': 'LA', '2': 'LB'}, False),
    'C1': ('Device:C', 'tune C0G', C_FP, '', '', 'not fitted: antenna trim, value found on the bench',
           (160, 110, 0), {'1': 'LA', '2': 'LB'}, True),
    'C2': ('Device:C', 'tune C0G', C_FP, '', '', 'not fitted: second trim position',
           (175, 110, 0), {'1': 'LA', '2': 'LB'}, True),
    'C3': ('Device:C', '100n', C_FP, 'C14663', 'CC0603KRX7R9BB104', 'tag VCC decoupling, by U1 pin 6',
           (240, 100, 0), {'1': 'NFC_VCC', '2': 'GND'}, False),
    # I2C pull-ups go to the tag's supply, so with NFC_VCC low nothing powers the tag through them.
    'R1': ('Device:R', '4.7k', R_FP, 'C23162', '0603WAF4701T5E', 'SDA pull-up to NFC_VCC',
           (240, 120, 0), {'1': 'NFC_VCC', '2': 'SDA'}, False),
    'R2': ('Device:R', '4.7k', R_FP, 'C23162', '0603WAF4701T5E', 'SCL pull-up to NFC_VCC',
           (255, 120, 0), {'1': 'NFC_VCC', '2': 'SCL'}, False),
    # FD is open drain and pulls low while a reader's field is on, with or without NFC_VCC.
    'R3': ('Device:R', '100k', R_FP, 'C25803', '0603WAF1003T5E', 'FD pull-up to VDD: 30 uA only while a field is on',
           (255, 140, 0), {'1': 'VDD', '2': 'FD'}, False),
    # to VDD: PA0/WKUP has its own pull-down in Standby (see the pin table)
    'SW1': ('Switch:SW_Push', 'measure', 'Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A', 'C318884',
            'TS-1187A-B-A-B', '', (60, 60, 0), {'1': 'BTN', '2': 'VDD'}, False),
    'BT1': ('Device:Battery_Cell', 'AAA', 'dbfob:BatteryContacts_MYOUNG_MY-AAA-07_1xAAA', '',
            'MY-AAA-07', 'two spring contacts, hand-fit on the back (LCSC C6937109); + towards the far end',
            (40, 140, 0), {'1': 'VCELL', '2': 'GND'}, False),
    # Tag-Connect TC2050-IDC (legged plug: its clips latch through the board) footprint, no part
    # fitted. ARM Cortex 10-pin pinout: 1 VTref = VDD, 2 SWDIO, 3/5/9 GND, 4 SWCLK, 6 SWO = TX
    # (the dB stream), 7 key, 8 NC, 10 nRESET (the CH32L103F8U6 has no NRST pin). A probe that
    # powers pin 1 feeds VDD past the converter (its rectifier blocks the way back).
    'J1': ('Connector_Generic:Conn_02x05_Odd_Even', 'PROG',
           'Connector:Tag-Connect_TC2050-IDC-FP_2x05_P1.27mm_Vertical', '', '',
           'Tag-Connect TC2050-IDC (legged) footprint, ARM 10-pin SWD: 1 VDD, 2 SWDIO, 4 SWCLK, 6 TX, 3/5/9 GND',
           (30, 90, 0), {'1': 'VDD', '2': 'SWDIO', '3': 'GND', '4': 'SWCLK', '5': 'GND', '6': 'TX', '9': 'GND'},
           False),
    # at the far end, opposite the mic: the stick hangs mic-down from a split ring
    'H1': ('Mechanical:MountingHole', 'keyring', 'MountingHole:MountingHole_3.2mm_M3', '', '',
           'keyring hole, 3.2 mm NPTH', (30, 110, 0), {}, False),
}
# LED bar as rev A: four low-Vf AlInGaP/GaP parts, deliberately dim; now from the regulated 3.0 V. D4's cathode goes to PA10: reverse-biased and timed, it senses ambient light.
LEDS = [  # ref, net, colour, LCSC, MPN, R, R LCSC, cathode net
    ('D1', 'LED_G', 'yellow-green 575nm', 'C89809', 'NCD0603C3', '1k', 'C21190', 'GND'),
    ('D2', 'LED_Y', 'yellow 590nm', 'C2287', 'KT-0603Y', '2.2k', 'C4190', 'GND'),
    ('D3', 'LED_O', 'orange 605nm', 'C111340', 'KT-0603O', '2.2k', 'C4190', 'GND'),
    ('D4', 'LED_R', 'red 625nm', 'C2286', 'KT-0603R', '2.2k', 'C4190', 'LED_R_K'),
]
for i, (d, net, col, lcsc, mpn, rv, rl, k) in enumerate(LEDS):
    x = 120 + 25 * i
    PARTS['R%d' % (i + 4)] = ('Device:R', rv, R_FP, rl, '', 'LED current', (x, 30, 0),
                              {'1': net, '2': net + '_A'}, False)
    PARTS[d] = ('Device:LED', col, LED_FP, lcsc, mpn, '', (x, 50, 90), {'2': net + '_A', '1': k}, False)

# MIC_VDD and NFC_VCC are driven by GPIOs, which ERC cannot know: flag them
# The cell's contacts are passive pins, and MIC_VDD / NFC_VCC come from GPIOs: flag them for ERC
FLAGS = {'#FLG01': ('VCELL', (40, 120)), '#FLG02': ('GND', (100, 150)), '#FLG03': ('MIC_VDD', (230, 40)),
         '#FLG04': ('NFC_VCC', (270, 100))}
NOCONNECT = {'U1': ['7'], 'U2': ['11', '13'], 'J1': ['7', '8', '10']}
TEXT = [
    ('dbfob B1 - AAA stick with NFC readout', (20, 20), 2.5),
    ('PDM mic on SPI1: PA5 SCK -> CLK at 1.5 MHz, PA6 MISO <- DATA. Mic powered from PA4 (via R8/C6) while measuring.', (20, 158), 1.5),
    ('LED PWM: PA1 O, PA2 Y, PA3 G (TIM2 CH2-4), PA8 R (TIM1 CH1). D4 cathode on PA10 = light sense.', (20, 162), 1.5),
    ('Tag on I2C2 (PB10/PB11), powered from PB14; FD (PB0) wakes. BTN on PA0/WKUP to VDD. TX on PA9.', (20, 166), 1.5),
    ('AAA (0.9-1.8 V) -> TLV61220 -> VDD 3.0 V. PA7 (ADC7) reads the cell.', (20, 170), 1.5),
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
        in_bom = lib_id not in ('Device:NetTie_2', 'Jumper:SolderJumper_2_Open', 'Mechanical:MountingHole') and ref != 'J1'   # not parts
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
           f'\t(title_block (title "dbfob B1") (rev "B1") (comment 1 "generated by hardware/b1/tools/gen_sch.py - edit the tables, not this file"))\n'
           f'\t(lib_symbols\n{libs}\t)\n{body}'
           f'\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n')
    open(OUT, 'w').write(out)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
