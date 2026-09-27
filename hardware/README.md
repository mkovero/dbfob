# dbfob hardware, rev A

30 × 52.5 mm, 2 layers, all parts on the top side. It is powered by a CR2032, the only input is one button, and the only output is a four-LED bar. Part choices are explained in [../docs/mic-mcu-options.md](../docs/mic-mcu-options.md).

![top render](production/render-top.png)

## Everything regenerates

The procedure follows `studer-vca/etofab.md`. The tables in `tools/gen_sch.py` are the only source; do not hand-edit the sheet or the board.

```sh
python3 hardware/tools/gen_sch.py    # tables -> dbfob.kicad_sch
python3 hardware/tools/make_pcb.py   # schematic -> placed, routed, poured, DRC'd board (~30 s)
python3 hardware/tools/fab.py        # board -> production/
```

These need KiCad 10 (`kicad-cli` and the `pcbnew` Python module) and [KiCadRoutingTools](https://github.com/drandyhaas/KiCadRoutingTools) at `/home/mui/src/KicadRoutingTools` (override with `KRT=`).

State at commit:
- **ERC:** clean, apart from KiCad's library-table warnings and one expected `pin_to_pin` warning. That warning comes from the PWR_FLAG on MIC_VDD, which is powered by a GPIO.
- **DRC:** 0 errors, 0 warnings, 0 unconnected, 0 schematic-parity issues.
- **Reproducibility:** two runs give byte-identical boards.

## Circuit

| U1 pin | Port | Net | Function |
|---|---|---|---|
| 15 | PC5 | MIC_CLK | SPI1 SCK, the PDM clock (1.024 MHz → decimate by 64 to 16 kHz) |
| 17 | PC7 | MIC_DATA | SPI1 MISO, the PDM data. MK1 SELECT is tied to GND |
| 16 | PC6 | MIC_VDD | GPIO push-pull. The mic is powered only while measuring (≈1 mA); allow ≥50 ms after power-up |
| 20 | PD3 | LED_G | TIM2_CH2, D1 yellow-green |
| 19 | PD2 | LED_Y | TIM1_CH1, D2 yellow |
| 14 | PC4 | LED_O | TIM1_CH4, D3 orange |
| 13 | PC3 | LED_R | TIM1_CH3, D4 red (anode side) |
| 12 | PC2 | LED_R_K | D4 cathode: drive low to light it; reverse-bias and time the decay to sense ambient light |
| 10 | PC0 | BTN | SW1 to GND. Use the internal pull-up; EXTI wakes the MCU from standby |
| 18 | PD1 | SWIO | Programming (WCH-LinkE) |
| 2 | PD5 | TX | USART1 TX: prints dB readings during calibration |

**LEDs.** The bar is deliberately dim: a club is dark and the fob should not light up the room. The resistors cap the current at about 0.45 mA (2.2 kΩ), or about 1 mA for the dimmer yellow-green (1 kΩ). Firmware uses PWM to go well below that indoors and shows the result for about 2 s.
- **Ambient light sensing.** D4's cathode is on PC2 rather than GND, so the red LED doubles as a light sensor. Reverse-bias it (PC3 low, PC2 high), switch PC2 to input, and time how long it takes to read low. Fast means bright, which lets the firmware tell a dark room from daylight.
- **Why these LEDs.** All four are low-Vf AlInGaP/GaP types (1.6–2.6 V), so every colour still lights near the end of the cell's life; InGaN green and blue LEDs need about 3 V.
- **Order.** The bar runs G Y · O R from left to right. The position of the lit LED also encodes the level, so the bar works for colour-blind users.

**J1** is four 2.54 mm pads: `+ D G T` = VBAT, SWIO, GND, TX. Fit a header by hand, or hold pogo pins against it. It is not assembled.

**Mic port.** MK1 is a bottom-port mic, so it hears through the 0.8 mm hole to the **back** of the board (marked MIC). Don't cover it, and give the case an opening there.

**Coin cell.** The Keystone 3034 uses a PCB pad as the − contact. The cell's + can wraps around onto the − face at the rim, so the top layer has no copper in the ring under the rim: only solder mask would stand between + and a GND pour. The − pad reaches ground through four vias inside the pad. There is no reverse-polarity protection; the holder only accepts the cell one way round.

## MCU: fitted with a CH32V003

The CH32V002 and CH32V006 had **zero stock at JLC/LCSC on 2026-09-27**, so the BOM carries the pin-compatible **CH32V003F4P6** (C5187096, 1035 in stock). The TSSOP-20 pinout is identical: it was checked against table 2-1 of the V002 datasheet. When stock returns, change the LCSC number in `gen_sch.py`. The board stays the same.

The V003 costs the project two things:
- **No hardware multiply.** Build the firmware for `rv32ec`, which runs on all three chips. The biquads cost more cycles but fit easily at 48 MHz.
- **Minimum supply of 2.7 V instead of 2.0 V.** A CR2032 stays at 2.9–3.0 V for most of its capacity, so the loss is roughly the last 10–15 % of the cell. Firmware should measure VDD against the internal reference and blink "battery low" before the MCU browns out.

## Ordering at JLCPCB

Upload `production/dbfob-gerbers.zip`, then for assembly `production/bom_jlc.csv` and `production/cpl_jlc.csv`.

- **PCB:** 2 layers, 1.6 mm, any colour. ENIG is recommended over HASL. HASL leaves the flat − battery contact bumpy, and the fine-pitch LGA mic solders more reliably on a flat finish.
- **Assembly:** top side only, 15 placements, 12 BOM lines. J1 is not placed. Economic assembly should accept everything; check that it does.
- **Extended parts:** U1, MK1, BT1, D1, D2 and D3 are extended. Each carries JLC's flat per-part setup fee regardless of quantity (etofab.md §7).
- **Low-stock lines to check before paying:**
  - MK1 IM69D130 (C536262): 614 in stock, about $3 each at small quantities.
  - D3 orange KT-0603O (C111340): 3979 in stock.
- **Placement is verified against JLC's own footprints.** JLC places each part with the EasyEDA footprint of its LCSC number. `tools/check_cpl.py` puts those footprints where the CPL says and checks three things: every pad lands on the KiCad pad of the same pin, MK1's port lands on the sound hole, and BT1's opening faces the board edge. `fab.py` refuses to finish if any check fails. The corrections are in `JLC_FRAME` in `fab.py`:
  - U1: +270°.
  - MK1: +90°, and the CPL point moves 0.13 mm, because EasyEDA's origin is not the package centre.
  - BT1: +180°. Its pads are symmetric but the opening is not.
  - LEDs: none. The cathode is on the left in both libraries, even though the pad numbers differ.

  Rev A's first CPL had MK1 turned 90° and BT1 backwards; this check is what caught it. Still glance at JLC's preview before paying.
- **MK1 is a MEMS mic with an open port.** Make sure the board is not water-washed after reflow.

## Not verified yet

This is rev A and no hardware exists. Open items before calling it done:
- The PDM clock rate and decimator on the V003 at 48 MHz without a multiplier.
- The mic's current when powered from a GPIO.
- Standby current, and so the cell's shelf life.
- The hand-held level offset.
