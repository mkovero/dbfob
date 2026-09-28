# dbfob case, rev A - FreeCAD script. Builds the front and back shells around the board from
# board_geometry.json (generated from the KiCad layout), checks the fit, and exports.
#
# Run inside FreeCAD (GUI or freecadcmd). GEOM may be injected before running; otherwise it is
# read from board_geometry.json next to this file. The design and its numbers are in README.md.
#
# Frame: the board's fab frame - x right, y up from the board's bottom-left corner, z = 0 at
# the board's back face. The board occupies z 0..1.6.
import json, os
import FreeCAD as App
import Part

V = App.Vector

if 'GEOM' not in globals():
    GEOM = json.load(open(os.path.join(os.path.dirname(__file__), 'board_geometry.json')))

B = GEOM['board']
BW, BH, BT, BR = B['w'], B['h'], B['t'], B['corner_r']
PARTS = GEOM['parts']

# ---- parameters (README.md "Numbers") ------------------------------------------------------
# 'sla' (resin, +-0.05 mm: tight fits, preloaded gasket) or 'fdm' (0.4 mm nozzle: loose fits)
PROCESS = globals().get('PROCESS', 'sla')
SLA = PROCESS == 'sla'
CL = 0.15 if SLA else 0.3   # board edge to wall
WALL = 1.6          # 4 perimeters at 0.4 mm
FLOOR = 1.2
TOP = 1.2
STANDOFF = 0.4      # back floor below the board: the board rests on a ledge and the gasket ring
LEDGE = 1.5         # width of that ledge inside the board edge
HEADROOM = 0.5      # above the tallest part (BT1 + cell)
TALLEST = max(p['height'] for p in PARTS.values())
Z_BOT = -(STANDOFF + FLOOR)                  # outer back face
Z_SPLIT = BT                                 # shells meet at the board's top face
Z_CEIL = BT + TALLEST + HEADROOM             # inside of the front
Z_TOPF = Z_CEIL + TOP                        # outer front face

# The screw goes through the board's own Ø3.2 hole (H1) at the top end, clamping the board. The
# keyring is at the opposite, bottom end, in the case only, so a hand holding it by the keys
# does not cover the mic port or the LEDs at the top.
SCREW = tuple(PARTS['H1']['center'])
SCREW_CLEAR, SCREW_HEAD, SCREW_HEAD_D = 2.3, 4.2, 0.8   # back is only 1.6 thick here: M2 x 6 button head
SCREW_PILOT, SCREW_DEPTH = 1.7, 4.5          # thread-forming M2 x 6: ~3.6 mm engaged in the front boss
BOSS_D = 6.0                                 # screw boss: clamps the board around H1 from both sides

SCREW_END = 8.0                              # the case extends this far below the board ...
RING_XY = (BW / 2, -4.2)                     # ... to carry the keyring hole
RING_HOLE = 3.6

MIC = next(tuple(h['at']) for h in GEOM['holes'] if h['ref'] == 'MK1')   # board's sound hole
# The case port is a straight hole under the board's sound hole. That is 0.68 mm off centre
# (x = 14.32): the IM69D130's port is off its package centre, and the board is fixed. Centring it
# would need a cavity joining two holes, with the gasket crossing a via - not worth it.
PORT = MIC
MIC_HOLE, MIC_RECESS, MIC_RECESS_D = 1.0, 3.0, 0.4
# Gasket ring around the port: it must clear the tented SWIO via at (15.83, 40.47), whose edge is
# 1.21 mm from the port, so the ring's outer radius is 1.1 mm.
VIA_NEAR_PORT = ((15.83, 40.47), 0.3)
CAV_R, GASKET_WALL = 0.6, 0.5
# SLA: a 0.3 mm crush bead on the gasket stands CRUSH above the ledge, so the board is preloaded
# onto it and the mic port is sealed from the case cavity. FDM layer lines would not seal anyway.
CRUSH = 0.08 if SLA else 0.0

LEDS = ['D1', 'D2', 'D3', 'D4']
WIN_X, WIN_Y = 1.4, 1.0                      # LED window
TUBE_X, TUBE_Y, TUBE_GAP = 2.6, 2.2, 0.2     # light tube, stops TUBE_GAP above the LED

SW = tuple(PARTS['SW1']['center'])
# Flexure: hinge 8 mm from the nub. At 4.5 mm the hinge strained ~2.7 % through the travel
# (3 t d / 2 L^2), marginal for PLA and a crack in resin; at 8 mm with the smaller gap it is < 0.7 %.
TONGUE = (SW[0] - 8.0, SW[1] - 4.5, SW[0] + 4.5, SW[1] + 4.5)
HINGE_ON_LEFT = True                         # hinge towards the board centre
SLOT, TONGUE_T, NUB_D = 0.6, 0.8, 2.5
NUB_GAP = 0.1 if SLA else 0.2                # nub above the switch plunger

RIB = 0.8                                    # front clamps the board within RIB of its edge
LIP_W, LIP_H = 0.6, 0.8                       # alignment lip on the back, groove in the front
LIP_CL = 0.1 if SLA else 0.15
LIP_Y_MIN = 3.0                              # no lip along the bottom edge: the cell slides out there

OUT_R = BR + CL + WALL


# ---- helpers --------------------------------------------------------------------------------
def rbox(x0, y0, x1, y1, r, z0, z1):
    """Box with vertical edges filleted to r."""
    b = Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
    if r <= 0: return b
    edges = [e for e in b.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[-1].Point.z) > 1e-6]
    return b.makeFillet(r, edges)


def cyl(x, y, d, z0, z1):
    return Part.makeCylinder(d / 2, z1 - z0, V(x, y, z0))


def box(cx, cy, w, h, z0, z1):
    return Part.makeBox(w, h, z1 - z0, V(cx - w / 2, cy - h / 2, z0))


# ---- the board, as the case sees it ---------------------------------------------------------
def board_model():
    s = rbox(0, 0, BW, BH, BR, 0, BT)
    for h in GEOM['holes']:
        if not h['plated']: s = s.cut(cyl(h['at'][0], h['at'][1], h['d'], -1, BT + 1))
    parts = []
    for ref, p in PARTS.items():
        if p['height'] <= 0: continue
        x0, y0, x1, y1 = p['bbox']
        parts.append(Part.makeBox(x1 - x0, y1 - y0, p['height'], V(x0, y0, BT)))
    return s, Part.makeCompound(parts)


# ---- shells ---------------------------------------------------------------------------------
def outer(z0, z1):
    return rbox(-CL - WALL, -SCREW_END, BW + CL + WALL, BH + CL + WALL, OUT_R, z0, z1)


def pocket(z0, z1):
    return rbox(-CL, -CL, BW + CL, BH + CL, BR + CL, z0, z1)


def band(d0, d1, z0, z1):
    """Ring between the board pocket grown by d0 and by d1, except along the cell edge."""
    ring = rbox(-CL - d1, -CL - d1, BW + CL + d1, BH + CL + d1, BR + CL + d1, z0, z1).cut(
        rbox(-CL - d0, -CL - d0, BW + CL + d0, BH + CL + d0, BR + CL + d0, z0 - 1, z1 + 1))
    return ring.cut(Part.makeBox(BW + 20, 20, z1 - z0 + 2, V(-10, LIP_Y_MIN - 20, z0 - 1)))


def stadium(r, z0, z1):
    """Stadium around the segment from the board's sound hole to the case port (a circle when
    they coincide, as they do now)."""
    (ax, ay), (bx, by) = MIC, PORT
    s = cyl(ax, ay, 2 * r, z0, z1).fuse(cyl(bx, by, 2 * r, z0, z1))
    if abs(bx - ax) > 1e-6:
        s = s.fuse(Part.makeBox(abs(bx - ax), 2 * r, z1 - z0, V(min(ax, bx), ay - r, z0)))
    return s.removeSplitter()


def gasket():
    return stadium(CAV_R + GASKET_WALL, -STANDOFF, 0).cut(stadium(CAV_R, -STANDOFF - 1, 1))


def crush_bead():
    rm = CAV_R + GASKET_WALL / 2
    return stadium(rm + 0.15, 0, CRUSH).cut(stadium(rm - 0.15, -1, 1))


def back_shell():
    s = outer(Z_BOT, Z_SPLIT)
    s = s.fuse(band(LIP_CL, LIP_CL + LIP_W, Z_SPLIT, Z_SPLIT + LIP_H))           # alignment lip
    s = s.cut(pocket(0, Z_SPLIT + 1))                                           # board pocket
    s = s.cut(rbox(LEDGE, LEDGE, BW - LEDGE, BH - LEDGE, max(BR - LEDGE, 0.5), -STANDOFF, 0.01))
    s = s.fuse(gasket())
    if CRUSH:
        s = s.fuse(crush_bead())
    s = s.fuse(cyl(SCREW[0], SCREW[1], BOSS_D, -STANDOFF, 0))                  # supports the board at H1
    s = s.cut(stadium(CAV_R, -STANDOFF, 1))                                    # inside the gasket ring
    s = s.cut(cyl(PORT[0], PORT[1], MIC_HOLE, Z_BOT - 1, 0))                   # mic port
    s = s.cut(cyl(PORT[0], PORT[1], MIC_RECESS, Z_BOT - 1, Z_BOT + MIC_RECESS_D))
    s = s.cut(cyl(RING_XY[0], RING_XY[1], RING_HOLE, Z_BOT - 1, Z_SPLIT + 1))
    s = s.cut(cyl(SCREW[0], SCREW[1], SCREW_CLEAR, Z_BOT - 1, Z_SPLIT + 1))
    s = s.cut(cyl(SCREW[0], SCREW[1], SCREW_HEAD, Z_BOT - 1, Z_BOT + SCREW_HEAD_D))
    return s.removeSplitter()


def front_shell():
    s = outer(Z_SPLIT, Z_TOPF)
    cav = pocket(Z_SPLIT - 1, Z_CEIL)
    # edge rib: the band within RIB inside the board edge stays solid and clamps the board
    rib = pocket(Z_SPLIT, Z_CEIL).cut(rbox(RIB, RIB, BW - RIB, BH - RIB, max(BR - RIB, 0.5), Z_SPLIT - 1, Z_CEIL + 1))
    s = s.cut(cav).fuse(rib)
    s = s.cut(band(0, 2 * LIP_CL + LIP_W, Z_SPLIT - 1, Z_SPLIT + LIP_H + LIP_CL))  # its groove
    # screw boss clamps the board around H1; keyring hole through the bottom end
    s = s.fuse(cyl(SCREW[0], SCREW[1], BOSS_D, Z_SPLIT, Z_CEIL))
    s = s.cut(cyl(RING_XY[0], RING_XY[1], RING_HOLE, Z_SPLIT - 1, Z_TOPF + 1))
    # LED light tubes and windows
    for ref in LEDS:
        x, y = PARTS[ref]['center']
        z0 = BT + PARTS[ref]['height'] + TUBE_GAP
        s = s.fuse(box(x, y, TUBE_X, TUBE_Y, z0, Z_CEIL))
        s = s.cut(box(x, y, WIN_X, WIN_Y, z0 - 1, Z_TOPF + 1))
    # button flexure: U-slot through the top, tongue thinned from below, nub down to the plunger
    x0, y0, x1, y1 = TONGUE
    slot = box((x0 + x1) / 2 + SLOT / 2, y1 + SLOT / 2, x1 - x0 + SLOT, SLOT, Z_CEIL - 1, Z_TOPF + 1)
    slot = slot.fuse(box((x0 + x1) / 2 + SLOT / 2, y0 - SLOT / 2, x1 - x0 + SLOT, SLOT, Z_CEIL - 1, Z_TOPF + 1))
    slot = slot.fuse(box(x1 + SLOT / 2, (y0 + y1) / 2, SLOT, y1 - y0 + 2 * SLOT, Z_CEIL - 1, Z_TOPF + 1))
    s = s.cut(slot)
    s = s.cut(Part.makeBox(x1 - x0, y1 - y0, TOP - TONGUE_T, V(x0, y0, Z_CEIL)))
    s = s.fuse(cyl(SW[0], SW[1], NUB_D, BT + PARTS['SW1']['height'] + NUB_GAP, Z_CEIL + TOP - TONGUE_T))
    s = s.cut(cyl(SW[0], SW[1], 4.0, Z_TOPF - 0.3, Z_TOPF + 1))           # finger dimple
    # screw pilot
    s = s.cut(cyl(SCREW[0], SCREW[1], SCREW_PILOT, Z_SPLIT - 1, Z_SPLIT + SCREW_DEPTH))
    return s.removeSplitter()


# ---- build, check, show ---------------------------------------------------------------------
def export(doc, out_dir):
    """STEP + STL per shell, in print orientation: back floor down, front top down."""
    import Mesh, MeshPart
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for name, flip in (('Back', False), ('Front', True)):
        shp = doc.getObject(name).Shape.copy()
        if flip: shp.rotate(V(0, 0, 0), V(1, 0, 0), 180)
        bb = shp.BoundBox
        shp.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
        step = os.path.join(out_dir, f'dbfob-case-{name.lower()}.step')
        stl = os.path.join(out_dir, f'dbfob-case-{name.lower()}.stl')
        shp.exportStep(step)
        MeshPart.meshFromShape(Shape=shp, LinearDeflection=0.02, AngularDeflection=0.15).write(stl)
        files += [step, stl]
    return files


def build(doc_name='dbfob_case'):
    board, comps = board_model()
    back, front = back_shell(), front_shell()
    report = {
        'port_x': round(PORT[0], 2),
        'gasket_to_via_edge_mm': round(((PORT[0] - VIA_NEAR_PORT[0][0]) ** 2 + (PORT[1] - VIA_NEAR_PORT[0][1]) ** 2) ** 0.5
                                       - VIA_NEAR_PORT[1] - (CAV_R + GASKET_WALL), 3),
        'keyring_web_mm': [round(RING_XY[1] - RING_HOLE / 2 + SCREW_END, 2), round(-CL - (RING_XY[1] + RING_HOLE / 2), 2)],  # to outer edge, to board pocket
        'outer_mm': [round(BW + 2 * (CL + WALL), 2), round(BH + CL + WALL + SCREW_END, 2), round(Z_TOPF - Z_BOT, 2)],
        'back_volume_mm3': round(back.Volume, 1), 'front_volume_mm3': round(front.Volume, 1),
        'valid': [back.isValid(), front.isValid()],
        # every one of these must be 0: the case may touch the board, never overlap it
        'process': PROCESS,
        # the crush bead is meant to press into the board: the back may overlap the board by
        # exactly the bead's interference and nothing else
        'overlap_back_board_beyond_bead': round(back.common(board).Volume - (crush_bead().common(board).Volume if CRUSH else 0), 3),
        'crush_bead_interference_mm3': round(crush_bead().common(board).Volume, 3) if CRUSH else 0,
        'overlap_front_board': round(front.common(board).Volume, 3),
        'overlap_front_parts': round(front.common(comps).Volume, 3),
        'overlap_shells': round(front.common(back).Volume, 3),
    }
    doc = App.getDocument(doc_name) if doc_name in App.listDocuments() else App.newDocument(doc_name)
    for o in list(doc.Objects): doc.removeObject(o.Name)
    for name, shp, col in (('Board', board, (0.1, 0.45, 0.2)), ('Parts', comps, (0.7, 0.7, 0.7)),
                           ('Back', back, (0.2, 0.2, 0.25)), ('Front', front, (0.85, 0.5, 0.1))):
        o = doc.addObject('Part::Feature', name); o.Shape = shp
        if App.GuiUp:
            o.ViewObject.ShapeColor = col
            if name == 'Front': o.ViewObject.Transparency = 60
    doc.recompute()
    return doc, report


if __name__ == '__main__' or 'GEOM' in globals():
    doc, report = build()
    print(json.dumps(report, indent=1))
