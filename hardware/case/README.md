# dbfob case, rev A

A two-part case, in an SLA and an FDM build, around the rev A board: a **front shell** and a **back shell**, held by **one M2 screw**. To change the cell, open the case: undo the screw, lift the front, slide the cell out of the bottom of the holder. The LEDs show through **open windows**.

**Ends.** The mic port and the LEDs are at the top end; the keyring is at the opposite, bottom end. A hand holding the fob by its keys therefore doesn't cover the mic. The screw uses the board's own Ø3.2 hole (H1) at the top end.

Inputs, both generated from the board so the case follows any layout change:
- `dbfob-board.step`, from `kicad-cli pcb export step --subst-models --drill-origin`. It has no 3D models for MK1 and SW1; their sizes come from the datasheets and are recorded in the JSON.
- `board_geometry.json`: part centres, bounding boxes and heights, and every hole.

Coordinates are in the board's fab frame: x to the right and y up from the board's bottom-left corner. z = 0 is the board's back face.

## Numbers

| Item | Value | Source |
|---|---|---|
| Board | 30 × 52.5 × 1.6 mm, R3 corners | layout |
| Tallest part | BT1 holder + cell, 4.0 mm above the board | KiCad STEP model |
| Other parts | SW1 1.5 (incl. plunger), MK1 / U1 1.2, LEDs 0.8 mm | datasheets |
| Clearance | SLA: 0.15 mm board to wall, 0.1 mm lip, 0.1 mm nub gap (FDM: 0.3 / 0.15 / 0.2); 0.5 mm above BT1 | `PROCESS` in `make_case.py` |
| Walls / floor / top | 1.6 / 1.2 / 1.2 mm (FDM walls 2.0, so the lip groove keeps 2 lines of skin) | perimeters at 0.4 mm |
| Outer size | SLA 33.5 × 62.25 × 8.9 mm, FDM 34.6 × 62.8 × 8.9 mm | board + walls + keyring end |

## Features

- **Screw.** An M2 × 6 **button head** (ISO 7380) goes through H1 at (15, 47.5), the board's own hole, and clamps the board between two Ø6 bosses.
  - Back shell: Ø2.3 clearance hole, with a Ø4.2 × 0.8 mm counterbore. The back is only 1.6 mm thick there.
  - Front shell: Ø1.7 pilot, 4.5 mm deep. The screw engages 3.6 mm, and its tip stops 2.1 mm short of the front face.
- **Keyring.** A Ø3.6 hole through both shells at the bottom end, (15, −4.2). The case extends 8 mm below the board to carry it.
  - It leaves 2.0 mm of material to the outer edge and 2.25 mm to the board pocket.
  - It's the end the cell comes out of, but the case is opened to change the cell anyway.
  - The mic port is not routed to an edge: a 13 mm duct to the top edge would resonate at about 6.6 kHz, inside the measured band.
- **Board retention.** The board is located by its outline pocket and the screw through H1.
  - It is clamped by 1 mm edge ribs from the front shell.
  - The ribs stay clear of J1's pads (x < 2.2 on the left) and BT1's tabs (x 3.1 and 26.9, y 8.9–14.1).
- **LED windows.** 1.4 × 1.0 mm openings (FDM 1.6 × 1.2) over D1–D4 at x = 4.5, 9, 21, 25.5, y = 48.5.
  - Each sits at the top of a square light tube that stops 0.2 mm above the LED, so there is no bleed between LEDs and the light stays directional.
  - Small engraved G Y O R marks sit below the windows.
- **Button.** A flexure tongue in the front over SW1 at (24, 26).
  - It is a U-slot 0.6 mm wide (FDM 0.8), 12.5 × 9 mm, hinged towards the board centre, 8 mm from the nub, and thinned to 0.8 mm.
  - The hinge strain at full travel is 0.66 % (3·t·d / 2L²). The first draft's 4.5 mm hinge came to 2.7 %, which would have cracked in resin.
  - A Ø2.5 nub stops 0.1 mm (SLA) / 0.2 mm (FDM) above the plunger.
- **Mic port.** A straight Ø1.0 hole in the back, directly under the board's sound hole at (14.32, 40.5), inside a Ø3 × 0.4 mm recess so a fingertip doesn't seal it.
  - It sits 0.68 mm off the case centreline. That's deliberate: the IM69D130's port is off its package centre and the board is fixed. Centring it would need a cavity joining two holes, with the gasket crossing a via.
  - Inside, a gasket ring (cavity Ø1.2, wall 0.5 mm, outer radius 1.1 mm) meets the board's back face, so sound reaches the mic only through the port. The ring clears the nearby tented SWIO via at (15.83, 40.47) by 0.11 mm.
  - On SLA the ring carries a 0.3 mm crush bead standing 0.08 mm proud (0.128 mm³ of intended interference); the board is preloaded onto it and the port is sealed.
  - The port's resonance is estimated at 35–40 kHz, well above the band measured.
- **Back floor.** It stands 0.4 mm off the board on a perimeter ledge and the gasket ring. The back of the board is flat: GND pour and tented vias only.

## Open until the first print

- Tolerances: the board pocket, the screw pilot, and the flexure's stiffness and travel.
- Whether the gasket ring seals well enough, measured as the level difference with the hole open and taped.
- The case's acoustic effect on the reading. The hand-held calibration from the firmware bring-up is done **in the case**.

## Files and printing

| File | What |
|---|---|
| `make_case.py` | The source: a FreeCAD script that builds both shells from `board_geometry.json`, checks fit and exports |
| `export_all.py` | Headless build of both variants: fit report plus the files below |
| `dbfob-case-back-sla.stl` / `.step` | Back shell, floor down: 33.5 × 62.25 × 4.0 mm |
| `dbfob-case-front-sla.stl` / `.step` | Front shell, top down: 33.5 × 62.25 × 5.7 mm |
| `dbfob-case-back-fdm.stl` / `.step` | Back shell, floor down: 34.6 × 62.8 × 4.0 mm |
| `dbfob-case-front-fdm.stl` / `.step` | Front shell, top down: 34.6 × 62.8 × 5.7 mm |

Two builds from the same script, chosen by `PROCESS`:

| | SLA | FDM |
|---|---|---|
| Board to wall / lip / nub gap | 0.15 / 0.1 / 0.1 mm | 0.3 / 0.15 / 0.2 mm |
| Wall | 1.6 mm | 2.0 mm |
| Screw clearance / pilot | Ø2.3 / Ø1.7 | Ø2.4 / Ø1.8 (FDM holes print small) |
| LED window / light tube | 1.4 × 1.0 / 2.6 × 2.2 mm | 1.6 × 1.2 / 3.2 × 2.8 mm (tube walls ≥ 2 lines) |
| Flexure slot | 0.6 mm | 0.8 mm (elephant's foot would close 0.6) |
| Gasket crush bead | 0.08 mm proud | none: layer lines would not seal against it |

**SLA printing:**
- **Resin: use a tough, ABS-like resin**, not standard resin. Standard resin is brittle, and the flexure hinge and the thread-forming screw would crack it.
- **Orientation and supports:** the files are exported flat, but let the slicer tilt them about 30–45° with supports on the **inside** faces only. Keep supports off:
  - the front's top face and LED windows,
  - the back's outer face,
  - the crush bead,
  - the lip.
- **Post-cure:** fully, before assembly. Resin shrinks by about 0.5–1 % on curing; if the board pocket comes out tight, scale X/Y by +0.5 % in the slicer rather than re-cutting clearances.
- **Screw:** M2 × 6 button-head (ISO 7380) thread-forming screw into the Ø1.7 pilot. Don't overtighten into resin. Heat-set inserts don't work in thermoset resin.

**FDM printing** (tuned for a Prusa MK2.5S, 0.4 mm nozzle):
- **PETG** preferred: tougher hinge, takes the thread-forming screw better. PLA works but the flexure creeps and may crack over time.
- **0.2 mm layers** (0.15 for nicer windows), Arachne perimeter generator (PrusaSlicer default), so the 0.5 mm gasket wall and thin tube walls get filled.
- **No supports.** Print as exported: back floor down, front top down. Every overhang is a bridge or a hole.
- **Elephant's foot compensation** on (0.2 mm), since the LED windows, the flexure slot and the outer edges sit on the first layer.
- The gasket ring won't seal as well as on SLA. If the open/taped test (below) shows leakage, a thin ring of foam tape or a dab of silicone on the ring fixes it.
- **Screw:** M2 × 6 button-head thread-forming screw into the Ø1.8 pilot. A heat-set insert is not an option: the boss is too small.

Fit check on rev A, both builds:
- Front shell vs board, front shell vs parts, and front vs back: 0 mm³ overlap in each case.
- Back shell vs board: SLA overlaps by exactly the crush bead's intended 0.128 mm³ and nothing else; FDM 0 mm³.
- The gasket stays clear of the via (0.11 mm).
- Keyring hole: 2.0 mm to the outer edge, 2.25 (SLA) / 2.1 (FDM) mm to the board pocket.

### Regenerating

```sh
cd hardware/case
freecadcmd export_all.py              # both builds; PROCS=fdm for one
```

It prints each build's fit report and writes the exports here. Every `overlap_*` must be 0. FreeCAD 1.1's AppImage works (`FreeCAD_1.1.4-Linux-x86_64-py311.AppImage freecadcmd export_all.py`). `make_case.py` alone also runs in the FreeCAD GUI to look at the model.

The script only reads `board_geometry.json` from its own folder. Refresh that file from the board first if the layout changed; see the git history for the generator snippet.
