#!/usr/bin/env python3
"""Generate the project's own KiCad symbols and footprints for parts KiCad's libraries lack.

  python3 hardware/lib/gen_lib.py      # -> hardware/lib/dbfob.kicad_sym, hardware/lib/dbfob.pretty/

Like the board generators, the tables here are the source (etofab.md §1): the files are rewritten
on every run with UUIDs derived from names, so an unchanged table gives byte-identical output.

Sources, by part:
  NT3H2111W0FHK  NXP NT3H2111_2211 datasheet rev 3.0: pinning fig 3 / table 3 (XQFN8, transparent
                 top view, pins counter-clockwise from 1 at top left), package SOT902-3 fig 31
                 (D = E = 1.6, b = 0.20, L = 0.40, e = 0.6, e1 = 0.5). The centre "metal area not
                 for soldering" gets no pad.
  CH32L103F8U6   WCH CH32L103 datasheet V2.1, table 2-1-1 (QFN20 column) and fig. 4.4. Pins sharing a
                 pad inside the chip (note 8: PB1/PB10, PB6/PB13, PA12/PA14, PA11/PA13, PA10/PB7) are one
                 symbol pin named for both; only one of each pair may be an output. The footprint is
                 KiCad's UQFN-20-1EP_3x3mm_P0.4mm_EP1.85x1.85mm (datasheet EP 1.9 +-0.15).
  IM66D130M      Infineon IM66D130MV01 datasheet v1.1: pin table 9, package fig. 13, land pattern
                 fig. 15. Origin = body centre; the GND ring (pad 3) and sound port sit 0.54 mm to +x,
                 the pad columns at -0.55 and -1.15. The ring is a custom pad (KiCad's way for the
                 IM69D130 too). The PCB port is a 0.5 mm NPTH (datasheet: >= 0.375 mm; 0.5 is JLC's
                 smallest NPTH), so the ring's copper-free centre grows from 0.76 to 1.0 mm to keep
                 0.25 mm hole-to-copper. Paste: three ring segments with 0.1 mm vents, as fig. 15.
  BS-08-B2AA001  MYOUNG CR2032 holder, LCSC C964777: pads and body from the EasyEDA footprint and
                 3D model JLC places it with (pad 1 = +, 3.8 x 3.8 at x +11.02; pad 2 = -, 4.3 x
                 2.8 at x -10.98; body 25.4 x 15.7 x 5.3 mm centred at x -0.34). The holder brings
                 its own - spring under the cell, so the board under the cell can stay bare and a
                 ferrite sheet can lie between the holder floor and the cell.
"""
import math, os, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
NS = uuid.UUID('5a1e7c3d-2b4f-4e61-9a8d-0c7b6e5f4d21')


def uid(*k): return str(uuid.uuid5(NS, '/'.join(map(str, k))))


def f(v): return ('%.4f' % v).rstrip('0').rstrip('.')


# ---------------------------------------------------------------------------------------------
# Symbols: name -> (reference, footprint, description, [(number, name, type, side, slot)])
# side: L / R / T (top) / B (bottom); slot counts 2.54 mm steps from the top (L/R) or from the
# centre (T/B). The last field is the body half-width.
# ---------------------------------------------------------------------------------------------
SYMBOLS = {
    'CH32L103F8U6': ('U', 'Package_DFN_QFN:UQFN-20-1EP_3x3mm_P0.4mm_EP1.85x1.85mm',
                     'WCH CH32L103F8U6, RV32IMAC low-power MCU, 64K flash / 20K RAM, QFN-20 3x3',
                     [('1', 'PA0', 'bidirectional', 'L', 0), ('2', 'PA1', 'bidirectional', 'L', 1),
                      ('3', 'PA2', 'bidirectional', 'L', 2), ('4', 'PA3', 'bidirectional', 'L', 3),
                      ('5', 'PA4', 'bidirectional', 'L', 4), ('6', 'PA5', 'bidirectional', 'L', 5),
                      ('20', 'PA6', 'bidirectional', 'L', 6), ('7', 'PA7', 'bidirectional', 'L', 7),
                      ('14', 'PA8', 'bidirectional', 'L', 8), ('15', 'PA9', 'bidirectional', 'L', 9),
                      ('18', 'PA10/PB7', 'bidirectional', 'L', 10),
                      ('8', 'PB0', 'bidirectional', 'R', 0), ('9', 'PB1/PB10', 'bidirectional', 'R', 1),
                      ('10', 'PB11', 'bidirectional', 'R', 2), ('11', 'PB6/PB13', 'bidirectional', 'R', 3),
                      ('12', 'PB14', 'bidirectional', 'R', 4), ('13', 'PB15', 'bidirectional', 'R', 5),
                      ('17', 'PA13/PA11/SWDIO', 'bidirectional', 'R', 7),
                      ('16', 'PA14/PA12/SWCLK', 'bidirectional', 'R', 8),
                      ('19', 'VDD', 'power_in', 'T', 0), ('21', 'VSS', 'power_in', 'B', 0)], 12.7),
    'IM66D130M': ('MK', 'dbfob:Infineon_IM66D130M_LGA-5_3x2mm',
                  'Infineon IM66D130MV01 PDM MEMS microphone, 130 dB SPL AOP, bottom port, 3 x 2 mm',
                  [('5', 'VDD', 'power_in', 'L', 0), ('4', 'CLK', 'input', 'L', 1), ('2', 'LR', 'input', 'L', 2),
                   ('1', 'DATA', 'output', 'R', 0), ('3', 'GND', 'power_in', 'B', 0)], 7.62),
    'NT3H2111W0FHK': ('U', 'dbfob:NXP_XQFN-8_1.6x1.6mm_P0.5mm',
                      'NTAG I2C plus 1k, NFC Forum Type 2 tag with I2C and field detect, XQFN8',
                      [('1', 'LA', 'passive', 'L', 0), ('8', 'LB', 'passive', 'L', 2),
                       ('6', 'VCC', 'power_in', 'R', 0), ('7', 'VOUT', 'power_out', 'R', 1),
                       ('5', 'SDA', 'bidirectional', 'R', 2), ('3', 'SCL', 'input', 'R', 3),
                       ('4', 'FD', 'open_collector', 'R', 4), ('2', 'VSS', 'power_in', 'B', 0)], 7.62),
}


def symbol(name, ref, fp, descr, pins, w):
    rows = max(5, 1 + max(slot for _, _, _, side, slot in pins if side in 'LR') + 1)
    top = 2.54 * 2
    body_bottom = top - 2.54 * rows
    out = [f'\t(symbol "{name}"', '\t\t(pin_names (offset 1.016))', '\t\t(exclude_from_sim no)',
           '\t\t(in_bom yes)', '\t\t(on_board yes)']
    props = [('Reference', ref, -w, top + 1.27), ('Value', name, 0, body_bottom - 3.81),
             ('Footprint', fp, 0, 0), ('Datasheet', '', 0, 0), ('Description', descr, 0, 0)]
    for k, v, x, y in props:
        hide = '' if k in ('Reference', 'Value') else ' (hide yes)'
        out.append(f'\t\t(property "{k}" "{v}" (at {f(x)} {f(y)} 0) (effects (font (size 1.27 1.27)){hide}))')
    out.append(f'\t\t(symbol "{name}_0_1"')
    out.append(f'\t\t\t(rectangle (start {f(-w)} {f(top)}) (end {f(w)} {f(body_bottom)}) '
               f'(stroke (width 0.254) (type default)) (fill (type background)))')
    out.append('\t\t)')
    out.append(f'\t\t(symbol "{name}_1_1"')
    for num, pname, typ, side, slot in pins:
        if side == 'L': x, y, a = -w - 2.54, top - 2.54 * (slot + 1), 0
        elif side == 'R': x, y, a = w + 2.54, top - 2.54 * (slot + 1), 180
        elif side == 'T': x, y, a = 2.54 * slot, top + 2.54, 270
        else: x, y, a = 2.54 * slot, body_bottom - 2.54, 90
        out.append(f'\t\t\t(pin {typ} line\n\t\t\t\t(at {f(x)} {f(y)} {a})\n\t\t\t\t(length 2.54)\n'
                   f'\t\t\t\t(name "{pname}" (effects (font (size 1.27 1.27))))\n'
                   f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n\t\t\t)')
    out.append('\t\t)')
    out.append('\t\t(embedded_fonts no)')
    out.append('\t)')
    return '\n'.join(out)


# ---------------------------------------------------------------------------------------------
# Footprints
# ---------------------------------------------------------------------------------------------
def fp_text(kind, val, x, y, layer, hide=False):
    h = ' (hide yes)' if hide else ''
    return (f'\t(property "{kind}" "{val}" (at {f(x)} {f(y)} 0) (layer "{layer}"){h} '
            f'(uuid "{uid("fpprop", val, kind)}") (effects (font (size 0.8 0.8) (thickness 0.12))))')


def rect(x0, y0, x1, y1, layer, width, name):
    return (f'\t(fp_rect (start {f(x0)} {f(y0)}) (end {f(x1)} {f(y1)}) (stroke (width {f(width)}) '
            f'(type solid)) (fill no) (layer "{layer}") (uuid "{uid(name, layer, x0, y0)}"))')


def line(x0, y0, x1, y1, layer, width, name):
    return (f'\t(fp_line (start {f(x0)} {f(y0)}) (end {f(x1)} {f(y1)}) (stroke (width {f(width)}) '
            f'(type solid)) (layer "{layer}") (uuid "{uid(name, layer, x0, y0, x1, y1)}"))')


def smd(num, x, y, w, h, name, shape='roundrect'):
    rr = ' (roundrect_rratio 0.25)' if shape == 'roundrect' else ''
    return (f'\t(pad "{num}" smd {shape} (at {f(x)} {f(y)}) (size {f(w)} {f(h)}) '
            f'(layers "F.Cu" "F.Paste" "F.Mask"){rr} (uuid "{uid(name, "pad", num, x, y)}"))')


def footprint(name, descr, attr, items):
    return '\n'.join([f'(footprint "{name}"', '\t(version 20240108)', '\t(generator "dbfob_gen_lib")',
                      '\t(layer "F.Cu")', f'\t(descr "{descr}")', f'\t(attr {attr})'] + items + [')']) + '\n'


def xqfn8():
    """SOT902-3. Terminals end at the body edge (0.8 mm from centre) and run L = 0.4 inward; the
    land adds 0.2 mm of toe outside the body and keeps the inner end of the terminal."""
    name = 'NXP_XQFN-8_1.6x1.6mm_P0.5mm'
    toe, heel, pw = 0.2, 0.0, 0.25            # mm beyond the terminal; pad width over b = 0.20
    inner, outer = 0.4 - heel, 0.8 + toe      # distance from centre along the terminal
    ln, mid = outer - inner, (outer + inner) / 2
    pads = []
    for num, y in (('1', -0.5), ('2', 0.0), ('3', 0.5)):       # left column, top to bottom
        pads.append(smd(num, -mid, y, ln, pw, name))
    pads.append(smd('4', 0.0, mid, pw, ln, name))               # bottom centre
    for num, y in (('5', 0.5), ('6', 0.0), ('7', -0.5)):       # right column, bottom to top
        pads.append(smd(num, mid, y, ln, pw, name))
    pads.append(smd('8', 0.0, -mid, pw, ln, name))              # top centre
    items = [fp_text('Reference', 'REF**', 0, -1.9, 'F.SilkS'), fp_text('Value', name, 0, 1.9, 'F.Fab'),
             rect(-0.8, -0.8, 0.8, 0.8, 'F.Fab', 0.1, name),
             rect(-1.25, -1.25, 1.25, 1.25, 'F.CrtYd', 0.05, name),
             # pin-1 mark outside the top-left corner, clear of the pads
             f'\t(fp_circle (center -1.15 -1.0) (end -1.05 -1.0) (stroke (width 0.1) (type solid)) '
             f'(fill yes) (layer "F.SilkS") (uuid "{uid(name, "pin1")}"))'] + pads
    return name, footprint(name, 'NXP SOT902-3 XQFN8 1.6 x 1.6 mm, 0.5 mm pitch (NTAG I2C plus)', 'smd', items)


def im66d130m():
    """Fig. 15, top view: pin 1 lower left, the port on the right."""
    name = 'Infineon_IM66D130M_LGA-5_3x2mm'
    px = 0.54                                  # ring and port centre
    pads = [smd(n, x, y, 0.42, 0.625, name, 'rect') for n, x, y in
            (('1', -1.15, 0.555), ('2', -0.55, 0.555), ('4', -0.55, -0.555), ('5', -1.15, -0.555))]
    # GND ring: outer 1.4 as fig. 15, inner 1.0 instead of 0.76 so the 0.5 mm port keeps 0.25 mm
    # hole-to-copper. The mic's own ring is 0.8 / 1.3, so the seal band is still 1.0..1.3.
    rm, rw = (1.4 + 1.0) / 4, (1.4 - 1.0) / 2
    pads.append(f'\t(pad "3" smd custom (at {f(px)} {f(-rm)}) (size {f(rw)} {f(rw)}) (layers "F.Cu" "F.Mask") '
                f'(zone_connect 0) (options (clearance outline) (anchor circle)) (primitives (gr_circle '
                f'(center 0 {f(rm)}) (end {f(rm)} {f(rm)}) (width {f(rw)}) (fill no))) (uuid "{uid(name, "ring")}"))')
    # paste: three ring segments with 0.1 mm vents at 60, 180 and 300 degrees, as fig. 15 but
    # inside the narrower copper ring
    ri, ro, vent = 0.52, 0.68, 0.1
    for k, (a0, a1) in enumerate(((60, 180), (180, 300), (300, 420))):
        da = math.degrees(vent / 2 / ri)
        arc = lambda r, a, b: [(r * math.cos(math.radians(t)), -r * math.sin(math.radians(t)))
                               for t in [a + (b - a) * i / 12 for i in range(13)]]
        pts = arc(ro, a0 + da, a1 - da) + list(reversed(arc(ri, a0 + da, a1 - da)))
        am = math.radians((a0 + a1) / 2)           # anchor on the segment, not over the port
        ax, ay = (ri + ro) / 2 * math.cos(am), -(ri + ro) / 2 * math.sin(am)
        xy = ' '.join(f'(xy {f(x - ax)} {f(y - ay)})' for x, y in pts)
        pads.append(f'\t(pad "" smd custom (at {f(px + ax)} {f(ay)}) (size 0.1 0.1) (layers "F.Paste") (zone_connect 0) '
                    f'(options (clearance outline) (anchor circle)) (primitives (gr_poly (pts {xy}) (width 0) '
                    f'(fill yes))) (uuid "{uid(name, "paste", k)}"))')
    pads.append(f'\t(pad "" np_thru_hole circle (at {f(px)} 0) (size 0.5 0.5) (drill 0.5) (layers "*.Cu" "*.Mask") '
                f'(uuid "{uid(name, "port")}"))')
    items = [fp_text('Reference', 'REF**', 0, -1.9, 'F.SilkS'), fp_text('Value', name, 0, 1.9, 'F.Fab'),
             rect(-1.5, -1.0, 1.5, 1.0, 'F.Fab', 0.1, name),
             rect(-1.75, -1.25, 1.75, 1.25, 'F.CrtYd', 0.05, name),
             line(-1.6, -1.1, 1.6, -1.1, 'F.SilkS', 0.12, name), line(-1.6, 1.1, 1.6, 1.1, 'F.SilkS', 0.12, name),
             f'\t(fp_circle (center -1.75 0.9) (end -1.65 0.9) (stroke (width 0.1) (type solid)) '
             f'(fill yes) (layer "F.SilkS") (uuid "{uid(name, "pin1")}"))'] + pads
    return name, footprint(name, 'Infineon IM66D130MV01 PG-LLGA-5, 3 x 2 mm, bottom port (datasheet v1.1 fig. 15)',
                           'smd', items)


def pogo4():
    """Four round SMD test pads on 2.54 mm for a pogo clip or pressed-in pins (programming)."""
    name = 'TestPads_1x04_P2.54mm_D1.2mm'
    pads = [smd(str(i + 1), 0, i * 2.54, 1.2, 1.2, name, 'circle') for i in range(4)]
    items = [fp_text('Reference', 'REF**', 0, -1.6, 'F.Fab'), fp_text('Value', name, 0, 9.3, 'F.Fab'),
             rect(-0.85, -0.85, 0.85, 7.62 + 0.85, 'F.CrtYd', 0.05, name)] + pads
    return name, footprint(name, '1 x 4 SMD test pads, 1.2 mm, 2.54 mm pitch (pogo / pressed pins)', 'smd', items)


def bs08():
    name = 'BatteryHolder_MYOUNG_BS-08-B2AA001_CR2032'
    bx0, bx1, by = -13.04, 12.36, 7.85
    items = [fp_text('Reference', 'REF**', 0, -9.0, 'F.SilkS'), fp_text('Value', name, 0, 9.0, 'F.Fab'),
             rect(bx0, -by, bx1, by, 'F.Fab', 0.1, name),
             rect(bx0 - 0.25, -by - 0.25, max(bx1, 11.02 + 1.9) + 0.25, by + 0.25, 'F.CrtYd', 0.05, name),
             f'\t(fp_circle (center -0.6 0) (end 9.4 0) (stroke (width 0.1) (type dash)) (fill no) '
             f'(layer "F.Fab") (uuid "{uid(name, "cell")}"))',
             line(bx0, -by, bx1, -by, 'F.SilkS', 0.12, name), line(bx0, by, bx1, by, 'F.SilkS', 0.12, name),
             # + mark beside pad 1
             line(8.4, -5.6, 9.6, -5.6, 'F.SilkS', 0.15, name + '+'), line(9.0, -6.2, 9.0, -5.0, 'F.SilkS', 0.15, name + '+'),
             smd('1', 11.02, 0, 3.8, 3.8, name, 'rect'), smd('2', -10.98, 0, 4.3, 2.8, name, 'rect')]
    return name, footprint(name, 'MYOUNG BS-08-B2AA001 SMD CR2032 holder with its own - spring (LCSC C964777)',
                           'smd', items)


def main():
    sym = ['(kicad_symbol_lib', '\t(version 20251024)', '\t(generator "dbfob_gen_lib")', '\t(generator_version "10.0")']
    for name, (ref, fp, descr, pins, w) in SYMBOLS.items():
        sym.append(symbol(name, ref, fp, descr, pins, w))
    sym.append(')')
    open(os.path.join(HERE, 'dbfob.kicad_sym'), 'w').write('\n'.join(sym) + '\n')
    d = os.path.join(HERE, 'dbfob.pretty')
    os.makedirs(d, exist_ok=True)
    for gen in (xqfn8, im66d130m, pogo4, bs08):
        name, text = gen()
        open(os.path.join(d, name + '.kicad_mod'), 'w').write(text)
    print('wrote', os.path.join(HERE, 'dbfob.kicad_sym'), 'and', d)


if __name__ == '__main__':
    main()
