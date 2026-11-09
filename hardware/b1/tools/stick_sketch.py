"""Size sketch: B1 as drafted (CR2032) next to the two stick options, to scale (1 SVG unit = 1 mm).

Writes docs/b1-stick-sketch.svg. A sketch for deciding the shape, not a layout: part positions
are indicative, case sizes assume rev A's SLA walls (1.6 mm wall, 0.15 mm board gap, 1.2 mm
floor and top), and the stick coil's inductance comes from the same AN11276 formula as B1's
antenna. Print at 100 % for real size.

    python3 hardware/b1/tools/stick_sketch.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'lib'))
import antenna  # noqa: E402

OUT = os.path.join(HERE, '..', '..', '..', 'docs', 'b1-stick-sketch.svg')
WALL, GAP, SKIN = 1.6, 0.15, 1.2          # rev A SLA case: wall, board-to-wall, floor/top
CASE = WALL + GAP

# AAA stick: one board face carries every part (the coil zone at the tip, the rest under the
# cell); the cell lies on the other face between two MY-AAA-07 spring contacts.
S_W, S_L = 10.5, 74.0                     # board
S_COIL = (0.25, 0.25, 22.0, 10.0)         # coil zone: x, y, length, width (outer turn)
S_TW, S_PITCH, S_TURNS = 0.15, 0.30, 9
S_CELL = (26.0, 44.5, 10.5)               # x start, length, diameter (Energizer L92)
S_LANYARD = 5.0                           # case past the board's far end, for a lanyard hole
S_PARTS_H, S_BOARD_T = 1.5, 1.0           # tallest part (button), board thickness

# CR1632 stick: cell under the far end of the board, coil zone at the tip, as on B1.
C_W, C_L, C_CELL_D = 18.0, 40.0, 16.0

INK, DIM, COIL, CELL, PART, MIC = '#222', '#888', '#c47a00', '#3a6fb0', '#555', '#c0392b'


def rect(x, y, w, h, stroke=INK, fill='none', sw=0.2, rx=0, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def circle(x, y, r, stroke=INK, fill='none', sw=0.2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'


def text(x, y, s, size=2.2, anchor='start', fill=INK, weight='normal'):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" '
            f'font-family="sans-serif" font-weight="{weight}">{s}</text>')


def poly(pts, stroke, sw):
    p = ' '.join(f'{x:.2f},{y:.2f}' for x, y in pts)
    return f'<polyline points="{p}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>'


def rect_coil(x, y, l, w, turns, pitch, tw):
    out = []
    for k in range(turns):
        d = k * pitch
        out.append(rect(x + d, y + d, l - 2 * d, w - 2 * d, stroke=COIL, sw=tw))
    return out


def case_outline(x, y, l, w, extra_l=0.0):
    return rect(x - CASE, y - CASE, l + 2 * CASE + extra_l, w + 2 * CASE, stroke=DIM, sw=0.3, rx=2.5)


def b1(ox, oy):
    """B1 as drafted: 30 x 26 board, coil round the edge, CR2032 under the board."""
    W, H = antenna.W, antenna.H_LOOP
    s = [case_outline(ox, oy, W, H), rect(ox, oy, W, H, rx=3)]
    s.append(poly([(ox + x, oy + y) for x, y in antenna.coil()], COIL, antenna.TW))
    s.append(circle(ox + 15, oy + 14, 10, stroke=CELL, dash='1,0.6'))
    s.append(rect(ox + 13.5, oy + 9.3, 3, 3, stroke=PART, fill='#ddd'))              # MCU
    s.append(rect(ox + 20.5, oy + 3.3, 2, 3, stroke=PART, fill='#ddd'))              # mic
    s.append(circle(ox + 21.5, oy + 4.26, 0.35, stroke=MIC, fill=MIC))
    s.append(rect(ox + 4.75, oy + 3.3, 5.1, 5.1, stroke=PART, fill='#eee'))          # button
    cw, ch = W + 2 * CASE, H + 2 * CASE
    s.append(text(ox + W / 2, oy - CASE - 2.5, 'B1 as drafted: CR2032', 2.8, 'middle', weight='bold'))
    s.append(text(ox + W / 2, oy + H + CASE + 4, f'case about {cw:.1f} × {ch:.1f} × 11 mm', 2.4, 'middle'))
    s.append(text(ox + W / 2, oy + H + CASE + 7, 'coil 6 turns 0.25/0.2, ~2.2 µH', 2.2, 'middle', DIM))
    return s


def cr1632(ox, oy):
    s = [case_outline(ox, oy, C_L, C_W), rect(ox, oy, C_L, C_W, rx=2)]
    s += rect_coil(ox + 0.25, oy + 0.25, 20.0, C_W - 0.5, 6, 0.45, 0.25)
    s.append(circle(ox + C_L - C_CELL_D / 2 - 1.5, oy + C_W / 2, C_CELL_D / 2, stroke=CELL, dash='1,0.6'))
    s.append(rect(ox + 3.5, oy + C_W / 2 - 1, 3, 2, stroke=PART, fill='#ddd'))
    s.append(circle(ox + 4.0, oy + C_W / 2, 0.35, stroke=MIC, fill=MIC))
    cw, ch = C_L + 2 * CASE, C_W + 2 * CASE
    s.append(text(ox + C_L / 2, oy - CASE - 2.5, 'Option B: CR1632 stick', 2.8, 'middle', weight='bold'))
    s.append(text(ox + C_L / 2, oy + C_W + CASE + 4, f'case about {cw:.0f} × {ch:.0f} × 9 mm, ~130 mAh', 2.4, 'middle'))
    s.append(text(ox + C_L / 2, oy + C_W + CASE + 7, 'coil at the tip, cell under the far end', 2.2, 'middle', DIM))
    return s


def aaa(ox, oy):
    s = [case_outline(ox, oy, S_L, S_W, S_LANYARD), rect(ox, oy, S_L, S_W, rx=1)]
    x, y, l, w = S_COIL
    s += rect_coil(ox + x, oy + y, l, w, S_TURNS, S_PITCH, S_TW)
    cx, cl, cd = S_CELL
    s.append(rect(ox + cx, oy + (S_W - cd) / 2, cl, cd, stroke=CELL, rx=1, dash='1,0.6'))
    for ex in (cx - 2.0, cx + cl):                                                   # spring contacts
        s.append(rect(ox + ex, oy + S_W / 2 - 3.2, 2.0, 6.35, stroke=CELL, sw=0.15, dash='0.5,0.4'))
    mid = S_W / 2
    s.append(rect(ox + 3.4, oy + mid - 1, 3, 2, stroke=PART, fill='#ddd'))          # MK1 inside the coil
    s.append(circle(ox + 3.9, oy + mid, 0.35, stroke=MIC, fill=MIC))
    s.append(rect(ox + 9.0, oy + mid - 0.8, 1.6, 1.6, stroke=PART, fill='#ddd'))    # tag
    s.append(rect(ox + 13.0, oy + mid - 1.6, 1.6, 0.8, stroke=PART, fill='#eee'))   # trim caps
    s.append(rect(ox + 13.0, oy + mid + 0.8, 1.6, 0.8, stroke=PART, fill='#eee'))
    s.append(rect(ox + 26.0, oy + mid - 1.5, 3, 3, stroke=PART, fill='#ddd'))        # MCU
    s.append(rect(ox + 32.0, oy + mid - 1.45, 1.6, 2.9, stroke=PART, fill='#ddd'))   # TLV61220
    s.append(rect(ox + 35.0, oy + mid - 0.8, 2.0, 1.6, stroke=PART, fill='#eee'))    # 4.7 uH
    for k in range(4):                                                                 # LEDs
        s.append(rect(ox + 41.0 + 3 * k, oy + mid - 0.4, 1.6, 0.8, stroke=PART, fill='#ffd27f'))
    s.append(rect(ox + 54.0, oy + mid - 2.55, 5.1, 5.1, stroke=PART, fill='#eee'))   # button
    for k in range(5):                                                                 # pogo pads
        s.append(circle(ox + 62.0 + 2.54 * k, oy + mid, 0.6, stroke=PART, fill='#eee'))
    cw, ch = S_L + 2 * CASE + S_LANYARD, S_W + 2 * CASE
    s.append(text(ox + S_L / 2, oy - CASE - 2.5, 'Option C: AAA stick (parts face; cell dashed, on the other face)',
                  2.8, 'middle', weight='bold'))
    th = SKIN + S_PARTS_H + S_BOARD_T + cd + 0.3 + SKIN
    L = antenna.inductance(l, w, S_TURNS, w=S_TW, g=S_PITCH - S_TW) * 1e6
    s.append(text(ox + S_L / 2, oy + S_W + CASE + 4,
                  f'case about {cw:.0f} × {ch:.0f} × {th:.0f} mm, ~1250 mAh (L92)', 2.4, 'middle'))
    s.append(text(ox + S_L / 2, oy + S_W + CASE + 7,
                  f'coil {S_TURNS} turns {S_TW}/{S_PITCH - S_TW:.2f} in {l:.0f} × {w:.0f} mm, ~{L:.1f} µH, mic port at the tip',
                  2.2, 'middle', DIM))
    s.append(text(ox + S_L / 2, oy + S_W + CASE + 10,
                  'MCU, boost, LEDs, button and pads sit under the cell, on the other face', 2.2, 'middle', DIM))
    return s, th


def side(ox, oy, l, layers, label):
    """Edge view: layers bottom-up as (name, thickness, colour)."""
    s, z = [], 0.0
    for name, t, col in layers:
        s.append(rect(ox, oy - z - t, l, t, stroke=col, fill=col, sw=0.15))
        z += t
    s.append(text(ox + l + 2, oy - z / 2 + 0.8, f'{label}: about {z:.0f} mm thick', 2.4))
    return s


def main():
    body = []
    body += b1(10, 14)
    body += cr1632(60, 18)
    s, th = aaa(10, 66)
    body += s
    sy = 103
    body.append(text(10, sy - 4, 'Edge views (case skins, parts, board, cell)', 2.8, weight='bold'))
    body += side(10, sy + 12, 30 + 2 * CASE,
                 [('skin', SKIN, '#ccc'), ('holder + cell', 5.3, '#9fbde0'), ('board', 1.6, '#4a7'),
                  ('parts', 1.5, PART), ('skin', SKIN, '#ccc')], 'B1')
    body += side(10, sy + 32, S_L + 2 * CASE + S_LANYARD,
                 [('skin', SKIN, '#ccc'), ('parts', S_PARTS_H, PART), ('board', S_BOARD_T, '#4a7'),
                  ('cell', S_CELL[2] + 0.3, '#9fbde0'), ('skin', SKIN, '#ccc')], 'AAA stick')
    body.append(text(10, sy + 40, 'Sizes estimated with rev A walls (1.6 mm wall, 1.2 mm skins); parts indicative.',
                     2.2, fill=DIM))
    body.append(text(10, sy + 43, 'Red dot = mic port. 1 unit = 1 mm: print at 100 % for real size.', 2.2, fill=DIM))
    W, H = 130, sy + 47
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">\n'
           f'<rect width="{W}" height="{H}" fill="white"/>\n' + '\n'.join(body) + '\n</svg>\n')
    with open(OUT, 'w') as f:
        f.write(svg)
    print(f'wrote {os.path.relpath(OUT)}; AAA stick about {th:.1f} mm thick')


if __name__ == '__main__':
    main()
