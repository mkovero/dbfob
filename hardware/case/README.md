# dbfob case, rev A

A two-part FDM case around the rev A board: a **front shell** and a **back shell**, held by **one M2 screw**. To change the cell, open the case: undo the screw, lift the front, slide the cell out of the bottom of the holder. The LEDs show through **open windows**.

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
| Clearance | 0.3 mm board to wall, 0.5 mm above BT1 | FDM tolerance, to tune after the first print |
| Walls / floor / top | 1.6 / 1.2 / 1.2 mm | 4 perimeters at 0.4 mm |
| Outer size | ≈ 33.8 × 60.4 × 8.9 mm | board + walls + screw end |

## Features

- **Screw end.** An M2 boss sits below the board at (15, −3.2), past the edge the cell comes out of.
  - Back shell: Ø2.3 through hole with a Ø4.2 counterbore for a pan head.
  - Front shell: Ø1.7 pilot for a thread-forming M2 × 8, or Ø3.2 for a heat-set insert.
- **Keyring.** A Ø3.4 tube through both shells, coaxial with the board's Ø3.2 hole at (15, 47.5).
  - The front boss (OD 6) clamps the board top. Nothing is within r = 3.5 of the hole.
  - The keyring goes through case and board together.
- **Board retention.** The board is located by the keyring tube and its outline pocket.
  - It is clamped by 1 mm edge ribs from the front shell.
  - The ribs stay clear of J1's pads (x < 2.2 on the left) and BT1's tabs (x 3.1 and 26.9, y 8.9–14.1).
- **LED windows.** 1.4 × 1.0 mm openings over D1–D4 at x = 4.5, 9, 21, 25.5, y = 48.5.
  - Each sits at the top of a square light tube that stops 0.2 mm above the LED, so there is no bleed between LEDs and the light stays directional.
  - Small engraved G Y O R marks sit below the windows.
- **Button.** A flexure tongue in the front over SW1 at (24, 26).
  - It is a U-slot 0.6 mm wide, about 7 × 9 mm, hinged towards the board centre and thinned to 0.8 mm.
  - A Ø2.5 nub reaches to 0.2 mm above the plunger.
- **Mic port.** A Ø1.2 hole in the back under MK1's port at (14.32, 40.5), with a 3 mm recess so a fingertip doesn't seal it.
  - Inside, a gasket ring (ID 2.0, OD 3.2) on the floor meets the board's back face, so sound reaches the mic through the hole and not from the case cavity.
- **Back floor.** It stands 0.4 mm off the board on a perimeter ledge and the gasket ring. The back of the board is flat: GND pour and tented vias only.

## Open until the first print

- Tolerances: the board pocket, the screw pilot, and the flexure's stiffness and travel.
- Whether the gasket ring seals well enough, measured as the level difference with the hole open and taped.
- The case's acoustic effect on the reading. The hand-held calibration from the firmware bring-up is done **in the case**.

## Files and printing

| File | What |
|---|---|
| `make_case.py` | The source: a FreeCAD script that builds both shells from `board_geometry.json`, checks fit and exports |
| `dbfob-case-back.stl` / `.step` | Back shell in print orientation, floor on the bed: 33.8 × 60.6 × 4.0 mm |
| `dbfob-case-front.stl` / `.step` | Front shell in print orientation, top on the bed: 33.8 × 60.6 × 5.7 mm |

Neither shell needs supports. The light tubes and the button nub print upwards from the front's top face, and the screw counterbore opens onto the bed.

Suggested print settings: 0.4 mm nozzle, 0.2 mm layers (0.12 mm for the front, so the LED windows and flexure slot come out cleanly), PETG or PLA, 4 perimeters.

Hardware: one M2 × 8 pan-head thread-forming screw, or a plain M2 × 8 with a Ø3.2 heat-set insert. For the insert, set `SCREW_PILOT = 3.2` and re-export.

Fit check on rev A: the overlap volume of back shell vs board, front shell vs board, front shell vs parts, and front vs back is 0 mm³ in every case.

### Regenerating

Run `make_case.py` in FreeCAD. The script only reads `board_geometry.json` from its own folder. Refresh that file from the board first if the layout changed; see the git history for the generator snippet.

`export(doc, out_dir)` writes the four files. On this project FreeCAD runs on a desktop with its MCP RPC port reverse-tunnelled to the dev machine. The exports come back with `scp -i ~/.ssh/id_free`, and are checked by SHA-256 against the desktop copies.
