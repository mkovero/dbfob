# B1 (rev B)

30 × 26 mm, 2 layers: rev A's metering at half the size, with the log readable by tapping a phone. Scope and part choices are in [docs/rev-b.md](../../docs/rev-b.md#b1-target).

![top render](production/render-top.png)

**Status: drafted 2026-11-03, not ordered.** It goes in the same order as the [NFC test board](../nfc-test/README.md), which carries the identical antenna. The trim value found on the test board goes onto B1's C1/C2.

## What's on it

- **Coil round the edge**, the tag U1 and trim pads C1/C2 inside the bottom turns: [../lib/antenna.py](../lib/antenna.py), shared with the test board. 6 turns, 0.25 mm track with a 0.2 mm gap, about 2.1 µH in air (NXP AN11276). The outer end drops to B.Cu at VO, crosses under the turns and comes back up at VI.
- **Back:** CR2032 in a MYOUNG BS-08-B2AA001, hand-fitted. A ferrite sheet goes on the holder floor under the cell (see the test board's bench steps).
- **Top, inside the coil:** CH32L103 in the middle, the mic at the top centre, the LED bar and the button on the right, programming pads at the right edge.
- **No ground pour.** Copper inside the loop detunes it, so GND is tracks. B.Cu under the coil is kept clear apart from the crossover.

| Ref | What | Note |
|---|---|---|
| U2 | CH32L103F8U6, C22467836 | QFN-20 3 × 3. No NRST pin, BOOT0 tied low inside |
| MK1 | IM66D130M, C52053030 | **0 JLC stock: global sourcing.** 0.5 mm port (NPTH) through the board, clear of the holder |
| U1 | NT3H2111W0FHKH, C710403 | NTAG I2C plus 1k, powered from PB0 |
| C1, C2 | 0603 trim, **not fitted** | C0G, value from the NFC test board |
| C3, C4, C6 | 100 nF | tag, MCU and mic decoupling |
| C5 | 10 µF | bulk |
| R1, R2 | 4.7 kΩ | SDA / SCL pull-ups to NFC_VCC |
| R3 | 100 kΩ | FD pull-up to the cell |
| R8 | 1 MΩ | button pull-up |
| D1–D4, R4–R7 | as rev A | D4's cathode on PA10 for ambient-light sensing |
| SW1 | TS-1187A, C318884 | measure button |
| BT1 | BS-08-B2AA001 (C964777) | **hand-fit on the back** |
| J1 | four 1.2 mm pads, 2.54 mm | `D C G +` = SWDIO, SWCLK, GND, VBAT for a WCH-LinkE pogo clip |

**MCU pins** (full table in `tools/gen_sch.py`):

| Pin | Net | | Pin | Net |
|---|---|---|---|---|
| 5 PA4 | MIC_VDD | | 12 PB14 | LED_G (TIM1_CH2N) |
| 6 PA5 | MIC_CLK (SPI1 SCK) | | 13 PB15 | LED_Y (TIM1_CH3N) |
| 20 PA6 | MIC_DATA (SPI1 MISO) | | 14 PA8 | LED_O (TIM1_CH1) |
| 7 PA7 | FD (wakes Standby) | | 15 PA9 | LED_R (TIM1_CH2) |
| 8 PB0 | NFC_VCC | | 18 PA10 | LED_R_K |
| 9 PB10 | SCL (I2C2) | | 17 PA13 | SWDIO |
| 10 PB11 | SDA (I2C2) | | 16 PA14 | SWCLK |
| 11 PB13 | BTN (wakes Standby) | | 1–4 | spare |

- Pins sharing a pad inside the chip (PB1/PB10, PB6/PB13, PA10/PB7): only one of each pair may drive. PB6 and PB7 are the Type-C CC pins. Some lots force CC1's 5.1k pull-down on in Standby, which costs about 3 µA through R8, only on those lots.
- LED_R and LED_G share TIM1 CH2's compare, so one of the two runs on software PWM.
- No UART: printf goes over SWDIO (ch32fun).

## Regenerate

```sh
python3 hardware/lib/gen_lib.py          # symbols, IM66D130M + pad footprints
python3 hardware/b1/tools/gen_sch.py     # tables -> schematic
python3 hardware/b1/tools/make_pcb.py    # antenna + placement + hand GND vias, the router does the rest
python3 hardware/b1/tools/fab.py         # -> production/
```

Same procedure as rev A ([../README.md](../README.md)). Routing is signals first, then GND and VBAT, with the router's `mps` net ordering.

**State at commit:**
- **ERC:** clean, apart from the library-table warnings and the two GPIO-driven supplies (MIC_VDD, NFC_VCC), whitelisted as rev A's.
- **DRC:** 0 errors, 0 unconnected, 0 parity issues.
- **Repeatability:** two runs give byte-identical boards.
- **CPL:** 19 of 20 placements checked against JLC's EasyEDA footprints. MK1 has no EasyEDA footprint: check its rotation in JLC's DFM preview.

## Before ordering

- Re-check CH32L103F8U6 stock (708 at JLC on 2026-11-03) and source the IM66D130M.
- **ENIG finish:** the mic's pads are NSMD.
- No keyring hole in the PCB: the case carries it.
- Fit C1/C2 with the value found on the test board.
