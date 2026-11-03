"""B1's NFC antenna block, shared by hardware/b1 and hardware/nfc-test so the two are identical.

Both boards are ordered together, so the test board cannot steer B1's layout. It measures B1's
antenna instead, and the trim value found on it goes onto B1's C1/C2. For that to hold, every
piece of copper that sets the tuning is defined here once, in board mm (top-left corner of the
30 x 26 mm antenna area, y down):

  - the coil: a 6-turn rectangular spiral of LA track on F.Cu, chamfered at the corners;
  - its outer end drops through VO to B.Cu, crosses under the turns and comes back up at VI;
  - its inner end meets LB through net tie NT1;
  - the tag U1 (NT3H2111) and trim pads C1/C2 sit just inside the bottom turns, with C3 (tag
    VCC decoupling) beside U1;
  - the CR2032 holder BT1 sits on the back, under the coil.

Inductance by NXP AN11276's rectangular-coil formula (N^1.8 fit): about 2.1 uH in air against
2.75 uH for 13.56 MHz with the tag's 50 pF. Deliberately short: ferrite raises L, the cell lowers
it, and a parallel trim cap can only pull the resonance down.

Same-net copper is not clearance-checked by DRC, so the geometry is made right by construction
and check_coil() asserts the 0.2 mm gap between turns, and between the vias and the turns.
"""
import math

W, H_LOOP = 30.0, 26.0       # the antenna area: B1's whole board, the test board's top part
TURNS = 6
TW = 0.25                    # coil track width
PITCH = 0.45                 # 0.2 mm gap
D0 = 0.65                    # outer turn centre line from the left, top and right edges
HB0 = 25.0                   # outer turn's bottom side: 1 mm up, so VO fits inside B1's edge
CT0 = 2.45                   # top-corner chamfer, outer turn: clears the 3 mm edge radius
CB0 = 1.7                    # bottom-corner chamfer, outer turn: 0.5 mm from B1's corner arcs
DC = (2 - math.sqrt(2)) * PITCH   # chamfer shrink per turn that keeps the diagonal pitch = PITCH
XS, XE = 17.6, 15.6          # outer end (LA, to VO) and inner end (to NT1)
VIA, DRILL = 0.6, 0.3
VO = (XS, 25.2)              # outer end down to B.Cu: 0.5 mm from the edge, 0.225 mm from turn 2
VI = (XS, 21.3)              # and back up inside the loop

# ref: (x, y, rotation, back side). U1 at 270 has LA (pin 1) top right and LB (pin 8) right, so
# both leave to the right in two lanes, LB at x = XE and LA outside it at x = XS, with the trim
# caps bridging the lanes. VSS and SCL face up, FD left, SDA and VCC down.
PLACE = {
    'BT1': (14.4, 14.0, 0, True),      # cell centre (footprint x -0.6, mirrored) at (15, 14)
    'NT1': (XE, 21.6, 90, False),      # pad 1 (LA, coil) below at y 22.1, pad 2 (LB) above at 21.1
    'U1': (13.8, 18.0, 270, False),
    'C1': (16.6, 20.0, 180, False),    # pad 1 (LA) right on the LA lane, pad 2 (LB) left on LB's
    'C2': (16.6, 18.5, 180, False),
    'C3': (13.8, 20.75, 270, False),   # tag VCC decoupling: VCC pad up, under U1's VCC pin
}
INNER_END = (XE, HB0 - TURNS * PITCH)
LANE_Y = 16.6                          # LA's lane over the top of U1
# hand routes: (net, layer, [points]); a point may be 'REF.pad' for that pad's centre
HAND = [
    ('/LA', 'F', [(XS, HB0), VO]),
    ('/LA', 'B', [VO, VI]),
    ('/LA', 'F', ['U1.1', (14.3, LANE_Y), (XS, LANE_Y), 'C2.1', 'C1.1', VI]),
    ('/LA', 'F', [INNER_END, 'NT1.1']),
    ('/LB', 'F', ['U1.8', (XE, 18.0), 'C2.2', 'C1.2', 'NT1.2']),
]
VIAS = [('/LA', VO), ('/LA', VI)]
# B.Cu under the coil: no router tracks or vias (the VO-VI crossover gap excepted). The test
# board leaves the bottom band open, as its tail is reached across it.
BAND = 3.3
# (the side bands stop short of the holder's pads, which reach under the coil)
KEEPOUT_SIDES = [(0, 0, W, BAND), (0, 0, BAND, 11.0), (0, 17.0, BAND, H_LOOP),
                 (W - BAND, 0, W, 11.0), (W - BAND, 17.0, W, H_LOOP)]
KEEPOUT_BOTTOM = [(0, 22.0, XS - 0.45, H_LOOP), (XS + 0.45, 22.0, W, H_LOOP)]


def coil():
    pts = [(XS, HB0)]
    for k in range(TURNS):
        d, ct, cb = D0 + k * PITCH, CT0 - k * DC, CB0 - k * DC
        hb, hb1 = HB0 - k * PITCH, HB0 - (k + 1) * PITCH
        pts += [(d + cb, hb), (d, hb - cb), (d, d + ct), (d + ct, d), (W - d - ct, d), (W - d, d + ct),
                (W - d, hb1 - cb), (W - d - cb, hb1)]
    pts.append(INNER_END)
    return pts


def seg_dist(a, b, c, d):
    """Minimum distance between segments ab and cd (2D)."""
    def pt_seg(p, q, r):
        qx, qy = r[0] - q[0], r[1] - q[1]
        L = qx * qx + qy * qy
        t = 0 if L == 0 else max(0, min(1, ((p[0] - q[0]) * qx + (p[1] - q[1]) * qy) / L))
        return math.dist(p, (q[0] + t * qx, q[1] + t * qy))
    def cross(o, p, q): return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b, c) * cross(a, b, d) < 0) and (cross(c, d, a) * cross(c, d, b) < 0): return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


def check_coil(pts):
    """Turn-to-turn gap, and each via's gap to every turn it is not the end of."""
    segs = list(zip(pts, pts[1:]))
    # (segments under four apart along the path are the same turn turning a corner)
    gap = min(seg_dist(*segs[i], *segs[j]) for i in range(len(segs)) for j in range(i + 4, len(segs))) - TW
    assert gap >= 0.199, f'coil gap {gap:.3f} mm'
    for name, v, skip in (('VO', VO, 1), ('VI', VI, 0)):
        g = min(seg_dist(v, v, *s) for s in segs[skip:]) - TW / 2 - VIA / 2
        assert g >= 0.199, f'{name} to coil {g:.3f} mm'
        gap = min(gap, g)
    return gap


def inductance(a0, b0, n, w=TW, g=PITCH - TW, t=0.035):
    """NXP AN11276, rectangular coil, outer dimensions a0 x b0 in mm; henries."""
    a0, b0, w, g, t = (v / 1e3 for v in (a0, b0, w, g, t))
    aa, bb = a0 - n * (g + w), b0 - n * (g + w)
    d, s = 2 * (t + w) / math.pi, math.hypot(aa, bb)
    x1 = aa * math.log(2 * aa * bb / (d * (aa + s))); x2 = bb * math.log(2 * aa * bb / (d * (bb + s)))
    return 4e-7 * (x1 + x2 - 2 * (aa + bb - s) + (aa + bb) / 4) * n ** 1.8


def summary(gap):
    a0, b0 = W - 2 * D0 + TW, HB0 - D0 + TW
    return (f'coil: {TURNS} turns, outer {a0:.2f} x {b0:.2f} mm, min gap {gap:.3f} mm, '
            f'L about {inductance(a0, b0, TURNS) * 1e6:.2f} uH in air (AN11276)')


def draw(board, nets, fps, mm, track, via):
    """Draw the coil, the vias and the hand routes on an already placed board."""
    import pcbnew
    pts = coil()
    gap = check_coil(pts)
    for a, b in zip(pts, pts[1:]):
        track(board, nets['/LA'], pcbnew.F_Cu, mm(*a), mm(*b), TW)
    for net, (x, y) in VIAS:
        via(board, nets[net], x, y)

    def point(p):
        if isinstance(p, str):
            ref, pad = p.split('.')
            return next(q for q in fps[ref].Pads() if q.GetNumber() == pad).GetPosition()
        return mm(*p)
    for net, side, path in HAND:
        layer = pcbnew.F_Cu if side == 'F' else pcbnew.B_Cu
        for a, b in zip(path, path[1:]):
            track(board, nets[net], layer, point(a), point(b), TW)
    return gap
