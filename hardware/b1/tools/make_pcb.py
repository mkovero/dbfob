#!/usr/bin/env python3
"""Build hardware/b1/b1.kicad_pcb from the schematic: place, draw the antenna, route, check.
Same method as rev A's make_pcb.py (etofab.md): placement is a table, KiCadRoutingTools routes
under our fab rules, UUIDs derive from content, DRC with schematic parity is the gate.

  python3 hardware/lib/gen_lib.py
  python3 hardware/b1/tools/gen_sch.py
  python3 hardware/b1/tools/make_pcb.py
  python3 hardware/b1/tools/fab.py

Board: 30 x 26 mm, 2 layers, every machine-placed part on top. The antenna block (coil round the
edge, its crossover, the tag, trim pads, the CR2032 holder on the back) comes from
../lib/antenna.py, identical to the NFC test board's. Inside the coil: the MCU in the middle,
the mic at the top centre with its port through the board into the strip above the holder,
the LED bar and the button right, the programming pads down the right side.

No ground pour: copper inside the loop detunes it, so GND is tracks like everything else, and
B.Cu under the coil is kept clear apart from the crossover. Three hand GND vias (U2's exposed
pad, the tag's VSS, C4 by the mic) let the router join GND on B.Cu under the holder.
Routing: signals first, then GND and VBAT, with the router's 'mps' net ordering (inside_out
leaves MIC_DATA or SWDIO open here).
"""
import json, math, os, re, shutil, subprocess, sys, tempfile, uuid
import pcbnew

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lib'))
import antenna as ant

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'b1'
SCH = os.path.join(HERE, NAME + '.kicad_sch')
PCB = os.path.join(HERE, NAME + '.kicad_pcb')
PRO = os.path.join(HERE, NAME + '.kicad_pro')
TEMPLATE = os.path.join(HERE, '..', 'tools', 'project_template.kicad_pro')
FPLIBS = {'dbfob': os.path.join(HERE, '..', 'lib', 'dbfob.pretty')}
FPLIB = '/usr/share/kicad/footprints'
KRT = os.environ.get('KRT', '/home/mui/src/KicadRoutingTools')

W, H = 30.0, 26.0            # board, mm
X0, Y0 = 100.0, 100.0
CORNER = 3.0
TRACK, CLEAR, VIA, DRILL = 0.2, 0.15, ant.VIA, ant.DRILL
POWER = ['/GND', '/VBAT']

# The antenna block (coil, VO/VI crossover, NT1, U1, C1-C3, BT1) is ../lib/antenna.py's.
PLACE = dict(ant.PLACE, **{
    'U2': (15.0, 10.8, 0, False),      # mic on the left/top-left pins, tag below, LEDs and button right
    'C4': (12.6, 7.65, 0, False),      # VDD (pin 19, top) decoupling
    'C5': (9.8, 6.0, 90, False),       # bulk
    'MK1': (15.0, 5.0, 90, False),     # port at (15, 4.46): above the holder's top edge (6.15)
    'C6': (11.8, 5.4, 90, False),
    # LED bar, vertical, right of U2: red on top. Resistors next to U2 (pad 1 left), LEDs
    # outside them with the anode left, cathode right
    'R7': (19.2, 7.2, 0, False), 'R6': (19.2, 8.8, 0, False),
    'R5': (19.2, 10.4, 0, False), 'R4': (19.2, 12.0, 0, False),
    'D4': (22.2, 7.2, 180, False), 'D3': (22.2, 8.8, 180, False),
    'D2': (22.2, 10.4, 180, False), 'D1': (22.2, 12.0, 180, False),
    'SW1': (21.0, 17.0, 90, False),
    'R8': (16.9, 14.4, 90, False),     # BTN pull-up
    # tag pull-ups in a stack left of U1, each level with its pin: supply pad left, signal right
    'R2': (9.9, 16.4, 0, False),      # SCL
    'R3': (9.9, 18.0, 0, False),      # FD
    'R1': (9.9, 19.6, 0, False),      # SDA
    'J1': (25.0, 8.6, 0, False),       # pads downwards: SWDIO SWCLK GND VBAT
})

SILK_F = [  # text, x, y, size
    ('D', 26.2, 8.6, 0.7), ('C', 26.2, 11.14, 0.7), ('G', 26.2, 13.68, 0.7), ('+', 26.2, 16.22, 0.7),
    ('dbfob B1', 6.4, 12.0, 1.0),
]
SILK_B = [
    ('FERRITE under cell', 15.0, 11.0, 0.9),
    ('CR2032 holder BS-08', 15.0, 17.5, 0.9),
]


def mm(x, y): return pcbnew.VECTOR2I(pcbnew.FromMM(X0 + x), pcbnew.FromMM(Y0 + y))


def netlist():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'n.net')
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', out, SCH],
                       check=True, capture_output=True)
        t = open(out).read()
    comps = {}
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)\s+\(value "([^"]*)"\)\s+\(footprint "([^"]*)"\)(.*?)\(tstamps "([^"]+)"\)', t, re.S):
        fields = dict(re.findall(r'\(field\s+\(name "([^"]+)"\)\s+"([^"]*)"\)', m.group(4)))
        comps[m.group(1)] = (m.group(3), m.group(2), m.group(5), fields)
    pins = {}
    nets = t[t.index('(nets'):]
    for blk in re.split(r'\(net\s+\(code', nets)[1:]:
        name = re.search(r'\(name "([^"]*)"\)', blk).group(1)
        for ref, pin in re.findall(r'\(ref "([^"]+)"\)\s+\(pin "([^"]+)"', blk):
            pins[(ref, pin)] = name
    return comps, pins


def write_project():
    pro = json.load(open(TEMPLATE))
    pro['meta']['filename'] = NAME + '.kicad_pro'
    pro['board']['design_settings']['rules'].update(
        min_clearance=0.0, min_copper_edge_clearance=0.5, min_hole_clearance=0.25, min_hole_to_hole=0.25,
        min_through_hole_diameter=0.3, min_track_width=0.15, min_via_annular_width=0.13,
        min_via_diameter=0.6, min_text_height=0.7, min_text_thickness=0.15)
    for c in pro['net_settings']['classes']:
        c.update(clearance=CLEAR, via_diameter=VIA, via_drill=DRILL,
                 track_width=TRACK if c['name'] == 'Default' else 0.3)
    pro['net_settings']['netclass_patterns'] = [{'netclass': 'Power', 'pattern': n} for n in POWER]
    pro['sheets'] = []
    open(PRO, 'w').write(json.dumps(pro, indent=2) + '\n')
    open(os.path.splitext(PRO)[0] + '.kicad_dru', 'w').write('(version 1)\n')
    return open(PRO).read()


def text(board, s, x, y, size, layer, mirror=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s); t.SetPosition(mm(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(max(0.15, size * 0.15)))
    if mirror: t.SetMirrored(True)
    board.Add(t)


def outline(board):
    r = CORNER
    segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(*a)); s.SetEnd(mm(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.05))
        board.Add(s)
    k = r * (1 - 0.5 ** 0.5)
    for a, m, b in [((0, r), (k, k), (r, 0)), ((W - r, 0), (W - k, k), (W, r)),
                    ((W, H - r), (W - k, H - k), (W - r, H)), ((r, H), (k, H - k), (0, H - r))]:
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(mm(*a), mm(*m), mm(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.05))
        board.Add(s)


def keepout(board, box, name, layers=(pcbnew.F_Cu, pcbnew.B_Cu)):
    for layer in layers:
        z = pcbnew.ZONE(board); z.SetIsRuleArea(True); z.SetLayer(layer); z.SetZoneName(name)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ol = z.Outline(); ol.NewOutline()
        x0, y0, x1, y1 = box
        for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]: ol.Append(mm(x, y))
        board.Add(z)


def track(board, net, layer, a, b, width):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(a); t.SetEnd(b); t.SetLayer(layer); t.SetWidth(pcbnew.FromMM(width)); t.SetNet(net)
    board.Add(t)


def via(board, net, x, y):
    v = pcbnew.PCB_VIA(board); v.SetPosition(mm(x, y)); v.SetNet(net)
    v.SetWidth(pcbnew.FromMM(VIA)); v.SetDrill(pcbnew.FromMM(DRILL)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(v)


def build():
    comps, pins = netlist()
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    nets = {}
    for name in sorted(set(pins.values())):
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    missing = set(comps) - set(PLACE)
    if missing: raise SystemExit(f'no placement for {sorted(missing)}')
    fps = {}
    for ref in sorted(comps):
        fpid, value, tstamp, fields = comps[ref]
        lib, name = fpid.split(':')
        fp = pcbnew.FootprintLoad(FPLIBS.get(lib, os.path.join(FPLIB, lib + '.pretty')), name)
        fp.SetReference(ref); fp.SetValue(value)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetPath(pcbnew.KIID_PATH('/' + tstamp))
        fp.SetSheetfile(NAME + '.kicad_sch'); fp.SetSheetname('/')
        for k in ('LCSC', 'MPN', 'Note'):
            f = pcbnew.PCB_FIELD(fp, pcbnew.FIELD_T_USER, k)
            f.SetText(fields.get(k, '')); f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
            fp.Add(f)
        x, y, r, back = PLACE[ref]
        fp.SetPosition(mm(x, y)); fp.SetOrientationDegrees(r)
        fp.Reference().SetLayer(pcbnew.F_Fab)
        if 'DNP' in fields or ref in ('C1', 'C2'):
            fp.SetDNP(True)
        board.Add(fp)
        if back: fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        for p in fp.Pads():
            net = pins.get((ref, p.GetNumber()))
            if net in nets: p.SetNet(nets[net])
        fps[ref] = fp
    outline(board)
    for i, box in enumerate(ant.KEEPOUT_SIDES + ant.KEEPOUT_BOTTOM):
        keepout(board, box, f'under the coil {i}', (pcbnew.B_Cu,))
    gap = ant.draw(board, nets, fps, mm, track, via)
    # U2's exposed pad straight down to B.Cu, where the router fans GND out under the holder
    via(board, nets['/GND'], *PLACE['U2'][:2])
    # the tag's VSS (pin 2, top) is boxed in by LA and SCL: straight up to its own via
    pad = next(q for q in fps['U1'].Pads() if q.GetNumber() == '2').GetPosition()
    track(board, nets['/GND'], pcbnew.F_Cu, pad, mm(13.75, 16.1), 0.25)
    via(board, nets['/GND'], 13.75, 16.1)
    # the mic's ring, C6 and C4 share GND above U2's top pins, cut off from the EP: own via
    pad = next(q for q in fps['C4'].Pads() if q.GetNumber() == '2').GetPosition()
    track(board, nets['/GND'], pcbnew.F_Cu, pad, mm(13.375, 6.7), 0.3)
    via(board, nets['/GND'], 13.375, 6.7)

    for s, x, y, size in SILK_F: text(board, s, x, y, size, pcbnew.F_SilkS)
    for s, x, y, size in SILK_B: text(board, s, x, y, size, pcbnew.B_SilkS, mirror=True)
    ds = board.GetDesignSettings()
    ds.SetAuxOrigin(mm(0, H)); ds.SetGridOrigin(mm(0, H))
    board.Save(PCB)
    stabilise_uuids(PCB)
    print(ant.summary(gap))


def _top_blocks(text, kinds):
    out, pat = [], re.compile(r'\n\t\((' + '|'.join(kinds) + r')\b')
    for m in pat.finditer(text):
        j, depth = m.start() + 2, 0
        while True:
            c = text[j]
            if c == '"':
                j += 1
                while text[j] != '"': j += 2 if text[j] == '\\' else 1
            elif c == '(': depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0: break
            j += 1
        out.append((m.start(), j + 1, m.group(1), text[m.start():j + 1]))
    return out


def stabilise_uuids(path):
    """UUIDs from content, footprints in reference order (etofab.md §4); see rev A's make_pcb.py."""
    ns = uuid.UUID('c7d35a90-1e2b-4b8f-9a64-5f0e8d2b3c71')
    text_ = open(path).read()
    blocks = _top_blocks(text_, ('footprint',))
    if not blocks: return
    ref_of = lambda b: (re.search(r'\(property "Reference" "([^"]+)"', b) or [None, ''])[1]

    def renumber(body, tag):
        k = iter(range(10 ** 6))
        return re.sub(r'\(uuid "[^"]*"\)', lambda m: f'(uuid "{uuid.uuid5(ns, f"{tag}/{next(k)}")}")', body)
    fps = sorted((ref_of(b), renumber(b, 'fp/' + ref_of(b))) for _, _, _, b in blocks)
    head, tail = text_[:blocks[0][0]], text_[blocks[-1][1]:]
    between = ''.join(text_[blocks[i][1]:blocks[i + 1][0]] for i in range(len(blocks) - 1))
    text_ = renumber(head, 'head') + ''.join(b for _, b in fps) + renumber(between + tail, 'tail')
    items = _top_blocks(text_, ('segment', 'via', 'arc', 'zone'))
    strip = lambda b: re.sub(r'\(uuid "[^"]*"\)', '', b)
    new = sorted(re.sub(r'\(uuid "[^"]*"\)', f'(uuid "{uuid.uuid5(ns, strip(b))}")', b) for _, _, _, b in items)
    new.sort(key=lambda b: re.search(r'\(uuid "([^"]*)"\)', b).group(1))
    out, last = [], 0
    for (a, e, _, _), b in zip(items, new):
        out += [text_[last:a], b]; last = e
    open(path, 'w').write(''.join(out) + text_[last:])


def route(keep_pro):
    """Signals first, then the power nets around them (one pass lets GND wall in the tag's pins)."""
    board = pcbnew.LoadBoard(PCB)
    # the antenna nets are drawn by hand; the router gets the rest (net names from the API)
    nets = sorted(str(n) for n in board.GetNetsByName().keys() if str(n) and str(n) not in ('/LA', '/LB'))
    py = os.path.join(KRT, '.venv', 'bin', 'python')
    for group in ([n for n in nets if n not in POWER], [n for n in nets if n in POWER]):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'routed.kicad_pcb')
            r = subprocess.run([py, os.path.join(KRT, 'py_router', 'route.py'), PCB, out, '--nets', *group,
                                '--layers', 'F.Cu', 'B.Cu', '--track-width', str(TRACK), '--clearance', str(CLEAR),
                                '--via-size', str(VIA), '--via-drill', str(DRILL),
                                '--power-nets', *POWER, '--power-nets-widths', *['0.3'] * len(POWER),
                                '--grid-step', '0.025', '--fab-tier', 'standard', '--escalation', 'off',
                                '--same-net-pad-clearance', '0.2', '--board-edge-clearance', '0.5',
                                '--hole-to-hole-clearance', '0.25', '--max-ripup', '200',
                                '--ordering', os.environ.get('ORDERING', 'mps'), '--direction', os.environ.get('DIRECTION', 'forward')],
                               capture_output=True, text=True, cwd=KRT)
            log = r.stdout + r.stderr
            if r.returncode or not os.path.exists(out):
                print(log[-3000:]); raise SystemExit('KiCadRoutingTools failed')
            shutil.copy(out, PCB)
        open(PRO, 'w').write(keep_pro)
        for l in log.splitlines():
            if l.startswith('JSON_SUMMARY_MIN'):
                print('  router:', l[:200])


def drc():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'd.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--save-board', '--schematic-parity',
                        '--severity-all', '--format', 'json', '-o', out, PCB], capture_output=True)
        return json.load(open(out))


def remove_dangling():
    removed = 0
    for _ in range(50):
        d = drc()
        base = len(d.get('unconnected_items', []))
        cands = [i for v in d['violations'] if v['type'] in ('via_dangling', 'track_dangling')
                 for i in v['items'][:1]]
        progress = False
        for it in cands:
            t = open(PCB).read()
            m = re.search(r'\n\t\((via|segment)\b[^\n]*?(?:\n\t\t[^\n]*)*?\(uuid "' + re.escape(it['uuid']) + r'"\)\n\t\)', t)
            if not m: continue
            open(PCB, 'w').write(t[:m.start()] + t[m.end():])
            if len(drc().get('unconnected_items', [])) > base:
                open(PCB, 'w').write(t)
            else:
                removed += 1; progress = True; break
        if not progress: break
    return removed


ALLOWED_DRC = {'lib_footprint_issues'}


def gate(d):
    out = []
    for x in d['violations']:
        if x['type'] not in ALLOWED_DRC:
            out.append(f"{x['severity']} {x['type']}: {x['description'][:70]} "
                       + '; '.join(i['description'][:50] for i in x.get('items', [])[:2]))
    out += [f"unconnected: {x['description'][:70]}" for x in d.get('unconnected_items', [])]
    out += [f"parity {x['type']}: {x['description'][:70]}" for x in d.get('schematic_parity', [])]
    n = len(d.get('unconnected_items', []))
    print(f"unconnected: {n}  other findings: {len(out) - n}")
    return out


def main():
    build()
    keep = write_project()
    if '--no-route' in sys.argv:
        print('placed:', PCB); return
    route(keep)
    stabilise_uuids(PCB)
    rules = lambda t: (json.loads(t)['net_settings']['classes'], json.loads(t)['board']['design_settings']['rules'])
    if rules(open(PRO).read()) != rules(keep): raise SystemExit('project rules changed underneath us')
    open(PRO, 'w').write(keep)
    k = remove_dangling()
    if k: print(f'removed {k} dangling via(s)/stub(s)')
    stabilise_uuids(PCB)
    problems = gate(drc())
    for x in problems: print('  ', x)
    if problems: sys.exit(f'{len(problems)} board problem(s): not a releasable board')


if __name__ == '__main__':
    main()
