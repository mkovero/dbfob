#!/usr/bin/env python3
"""Build hardware/dbfob.kicad_pcb from the schematic: place, route, pour, check.

  python3 hardware/tools/gen_sch.py      # tables -> schematic
  python3 hardware/tools/make_pcb.py     # schematic -> routed, poured, DRC-checked board
  python3 hardware/tools/fab.py          # board -> production/

The procedure is ../../../studer-vca/etofab.md: the schematic is the only source, placement is a
table, KiCadRoutingTools routes it under our fab rules (--fab-tier standard --escalation off, and
our .kicad_pro restored afterwards), GND is routed as tracks and then poured, UUIDs derive from
reference designators so two runs give the same file, and the result is judged by DRC with
schematic parity.

Board: 30 x 52.5 mm, everything on the top side (one assembly pass). Top edge: the LED bar, two
LEDs either side of the keyring hole. Below the hole the mic, whose bottom port opens through the
board to the back. Then U1, its decoupling, the programming pads and the button. The CR2032
holder takes the bottom half with its insertion opening at the bottom edge.
"""
import json, os, re, shutil, subprocess, sys, tempfile, uuid
import pcbnew

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCH = os.path.join(HERE, 'dbfob.kicad_sch')
PCB = os.path.join(HERE, 'dbfob.kicad_pcb')
PRO = os.path.join(HERE, 'dbfob.kicad_pro')
FPLIB = '/usr/share/kicad/footprints'
KRT = os.environ.get('KRT', '/home/mui/src/KicadRoutingTools')

W, H = 30.0, 52.5            # board, mm
X0, Y0 = 100.0, 100.0        # board top-left on the page
CORNER = 3.0
TRACK, CLEAR, VIA, DRILL = 0.2, 0.15, 0.6, 0.3     # JLC standard tier with margin
POWER = ['/GND', '/VBAT', '/MIC_VDD']

# Scoped rules instead of accepted errors (etofab.md §5): the only fixed-geometry exception.
DRU = '''(version 1)

# MK1 is Infineon's own land pattern: the GND ring pad 5 sits 0.21 mm from the 0.8 mm sound-port
# NPTH. JLC's NPTH-to-copper minimum is 0.20 mm, so this holds MK1 alone to 0.20 mm while the
# board keeps 0.25 mm everywhere else.
(rule "MK1 sound port"
	(condition "A.memberOfFootprint('MK1') && B.memberOfFootprint('MK1')")
	(constraint hole_clearance (min 0.2mm)))
'''

# ref: (x, y, rotation) in board mm from the top-left corner, y down
PLACE = {
    'H1': (15.0, 5.0, 0),
    'D1': (4.5, 4.0, 0), 'R4': (4.5, 7.0, 0),
    'D2': (9.0, 4.0, 0), 'R5': (9.0, 7.0, 0),
    'D3': (21.0, 4.0, 0), 'R6': (21.0, 7.0, 0),
    'D4': (25.5, 4.0, 0), 'R7': (25.5, 7.0, 0),
    'MK1': (15.0, 12.0, 180),
    'C3': (19.5, 12.0, 90),
    'U1': (15.0, 19.0, 90),            # pins 11-20 face the mic
    'C1': (17.0, 24.3, 0),
    'C2': (13.0, 24.3, 0),
    'J1': (3.5, 27.0, 90),             # pads run left to right: VBAT SWIO GND TX
    'SW1': (24.0, 26.5, 0),
    'BT1': (15.0, 41.0, 0),            # opening towards the bottom edge
}

SILK_F = [  # text, x, y, size
    ('+', 3.5, 29.2, 0.8), ('D', 6.04, 29.2, 0.8), ('G', 8.58, 29.2, 0.8), ('T', 11.12, 29.2, 0.8),
]
SILK_B = [   # kept clear of BT1's pad vias (y 37, 41, 45) and the router's via at the cell top
    ('dbfob rev A', 15.0, 31.6, 1.2),
    ('steady = bare ear', 15.0, 33.6, 0.9),
    ('blink = with plugs', 15.0, 35.2, 0.9),
    ('G<=83 Y<=90 O<=96 R>96', 15.0, 48.2, 0.8),
    ('MIC', 15.0, 9.3, 0.8),
    ('dBA at ear  CERN-OHL-P', 15.0, 50.0, 0.8),
]


def mm(x, y): return pcbnew.VECTOR2I(pcbnew.FromMM(X0 + x), pcbnew.FromMM(Y0 + y))


def netlist():
    """Components and pin->net from kicad-cli: {ref: (footprint, value, uuid)}, {(ref, pin): net}."""
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
    """Our rules, written onto a complete KiCad 10 project file (a partial one is silently
    ignored and the board falls back to 0.2 mm defaults). The router may rewrite this file; it is
    put back afterwards and the board judged by it."""
    pro = json.load(open(os.path.join(os.path.dirname(__file__), 'project_template.kicad_pro')))
    pro['meta']['filename'] = 'dbfob.kicad_pro'
    pro['board']['design_settings']['rules'].update(
        min_clearance=0.0, min_copper_edge_clearance=0.5, min_hole_clearance=0.25, min_hole_to_hole=0.25,
        min_through_hole_diameter=0.3, min_track_width=0.15, min_via_annular_width=0.13,
        min_via_diameter=0.6, min_text_height=0.8, min_text_thickness=0.15)
    classes = pro['net_settings']['classes']
    for c in classes:
        c.update(clearance=CLEAR, via_diameter=VIA, via_drill=DRILL,
                 track_width=TRACK if c['name'] == 'Default' else 0.3)
    pro['net_settings']['netclass_patterns'] = [{'netclass': 'Power', 'pattern': n} for n in POWER]
    pro['sheets'] = []
    open(PRO, 'w').write(json.dumps(pro, indent=2) + '\n')
    open(os.path.splitext(PRO)[0] + '.kicad_dru', 'w').write(DRU)
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


# The CR2032's + can wraps round its rim onto the - face that sits on BT1's pad, so the ring just
# outside the pad is where a + rim meets the board. No top copper there: only solder mask would
# separate the can from a GND pour, and one scratch from inserting a cell shorts it. The - pad
# reaches the back GND pour through vias inside the pad instead of through the top pour.
CELL_RING = (17.0, 20.6)      # keep-out annulus on F.Cu, inner/outer diameter, mm: the cell is
                              # 20 mm across; 20.6 clears the holder tabs (inner edge r = 10.35)
CELL_VIAS = [(-4, 0), (4, 0), (0, -4), (0, 4)]


def circle(r, n=72):
    import math
    return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def cell_guard(board, gnd):
    cx, cy, _ = PLACE['BT1']
    z = pcbnew.ZONE(board); z.SetIsRuleArea(True); z.SetLayer(pcbnew.F_Cu)
    z.SetZoneName('cell rim')
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ol = z.Outline(); ol.NewOutline()
    for x, y in circle(CELL_RING[1] / 2): ol.Append(mm(cx + x, cy + y))
    h = ol.NewHole(0)
    for x, y in circle(CELL_RING[0] / 2): ol.Append(pcbnew.VECTOR2I(mm(cx + x, cy + y)), 0, h)
    board.Add(z)
    for dx, dy in CELL_VIAS:
        v = pcbnew.PCB_VIA(board); v.SetPosition(mm(cx + dx, cy + dy)); v.SetNet(gnd)
        v.SetWidth(pcbnew.FromMM(VIA)); v.SetDrill(pcbnew.FromMM(DRILL)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(v)


def ring_guard(board):
    """No tracks or vias within 1 mm of the keyring hole on either layer: a steel ring wears the
    hole edge, and the router otherwise hugs the NPTH at exactly its clearance."""
    cx, cy, _ = PLACE['H1']
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board); z.SetIsRuleArea(True); z.SetLayer(layer); z.SetZoneName('keyring')
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(False)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ol = z.Outline(); ol.NewOutline()
        for x, y in circle(3.2 / 2 + 1.0): ol.Append(mm(cx + x, cy + y))
        board.Add(z)


def build():
    comps, pins = netlist()
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    nets = {}
    for name in sorted(set(pins.values())):
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    missing = set(comps) - set(PLACE)
    if missing: raise SystemExit(f'no placement for {sorted(missing)}')
    for ref in sorted(comps):
        fpid, value, tstamp, fields = comps[ref]
        lib, name = fpid.split(':')
        fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + '.pretty'), name)
        fp.SetReference(ref); fp.SetValue(value)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetPath(pcbnew.KIID_PATH('/' + tstamp))
        fp.SetSheetfile('dbfob.kicad_sch'); fp.SetSheetname('/')
        for k in ('LCSC', 'MPN', 'Note'):
            f = pcbnew.PCB_FIELD(fp, pcbnew.FIELD_T_USER, k)
            f.SetText(fields.get(k, '')); f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
            fp.Add(f)
        x, y, r = PLACE[ref]
        fp.SetPosition(mm(x, y)); fp.SetOrientationDegrees(r)
        # references live on F.Fab (assembly drawing); the board is too small for legible silk refs
        fp.Reference().SetLayer(pcbnew.F_Fab)
        board.Add(fp)
        for p in fp.Pads():
            net = pins.get((ref, p.GetNumber()))
            if net in nets: p.SetNet(nets[net])
    outline(board)
    cell_guard(board, nets['/GND'])
    ring_guard(board)
    for s, x, y, size in SILK_F: text(board, s, x, y, size, pcbnew.F_SilkS)
    for s, x, y, size in SILK_B: text(board, s, x, y, size, pcbnew.B_SilkS, mirror=True)
    # fab origin: board bottom-left, which is where JLC expects it for gerbers, drill and CPL
    ds = board.GetDesignSettings()
    ds.SetAuxOrigin(mm(0, H)); ds.SetGridOrigin(mm(0, H))
    board.Save(PCB)
    stabilise_uuids(PCB)


def _top_blocks(text, kinds):
    """(start, end, kind, body) of every top-level (kind ...) block, strings respected."""
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
    """Every UUID derived from what it belongs to, footprints in reference order: FootprintLoad
    hands out random UUIDs, KiCad writes footprints in UUID order and the router works in file
    order, so without this two identical placements route differently (etofab.md §4)."""
    ns = uuid.UUID('9e3c1b52-0f6a-4d7e-8b21-3c5d7a9e0f14')
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
    # tracks, vias, zones: UUID from content, and written in that order. Sequence-numbered UUIDs are
    # not a fixed point - KiCad re-sorts by UUID on the next save and the order flips each run.
    items = _top_blocks(text_, ('segment', 'via', 'arc', 'zone'))
    strip = lambda b: re.sub(r'\(uuid "[^"]*"\)', '', b)
    new = sorted(re.sub(r'\(uuid "[^"]*"\)', f'(uuid "{uuid.uuid5(ns, strip(b))}")', b) for _, _, _, b in items)
    new.sort(key=lambda b: re.search(r'\(uuid "([^"]*)"\)', b).group(1))
    out, last = [], 0
    for (a, e, _, _), b in zip(items, new):
        out += [text_[last:a], b]; last = e
    open(path, 'w').write(''.join(out) + text_[last:])


def route(keep_pro):
    board = pcbnew.LoadBoard(PCB)
    # net names from the API, never from the file text (etofab.md §4)
    nets = sorted(str(n) for n in board.GetNetsByName().keys() if str(n))
    py = os.path.join(KRT, '.venv', 'bin', 'python')
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'routed.kicad_pcb')
        r = subprocess.run([py, os.path.join(KRT, 'py_router', 'route.py'), PCB, out, '--nets', *nets,
                            '--layers', 'F.Cu', 'B.Cu', '--track-width', str(TRACK), '--clearance', str(CLEAR),
                            '--via-size', str(VIA), '--via-drill', str(DRILL),
                            '--power-nets', *POWER, '--power-nets-widths', *['0.3'] * len(POWER),
                            '--grid-step', '0.025', '--fab-tier', 'standard', '--escalation', 'off',
                            '--same-net-pad-clearance', '0.2', '--board-edge-clearance', '0.5',
                            '--hole-to-hole-clearance', '0.25', '--max-ripup', '200',
                            '--ordering', 'inside_out'],
                           capture_output=True, text=True, cwd=KRT)
        log = r.stdout + r.stderr
        if r.returncode or not os.path.exists(out):
            print(log[-3000:]); raise SystemExit('KiCadRoutingTools failed')
        shutil.copy(out, PCB)
    open(PRO, 'w').write(keep_pro)          # judged by our rules, never the router's rewrite
    for l in log.splitlines():
        if l.startswith('JSON_SUMMARY') or 'routed' in l.lower() and ('/' in l or 'fail' in l.lower()):
            print('  router:', l[:200])


def pour():
    board = pcbnew.LoadBoard(PCB)
    old = list(board.Zones())
    for z in old:
        if not z.GetIsRuleArea(): board.Remove(z)      # keep the keep-outs
    gnd = board.FindNet('/GND')
    for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
        z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(gnd)
        ol = z.Outline(); ol.NewOutline()
        for x, y in [(0, 0), (W, 0), (W, H), (0, H)]: ol.Append(mm(x, y))
        z.SetLocalClearance(pcbnew.FromMM(0.3)); z.SetMinThickness(pcbnew.FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(pcbnew.FromMM(0.3)); z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.35))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB)


def remove_dangling():
    """Delete vias/stubs DRC calls dangling, one at a time, keeping each removal only if
    connectivity is no worse: a 'dangling' via can be carrying a pour across layers (etofab.md §4).
    Text edits, not pcbnew, so the per-process project cache cannot touch the rules."""
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


def drc():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'd.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '--schematic-parity',
                        '--severity-all', '--format', 'json', '-o', out, PCB], capture_output=True)
        d = json.load(open(out))
    return d


def main():
    if '--pour' in sys.argv:
        pour(); return
    build()
    # after build(): saving a fresh BOARD() also writes its default rules over the project file
    keep = write_project()
    if '--no-route' in sys.argv:
        print('placed:', PCB); return
    route(keep)
    stabilise_uuids(PCB)
    # pcbnew caches the project per process: a LoadBoard here would see the defaults build()
    # saved, and its Save would write them back over our rules. Pour in a fresh process.
    subprocess.run([sys.executable, os.path.abspath(__file__), '--pour'], check=True, capture_output=True)
    rules = lambda t: (json.loads(t)['net_settings']['classes'], json.loads(t)['board']['design_settings']['rules'])
    if rules(open(PRO).read()) != rules(keep): raise SystemExit('project rules changed underneath us')
    open(PRO, 'w').write(keep)
    k = remove_dangling()
    if k: print(f'removed {k} dangling via(s)/stub(s)')
    stabilise_uuids(PCB)        # router tracks and zones come with random UUIDs too
    d = drc()
    lib = ('lib_footprint_issues', 'lib_footprint_mismatch')
    v = [x for x in d['violations'] if x['type'] not in lib]
    errs = [x for x in v if x['severity'] == 'error']
    print(f"unconnected: {len(d.get('unconnected_items', []))}  errors: {len(errs)}  "
          f"warnings: {len(v) - len(errs)}  parity: {len(d.get('schematic_parity', []))}")
    for x in v + d.get('schematic_parity', []) + d.get('unconnected_items', []):
        print(f"  {x['severity']:8s} {x['type']:28s} {x['description'][:60]} "
              + '; '.join(i['description'][:50] for i in x.get('items', [])[:2]))


if __name__ == '__main__':
    main()
