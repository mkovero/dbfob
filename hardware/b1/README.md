# B1 (rev B)

30 × 26 mm, 2 layers: rev A's metering at half the size, with the log readable by tapping a phone. Scope and part choices are in [docs/rev-b.md](../../docs/rev-b.md#b1-target).

![top render](production/render-top.png)

**Status: drafted 2026-11-03 and revised after an independent review the same day, not ordered.** It goes in the same order as the [NFC test board](../nfc-test/README.md), which carries the identical antenna. The trim value found on the test board goes onto B1's C1/C2.

## What's on it

- **Coil round the edge**, the tag U1 and trim pads C1/C2 inside the bottom turns: [../lib/antenna.py](../lib/antenna.py), shared with the test board. 6 turns, 0.25 mm track with a 0.2 mm gap, about 2.1 µH in air (NXP AN11276). The outer end drops to B.Cu at VO, crosses under the turns and comes back up at VI.
- **Back:** CR2032 in a MYOUNG BS-08-B2AA001, hand-fitted. A ferrite sheet goes on the holder floor under the cell (see the test board's bench steps).
- **Top, inside the coil:** CH32L103 in the middle, the button and the LED bar on the left, the mic at the top right, programming pads at the right edge. The mic port sits 1.5 mm outside the cell's rim, so it opens beside the holder, not into the slot under the cell.
- **No ground pour.** Copper inside the loop detunes it, so GND is tracks. B.Cu under the coil is kept clear apart from the crossover.

| Ref | What | Note |
|---|---|---|
| U2 | CH32L103F8U6, C22467836 | QFN-20 3 × 3. No NRST pin, BOOT0 tied low inside |
| MK1 | IM66D130M, C52053030 | **0 JLC stock: global sourcing.** 0.5 mm port (NPTH) through the board, clear of the holder |
| U1 | NT3H2111W0FHKH, C710403 | NTAG I2C plus 1k, powered from PA7 |
| C1, C2 | 0603 trim, **not fitted** | C0G, value from the NFC test board |
| C3, C4 | 100 nF | tag and MCU decoupling |
| C6 | 1 µF, C15849 | mic decoupling (IM66D130M datasheet, table 5 note 2) |
| C5 | 10 µF | bulk |
| R1, R2 | 4.7 kΩ | SDA / SCL pull-ups to NFC_VCC |
| R3 | 100 kΩ | FD pull-up to the cell |
| D1–D4, R4–R7 | as rev A | each on its own hardware PWM channel; D4's cathode on PA10 for ambient-light sensing |
| SW1 | TS-1187A, C318884 | measure button, PA0/WKUP to VBAT: no resistor |
| BT1 | BS-08-B2AA001 (C964777) | **hand-fit on the back** |
| J1 | five 1.2 mm pads, 2.54 mm | `D C G + T` = SWDIO, SWCLK, GND, VBAT, TX: WCH-LinkE pogo clip + the dB stream |

**MCU pins** (full table in `tools/gen_sch.py`):

| Pin | Net | | Pin | Net |
|---|---|---|---|---|
| 1 PA0 | BTN (WKUP: wakes Standby on a rising edge) | | 7 PA7 | NFC_VCC |
| 2 PA1 | LED_O (TIM2_CH2) | | 8 PB0 | FD (EXTI) |
| 3 PA2 | LED_Y (TIM2_CH3) | | 9 PB10 | SCL (I2C2) |
| 4 PA3 | LED_G (TIM2_CH4) | | 10 PB11 | SDA (I2C2) |
| 14 PA8 | LED_R (TIM1_CH1) | | 15 PA9 | TX (USART1) |
| 18 PA10 | LED_R_K | | 17 PA13 | SWDIO |
| 5 PA4 | MIC_VDD | | 16 PA14 | SWCLK |
| 6 PA5 | MIC_CLK (SPI1 SCK) | | 11–13 | spare |
| 20 PA6 | MIC_DATA (SPI1 MISO) | | | |

- **Button on WKUP.** With EWUP set, PA0 is forced to an input with pull-down in Standby, so the button goes to VBAT and needs no resistor. The first draft had it on PB13 with a 1 MΩ pull-up. PB13 shares a pad with PB6 = CC1, and some lots force CC1's 5.1 kΩ pull-down on in Standby (datasheet table 3-8-1 note 3), which would have held BTN low for good.
- Pins sharing a pad inside the chip (PB1/PB10, PA10/PB7, PA11/PA13, PA12/PA14): only one of each pair may drive. Keep CC2_PD off, or PA10 gets 5.1 kΩ to ground.
- **Firmware notes:** PA4 is also SPI1_NSS (use SSM=1, SSOE=0). Set PB2 (no pin on this package) as a pull-down input in low power. Turn I2C2 off and set SDA/SCL to analog before dropping NFC_VCC.

**Not yet shown on the bench:**
- Waking Standby by an EXTI event on FD (PB0). The reference manual says any EXTI event wakes Standby, but no example does it. If it doesn't work, FD wakes from Stop (about 4.5 µA) instead.
- R3 (100 kΩ) against the tag's FD leakage (10 µA max). Measure FD current with VCC off on the test board; keep 100 kΩ only if it is well under 1 µA.

## Regenerate

```sh
python3 hardware/lib/gen_lib.py          # symbols, IM66D130M + pad footprints
python3 hardware/b1/tools/gen_sch.py     # tables -> schematic
python3 hardware/b1/tools/make_pcb.py    # antenna + placement + hand vias, the router does the rest
python3 hardware/b1/tools/fab.py         # -> production/
```

Same procedure as rev A ([../README.md](../README.md)). Routing is signals first, then GND and VBAT.

**State at commit:**
- **ERC:** clean, apart from the library-table warnings and the two GPIO-driven supplies (MIC_VDD, NFC_VCC), whitelisted as rev A's.
- **DRC:** 0 errors, 0 unconnected, 0 parity issues.
- **Repeatability:** two runs give byte-identical boards.
- **CPL:** 18 of 19 placements checked against JLC's EasyEDA footprints. MK1 has no EasyEDA footprint: check its rotation in JLC's DFM preview.

## Before ordering

- Re-check CH32L103F8U6 stock (708 at JLC on 2026-11-03) and source the IM66D130M.
- **ENIG finish:** the mic's pads are NSMD (0.05 mm mask clearance on them).
- **Check JLC's DFM preview** for the mic: its rotation, and that the copper ring round the 0.5 mm port isn't trimmed (JLC may remove thin copper rings at NPTHs).
- U2's GND via sits in the exposed pad, between the paste windows: expect a little solder wicking.
- No keyring hole in the PCB: the case carries it.
- Fit C1/C2 with the value found on the test board.
