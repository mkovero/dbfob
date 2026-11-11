"""The stick's NFC antenna block, shared by hardware/b1 and hardware/nfc-test so the two are identical.

Both boards are ordered together, so the test board cannot steer B1's layout. It measures B1's
antenna instead, and the trim value found on it goes onto B1's C1/C2. For that to hold, every
piece of copper that sets the tuning is defined here once, together with the board outline and
the cell beside the coil. Board mm, x along the stick from the mic tip (x = 0), y across it
(0..W, y down); parts on F.Cu, the AAA cell on the back:

  - the coil fills the tip, 23 x 9.3 mm: a 9-turn rectangular spiral of LA track on F.Cu, corners
    chamfered where the board's rounded tip needs it. Its outer end leaves on the right side
    straight to the tag; its inner end meets LB through net tie NT1 inside the coil;
  - LB drops through VI, crosses under the right-hand turns on B.Cu and comes back up at VO;
  - the tag U1 (NT3H2111) sits just past the coil with trim pads C1/C2 bridging the LA and LB
    lanes in front of it, and C3 (tag VCC decoupling) beside it;
  - the cell lies on the back between two MYOUNG MY-AAA-07 spring contacts, its near end about
    1.4 mm past the coil's end. Its steel can shifts the tuning, which is why the test board
    carries it too.

Inductance by NXP AN11276's rectangular-coil formula (N^1.8 fit): about 2.25 uH in air against
2.75 uH for 13.56 MHz with the tag's 50 pF. Deliberately short: the cell, its contacts and a
phone lower the resonance less than a parallel trim cap can, and a trim cap can only pull it down.

Same-net copper is not clearance-checked by DRC, so the geometry is made right by construction
and check_coil() asserts the gap between turns, and between the vias and the turns.
"""
import math

W, L = 10.5, 93.0            # the stick's board: width (y) and length (x), tip at x = 0; past the cell
                             # contacts B1 has its keyring hole, then the Tag-Connect footprint
TURNS = 9
TW = 0.15                    # coil track width
PITCH = 0.30                 # 0.15 mm gap
GAP_MIN = PITCH - TW - 0.001
D0 = 0.6                     # outer turn centre line from the tip and side edges: 0.525 mm copper-edge
XE = 23.6                    # outer turn's right side (the end towards the cell)
C0 = 0.3                     # corner chamfer, outer turn: clears the 1 mm corner radius at the tip
DC = (2 - math.sqrt(2)) * PITCH   # chamfer shrink per turn that keeps the diagonal pitch = PITCH
LB_Y, LA_Y = 4.0, 5.55       # the two lanes to the tag; C1/C2 (0603 on end, 1.55 mm pad pitch) bridge them
VIA, DRILL = 0.6, 0.3
RN = XE - TURNS * PITCH      # the final inward segment of the spiral
NT1_X = RN - 1.0             # net tie inside the coil, pad 1 (coil) at x + 0.5, clear of the next turn
VI = (NT1_X - 1.2, LB_Y)     # LB down to B.Cu inside the coil
VO = (XE + 0.55, LB_Y)       # and back up past the outer turn
CELL_X = 50.45               # cell centre: the contact pair's courtyard (+-25.45) starts at x = 25.0

# ref: (x, y, rotation, back side). U1 at 90 has LB (pin 8) facing the coil and LA (pin 1) at the
# bottom-left corner. BT1 is the pair of cell contacts on the back, + towards the far end.
PLACE = {
    'NT1': (NT1_X, LB_Y, 180, False),  # pad 1 (LA, coil) at +x, pad 2 (LB) at -x
    'C1': (25.2, (LB_Y + LA_Y) / 2, 90, False),   # pad 2 (LB) up on the LB lane, pad 1 (LA) down
    'C2': (26.8, (LB_Y + LA_Y) / 2, 90, False),
    'U1': (28.9, LB_Y, 90, False),
    'C3': (28.9, 1.9, 0, False),      # tag VCC decoupling, over pin 6 (top)
    'BT1': (CELL_X, W / 2, 180, True),
}
# hand routes: (net, layer, [points]); a point may be 'REF.pad' for that pad's centre
HAND = [
    ('/LA', 'F', [(XE, LA_Y), 'C1.1', 'C2.1', (28.4, LA_Y), 'U1.1']),
    ('/LB', 'F', ['NT1.2', VI]),
    ('/LB', 'B', [VI, VO]),
    ('/LB', 'F', [VO, 'C1.2', 'C2.2', 'U1.8']),
]
VIAS = [('/LB', VI), ('/LB', VO)]
# B.Cu under the turns: no router tracks or vias, apart from the band at the coil's cell end,
# where the mic's nets and LB cross under the right-hand turns.
BAND = D0 + TURNS * PITCH + 0.1
KEEPOUTS = [(0, 0, RN - 0.8, BAND), (0, W - BAND, RN - 0.8, W), (0, 0, BAND, W)]


def coil():
    pts = [(XE, LA_Y)]
    for k in range(TURNS):
        r, t, l, b = XE - k * PITCH, D0 + k * PITCH, D0 + k * PITCH, W - D0 - k * PITCH
        rn, c = r - PITCH, max(0.0, C0 - k * DC)
        pts += [(r, t + c), (r - c, t), (l + c, t), (l, t + c), (l, b - c), (l + c, b), (rn - c, b), (rn, b - c)]
    pts += [(RN, LB_Y), (NT1_X + 0.5, LB_Y)]
    out = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, out[-1]) > 1e-9: out.append(p)     # drop the zero-length chamfers
    return out


def seg_dist(a, b, c, d):
    """Minimum distance between segments ab and cd (2D)."""
    def pt_seg(p, q, r):
        qx, qy = r[0] - q[0], r[1] - q[1]
        n = qx * qx + qy * qy
        t = 0 if n == 0 else max(0, min(1, ((p[0] - q[0]) * qx + (p[1] - q[1]) * qy) / n))
        return math.dist(p, (q[0] + t * qx, q[1] + t * qy))
    def cross(o, p, q): return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b, c) * cross(a, b, d) < 0) and (cross(c, d, a) * cross(c, d, b) < 0): return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


def check_coil(pts):
    """Turn-to-turn gap, and each via's gap to every turn (both vias are LB, the coil is LA)."""
    segs = list(zip(pts, pts[1:]))
    # (segments under three apart along the path are one side turning a corner)
    gap = min(seg_dist(*segs[i], *segs[j]) for i in range(len(segs)) for j in range(i + 3, len(segs))) - TW
    assert gap >= GAP_MIN, f'coil gap {gap:.3f} mm'
    for name, v in (('VO', VO), ('VI', VI)):
        g = min(seg_dist(v, v, *s) for s in segs) - TW / 2 - VIA / 2
        assert g >= GAP_MIN, f'{name} to coil {g:.3f} mm'
        gap = min(gap, g)
    return gap


def inductance(a0, b0, n, w=TW, g=PITCH - TW, t=0.035):
    """NXP AN11276, rectangular coil, outer dimensions a0 x b0 in mm; henries."""
    a0, b0, w, g, t = (v / 1e3 for v in (a0, b0, w, g, t))
    aa, bb = a0 - n * (g + w), b0 - n * (g + w)
    d, s = 2 * (t + w) / math.pi, math.hypot(aa, bb)
    x1 = aa * math.log(2 * aa * bb / (d * (aa + s))); x2 = bb * math.log(2 * aa * bb / (d * (bb + s)))
    return 4e-7 * (x1 + x2 - 2 * (aa + bb - s) + (aa + bb) / 4) * n ** 1.8


def outer():
    return XE - D0 + TW, W - 2 * D0 + TW


def summary(gap):
    a0, b0 = outer()
    return (f'coil: {TURNS} turns {TW}/{PITCH - TW:.2f}, outer {a0:.2f} x {b0:.2f} mm, min gap {gap:.3f} mm, '
            f'L about {inductance(a0, b0, TURNS) * 1e6:.2f} uH in air (AN11276)')


def outline(board, mm, corner=1.0):
    """The stick: W x L with rounded corners."""
    import pcbnew
    r, k = corner, corner * (1 - 0.5 ** 0.5)
    for a, b in [((r, 0), (L - r, 0)), ((L, r), (L, W - r)), ((L - r, W), (r, W)), ((0, W - r), (0, r))]:
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(*a)); s.SetEnd(mm(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.05))
        board.Add(s)
    for a, m, b in [((0, r), (k, k), (r, 0)), ((L - r, 0), (L - k, k), (L, r)),
                    ((L, W - r), (L - k, W - k), (L - r, W)), ((r, W), (k, W - k), (0, W - r))]:
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(mm(*a), mm(*m), mm(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.05))
        board.Add(s)


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
            track(board, nets[net], layer, point(a), point(b), 0.2)
    return gap
