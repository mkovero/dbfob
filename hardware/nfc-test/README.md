# NFC test board (for rev B / B1)

30 × 38 mm, 2 layers. It answers one question before B1 is trusted: **does B1's NFC antenna read on a phone with a CR2032 right behind it, and with what trim?** This is [experiment 4](../../docs/rev-b.md#experiments-before-any-board).

![top render](production/render-top.png)

It goes in the **same order as B1**, so it can't steer B1's layout. B1 copies this antenna and its trim pads exactly. Whatever trim value this board finds goes straight onto B1's pads.

## What's on it

- **Top 30 × 26 mm:** B1's outline and B1's antenna. A 6-turn PCB coil, 0.25 mm track with a 0.2 mm gap, chamfered to clear the 3 mm corners. It is about 2.1 µH in air (NXP AN11276 formula). Nothing sits inside the loop on the top side.
- **Back:** B1's CR2032 holder, MYOUNG BS-08-B2AA001. The holder has its own − spring, so the board under the cell is bare. A ferrite sheet can then lie on the holder floor under the cell, with a slot for the spring. Rev A's Keystone 3034 couldn't take a ferrite, because the cell sits directly on a PCB pad.
- **Tail, 12 mm:**
  - **U1:** NT3H2111 (NTAG I2C plus 1k).
  - **C1/C2:** trim pads (not fitted).
  - **D1:** field LED.
  - **J1:** host header.
  - **JP1:** solder jumper.

| Ref | What | Note |
|---|---|---|
| U1 | NT3H2111W0FHKH, C710403 | VOUT unused |
| C1, C2 | 0603 trim, **not fitted** | C0G, chosen on the bench |
| C3 | 100 nF | VCC decoupling |
| R1, R2 | 4.7 kΩ | SDA / SCL pull-ups to VCC |
| R3 | 10 kΩ | FD pull-up to the cell, as B1 will wake the MCU with it |
| R4, D1 | 1 kΩ, red | lit while a reader's field is on: FD pulls it low, even with VCC off |
| JP1 | solder jumper | bridge to run the tag's I2C side from the cell |
| BT1 | BS-08-B2AA001 (C964777) | **hand-fit on the back**, so JLC assembly stays one-sided |
| J1 | 1×6 2.54 mm, not fitted | `+ G C F D V` = VBAT, GND, SCL, FD, SDA, VCC |

## Regenerate

```sh
python3 hardware/lib/gen_lib.py               # NT3H2111 symbol, XQFN8 + BS-08 footprints
python3 hardware/nfc-test/tools/gen_sch.py    # tables -> schematic
python3 hardware/nfc-test/tools/make_pcb.py   # coil + placement + hand-drawn LA/LB, the router does the rest
python3 hardware/nfc-test/tools/fab.py        # -> production/
```

This follows the same procedure as rev A ([../README.md](../README.md)).

**How the antenna is drawn.** The coil is LA track. Its inner end meets LB through net tie NT1, and LB crosses back under the turns on B.Cu. DRC doesn't check clearance within one net, so `make_pcb.py` builds the turns at a fixed pitch and asserts the 0.2 mm gap itself.

**State at commit:**
- **ERC:** clean, apart from the library-table warnings.
- **DRC:** 0 errors, 0 unconnected, 0 parity issues.
- **Repeatability:** two runs give byte-identical boards.
- **CPL:** all 7 placements checked against JLC's EasyEDA footprints.

## On the bench

1. **No cell, no ferrite.** Tap with an Android (NXP TagInfo) and an iPhone. Write a URL with NFC Tools. Note the read distance, and the distance at which D1 lights.
2. **Find the resonance**, if a NanoVNA and a small pickup loop are at hand. Couple the loop loosely and read the S11 dip, f0. Then the trim is **C = 50 pF × ((f0 / 13.56 MHz)² − 1)**. Without a VNA, try 0, 4.7, 10, 15 and 22 pF C0G in C1, and keep the value with the longest read distance.
3. **Fit the cell, no ferrite.** Repeat steps 1–2. This shows how much the cell costs.
4. **Fit the ferrite:** WE-FSFS-class, 0.1–0.2 mm, cut to a 20 mm disc with a slot for the − spring, on the holder floor. Repeat steps 1–2.
5. **Locked iPhone:** with the screen on, a tap should open the URL with no app.

Record f0, the trim value, the read distance and the LED distance for each of steps 1, 3 and 4. The step 4 trim value goes on B1's pads.

**Why the coil is under 2.75 µH.** 13.56 MHz needs 2.75 µH with the tag's 50 pF (44–56 pF). The coil is short of that on purpose: ferrite raises L, the cell lowers it, and a parallel trim cap can only pull the resonance down.
