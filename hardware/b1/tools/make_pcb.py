#!/usr/bin/env python3
"""Build hardware/b1/b1.kicad_pcb from the schematic: place, draw the antenna, route, check.
Same method as rev A's make_pcb.py (etofab.md): placement is a table, KiCadRoutingTools routes
under our fab rules, UUIDs derive from content, DRC with schematic parity is the gate.

  python3 hardware/lib/gen_lib.py
  python3 hardware/b1/tools/gen_sch.py
  python3 hardware/b1/tools/make_pcb.py
  python3 hardware/b1/tools/fab.py

Board: the stick, 10.5 x 76.5 x 1.0 mm, 4 layers, every machine-placed part on the front. The
outline and the antenna block (coil in the tip, the LB crossover, tag, trim pads, the AAA
contacts on the back) come from ../lib/antenna.py, identical to the NFC test board's. Along
the stick from the tip: the mic inside the coil with its port through the board, the tag, the
LED bar, the MCU, the boost converter, the button, the programming pads. Everything past the
coil sits under the cell, which lies on the back.

Four layers because two would not route in 10.5 mm: the MCU's fan-out, the tag's lines and the
mic's lines out of the coil share one corridor, and the cell contacts' pads fill the middle of
B.Cu. The inner layers carry signals only. No planes or pours anywhere: copper near the loop
detunes it, so GND is tracks like everything else, and every layer under the coil is kept clear
apart from the band at its cell end, where LB and the mic's nets cross under the turns.
Hand-drawn: a via in U2's exposed pad, and the mic's GND ring tied to its GND pad.
Routing: signals first, then the power nets, with the router's mps net ordering and no extra via
cost near pads (the default tenfold one keeps the MCU's bottom pins off the inner layers).
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

W, H = ant.L, ant.W           # board, mm: x along the stick
X0, Y0 = 100.0, 100.0
THICKNESS = 1.0
TRACK, CLEAR, VIA, DRILL = 0.15, 0.15, ant.VIA, ant.DRILL
POWER = ['/GND', '/VDD', '/VCELL']
LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']   # 4 layers, no planes: the inner two are for signals
POWER_FIRST = os.environ.get('POWER_FIRST') == '1'
ROUTER_ARGS = os.environ.get('ROUTER_ARGS', '').split()

# The antenna block (coil, LB crossover, NT1, U1, C1-C3, BT1) is ../lib/antenna.py's.
PLACE = dict(ant.PLACE, **{
    # mic at the tip inside the coil, pads towards the cell end; port at x 4.36
    'MK1': (4.9, 5.25, 180, False),
    'C6': (7.5, 5.25, 90, False),
    'R8': (9.2, 5.25, 90, False),
    # tag pull-ups right of U1, signal pad left, each level with its pin
    'R1': (32.0, 2.3, 180, False),     # SDA
    'R3': (32.0, 4.0, 180, False),     # FD
    'R2': (32.0, 5.7, 180, False),     # SCL
    # LED bar right after the tag, green to red. Each column: the LED at the top, cathode to the
    # edge, anode down onto its resistor, whose U2 end faces the middle of the stick.
    'D1': (34.6, 1.9, 270, False), 'D2': (36.4, 1.9, 270, False), 'D3': (38.2, 1.9, 270, False), 'D4': (40.0, 1.9, 270, False),
    'R4': (34.6, 5.0, 90, False), 'R5': (36.4, 5.0, 90, False), 'R6': (38.2, 5.0, 90, False), 'R7': (40.0, 5.0, 90, False),
    'U2': (45.4, 5.25, 0, False),
    'C4': (48.4, 2.4, 90, False),      # VDD decoupling, top right of U2: its top pins escape upwards
    # boost: L1 over U3, SW (pin 1) top left, VBAT (pin 6) top right, VOUT (5) and FB (4) right
    'U3': (51.5, 5.25, 0, False),
    'L1': (51.5, 2.2, 180, False),
    'C7': (54.7, 2.4, 90, False),
    'C5': (54.7, 5.6, 90, False),
    'R9': (51.8, 8.5, 0, False),
    'R10': (55.1, 8.5, 0, False),
    'SW1': (59.5, 5.25, 90, False),
    'J1': (63.3, 5.25, 90, False),     # pads along the stick: SWDIO SWCLK GND VDD TX
})

# The mic's GND ring (pad 3, round the port) tied to its GND pad 2: the router can't get in
# between the pads. Ring centre line at r 0.6 round the port.
RING_TIE = ['MK1.2', (4.36 + 0.6 * math.cos(math.radians(40)), 5.25 - 0.6 * math.sin(math.radians(40)))]

SILK_F = [  # text, x, y, size
    # 1.0 mm: JLC's minimum legend height
    ('D', 63.30, 3.6, 1.0), ('C', 65.84, 3.6, 1.0), ('G', 68.38, 3.6, 1.0), ('+', 70.92, 3.6, 1.0),
    ('T', 73.46, 3.6, 1.0),
    ('dbfob B1', 67.8, 8.4, 1.0),
]
SILK_B = [
    ('AAA', 44.0, 9.4, 1.0),
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
    board.SetCopperLayerCount(4)
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(THICKNESS))
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
    ant.outline(board, mm)
    for i, box in enumerate(ant.KEEPOUTS):
        keepout(board, box, f'under the coil {i}', (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu))
    gap = ant.draw(board, nets, fps, mm, track, via)
    # U2's exposed pad straight down
    via(board, nets['/GND'], *PLACE['U2'][:2])
    ref, pad = RING_TIE[0].split('.')
    track(board, nets['/GND'], pcbnew.F_Cu, next(q for q in fps[ref].Pads() if q.GetNumber() == pad).GetPosition(),
          mm(*RING_TIE[1]), TRACK)

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
    groups = [[n for n in nets if n not in POWER], [n for n in nets if n in POWER]]
    if POWER_FIRST: groups.reverse()
    for k, group in enumerate(groups):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'routed.kicad_pcb')
            r = subprocess.run([py, os.path.join(KRT, 'py_router', 'route.py'), PCB, out, '--nets', *group,
                                '--layers', *LAYERS, '--track-width', str(TRACK), '--clearance', str(CLEAR),
                                '--via-size', str(VIA), '--via-drill', str(DRILL),
                                '--power-nets', *POWER, '--power-nets-widths', *['0.3'] * len(POWER),
                                '--grid-step', '0.025', '--fab-tier', 'standard', '--escalation', 'off',
                                '--same-net-pad-clearance', '0.2', '--board-edge-clearance', '0.5',
                                '--hole-to-hole-clearance', '0.25', '--max-ripup', '200',
                                '--via-proximity-cost', '0',   # the MCU's pins must drop to the inner layers
                                *ROUTER_ARGS, '--ordering', os.environ.get('ORDERING%d' % k, os.environ.get('ORDERING', 'mps')), '--direction', os.environ.get('DIRECTION', 'forward')],
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
