# B1 (rev B)

A stick, 10.5 × 76.5 × 1.0 mm, 4 layers, with the mic at the tip and one AAA cell on the back: rev A's metering, with the log readable by tapping a phone. Scope and part choices are in [docs/rev-b.md](../../docs/rev-b.md#b1-stick-aaa-instead-of-cr2032-decided-2026-11-09).

![top render](production/render-top.png)

**Status: redrawn as the AAA stick on 2026-11-09, not ordered.** The first draft (2026-11-03) was a 30 × 26 mm CR2032 board. The [NFC test board](../nfc-test/README.md) shares its antenna, outline and cell but was dropped from the order on 2026-11-12: B1 finds its own trim (see [On the bench](#on-the-bench-nfc)).

## What's on it

Along the stick from the tip:

- **The tip, 24 mm:** the NFC coil, from [../lib/antenna.py](../lib/antenna.py), shared with the (unordered) test board. It has 9 turns of 0.15 mm track with a 0.15 mm gap, about 2.25 µH in air (NXP AN11276). The mic MK1 sits inside it, with its port through the board, and C6/R8 sit beside it. The coil's inner end meets LB at net tie NT1; LB crosses under the turns on B.Cu.
- **Just past the coil:** the tag U1, trim pads C1/C2 and C3.
- **The middle:** the tag's pull-ups, the LED bar (LED at the top edge, its resistor below, at 1.5 mm pitch with only the cathode bar in silk), then the button SW1 about mid-stick (x 42.3 of 76.5), where a thumb finds it while the far end rests in the hand. Then the Tag-Connect footprint J1, **pads on the back**, under the cell, so a sweaty thumb can't touch them; its guide and clip holes go through the board in the gap between the two contacts' base pads. Then the MCU U2, still in that gap, so its vias have room all round, and right after it the boost converter U3, with L1 over it and C5 under it, so the switching and output loops stay on F.Cu (hand-drawn). It sits over the + contact's base pad: its VCELL via goes into that pad, the rest of its vias above and below it.
- **The far end:** a 2.7 × 3.1 mm ring slot H1 in the corner, past the + contact's plate, for hanging the stick up. It's 0.5 mm clear of the contact's foot pad (a slot counts as board edge), with 0.75 mm of web to the side and 0.9 mm to the end. The board's name is on the back silk, under the coil.
- **Back:** the AAA cell between two MYOUNG MY-AAA-07 spring contacts, hand-fitted, + towards the far end. Everything past the coil sits under the cell.
- **No planes or pours on any layer.** Copper near the loop detunes it, so GND is tracks. Every layer under the coil is kept clear, apart from a band at its cell end where LB and the mic's nets cross under the turns.

**Why 4 layers:** two would not route in 10.5 mm. The MCU's fan-out, the tag's lines and the mic's lines share one corridor, and the contacts' pads fill the middle of B.Cu. The inner layers carry signals only.

| Ref | What | Note |
|---|---|---|
| U2 | CH32L103F8U6, C22467836 | QFN-20 3 × 3. No NRST pin, BOOT0 tied low inside |
| U3 | TLV61220DBVR, C111811 | boost, 0.7 V start-up, 3.0 V out (R9 1 MΩ / R10 200 kΩ); EN to the cell, always on |
| L1 | MPL2016S4R7MHT, C98335 | 4.7 µH, 2.0 × 1.6 mm, multilayer |
| C5, C7 | 10 µF | boost output, input |
| MK1 | IM66D130M, C52053030 | **20 at JLC on 2026-11-09** (0 on 2026-11-03): order early. 0.5 mm port (NPTH) through the board, inside the coil |
| R8, C6 | 100 Ω, 1 µF (C15849) | mic supply from PA4, filtered against the boost's burst ripple |
| U1 | NT3H2111W0FHKH, C710403 | NTAG I2C plus 1k, powered from PB14 |
| C1, C2 | 0603 trim, **not fitted** | C0G, value found on the bench |
| C3, C4 | 100 nF | tag and MCU decoupling |
| R1, R2 | 4.7 kΩ | SDA / SCL pull-ups to NFC_VCC |
| R3 | 100 kΩ | FD pull-up to VDD |
| D1–D4, R4–R7 | as rev A | each on its own hardware PWM channel; D4's cathode on PA10 for ambient-light sensing |
| SW1 | TS-1187A, C318884 | measure button, PA0/WKUP to VDD: no resistor |
| BT1 | 2 × MY-AAA-07 (C6937109) | **hand-fit on the back**, so JLC assembly stays one-sided |
| H1 | 2.7 × 3.1 mm NPTH slot | ring / cord slot in the far corner; a light split ring is fine, but a heavy key bunch should hang from the case |
| J1 | Tag-Connect TC2050-IDC footprint (KiCad stock `TC2050-IDC-FP`, for the legged plug), no part | 2 × 5 pogo pads at 1.27 mm, 3 guide holes and 4 clip holes (2.4 mm), **on the back**, along the stick between the button and the MCU, its holes in the gap between the contacts' base pads, 0.4 mm clear of the button's body on the front, where the clips latch. ARM Cortex 10-pin pinout: 1 VDD (VTref), 2 SWDIO, 4 SWCLK, 6 TX (SWO slot: the dB stream), 3/5/9 GND; 7, 8, 10 not connected (no NRST pin) |

**MCU pins** (full table in `tools/gen_sch.py`):

| Pin | Net | | Pin | Net |
|---|---|---|---|---|
| 1 PA0 | BTN (WKUP: wakes Standby on a rising edge) | | 7 PA7 | VCELL (ADC7: the cell, for the low-battery lockout) |
| 2 PA1 | LED_O (TIM2_CH2) | | 8 PB0 | FD (EXTI) |
| 3 PA2 | LED_Y (TIM2_CH3) | | 9 PB10 | SCL (I2C2) |
| 4 PA3 | LED_G (TIM2_CH4) | | 10 PB11 | SDA (I2C2) |
| 14 PA8 | LED_R (TIM1_CH1) | | 12 PB14 | NFC_VCC |
| 18 PA10 | LED_R_K | | 15 PA9 | TX (USART1) |
| 5 PA4 | MIC_PWR (through R8 to MIC_VDD) | | 17 PA13 | SWDIO |
| 6 PA5 | MIC_CLK (SPI1 SCK) | | 16 PA14 | SWCLK |
| 20 PA6 | MIC_DATA (SPI1 MISO) | | 11, 13 | spare (PB13, PB15) |

- **Button on WKUP.** With EWUP set, PA0 is forced to an input with pull-down in Standby, so the button goes to VDD and needs no resistor. Not PB13: it shares a pad with PB6 = CC1, and some lots force CC1's 5.1 kΩ pull-down on in Standby (datasheet table 3-8-1 note 3). For the same reason NFC_VCC is on PB14, not PB13.
- Pins sharing a pad inside the chip (PB1/PB10, PA10/PB7, PA11/PA13, PA12/PA14): only one of each pair may drive. Keep CC2_PD off, or PA10 gets 5.1 kΩ to ground.
- **Power.** The boost runs all the time, and the MCU's Standby sets the floor: about 0.5 µA into the converter, 5 µA at its output and 2.5 µA in the divider. VCELL (0.9–1.8 V) is always under VDD, so PA7 reads it directly. It is the boost's input node, with the inductor's ripple on it and no RC filter: average many ADC samples, or take them while the converter idles.
- **Programming and calibration.** A legged TC2050-IDC cable on J1 from the back (with **the cell out**): its clips latch through the board and hook on the front, beside the button. The probe powers the board through pin 1. A probe that drives pin 1 (VTref) at 3.3 V powers VDD past the converter, which doesn't feed back into the cell. A sense-only probe (J-Link, ST-Link) just reads the boost's 3.0 V. 
- **Firmware notes:** PA4 is also SPI1_NSS (use SSM=1, SSOE=0). Set PB2 (no pin on this package) as a pull-down input in low power. Turn I2C2 off and set SDA/SCL to analog before dropping NFC_VCC. Likewise set MIC_CLK/MIC_DATA (PA5/PA6) low or analog before PA4 drops MIC_PWR: a high clock would feed the mic's supply through its ESD diode and sink about 20 mA through R8 into PA4. PA0 (BTN) has no series resistor: never drive it as an output, or a press shorts VDD into it.

**Not yet shown on the bench:**
- Waking Standby by an EXTI event on FD (PB0). The reference manual says any EXTI event wakes Standby, but no example does it. If it doesn't work, FD wakes from Stop (about 4.5 µA) instead.
- R3 (100 kΩ) against the tag's FD leakage (10 µA max). Measure FD current with NFC_VCC off (PB0 as an analog input, meter in series with R3 or across it); keep 100 kΩ only if it is well under 1 µA.
- The boost's ripple at the mic, and the converter's real standby draw from an AAA.

## On the bench: NFC

Experiment 4 runs here (the test board was dropped). The tag runs from the phone's field, so it needs no firmware for steps 1–3.

1. **No cell, C1/C2 empty.** Tap with an Android (NXP TagInfo) and an iPhone; write a URL with NFC Tools. Note the read distance.
2. **Find the resonance.** With a NanoVNA and a small pickup loop, read the S11 dip f0; trim **C = 50 pF × ((f0 / 13.56 MHz)² − 1)** in C1 (C0G). Without a VNA, try 0, 4.7, 10, 15 and 22 pF and keep the longest read distance.
3. **Fit the cell** (alkaline and lithium AAA) and repeat 1–2: the cell's effect. The value from here (or in the case) goes on every board.
4. **Locked iPhone:** with the screen on, a tap should open the URL with no app.

## Regenerate

```sh
python3 hardware/lib/gen_lib.py          # symbols, IM66D130M, AAA contact + pad footprints
python3 hardware/b1/tools/gen_sch.py     # tables -> schematic
python3 hardware/b1/tools/make_pcb.py    # antenna + placement + hand vias, the router does the rest
python3 hardware/b1/tools/fab.py         # -> production/
```

Same procedure as rev A ([../README.md](../README.md)). Routing is signals first, then GND, VDD and VCELL, with the router's mps ordering, backward direction and `--via-proximity-cost 0`. At the default (tenfold via cost near pads), the MCU's bottom pins never drop to the inner layers. Drawn by hand before routing: the boost's SW, GND and VDD loops, U2's decoupling feed (pin 19 up to C4), VCELL to U2's ADC pin (through In2 along the bottom edge, which the router couldn't reach), and LED_R and NFC_VCC out of U2's right column over the + contact's base pad to vias below it. SW and FD (U2's bottom-row pin 8 along the bottom edge to the tag) are drawn whole and kept from the router, which reshapes them anyway; `restore_hand()` puts them back after routing, and a User.2 polygon (KiCadRoutingTools `--keepout`) keeps other nets out of SW's gap. Also by hand: a GND via for C3, boxed in behind the tag's top row, and on the back, a VDD stub from J1 pin 1 out between two clip holes and a GND link between J1's diagonal neighbours 3 and 9. The router doesn't know the 0.25 mm copper-to-hole clearance, so J1's and H1's NPTH pads are grown 0.2 mm while it routes (`restore_npth()`). The router's result swings with small changes: rerun after any placement edit and check that it is still clean.

**State at commit:**
- **ERC:** clean, apart from the library-table warnings and two whitelisted pin-to-pin notes: NFC_VCC, a GPIO-driven supply as on rev A, and PA7 reading the power-flagged VCELL.
- **DRC:** 0 errors, 0 unconnected, 0 parity issues.
- **Repeatability:** two runs give byte-identical boards.
- **CPL:** 24 of 25 placements checked against JLC's EasyEDA footprints. U3 (SOT-23-6) needs a 180° correction, which fab.py applies. MK1 has no EasyEDA footprint: check its rotation in JLC's DFM preview.

## Before ordering

- Stock on 2026-11-10: CH32L103F8U6 119 (708 on 11-03, 481 on 11-09: falling fast), TLV61220 10 665, IM66D130M 20, MY-AAA-07 3 594. Recheck the MCU and the mic on order day.
- Extended parts (JLC setup fee each): D1–D3, L1, MK1, U1, U2, U3. The rest are Basic.
- **ENIG finish:** the mic's pads are NSMD (0.05 mm mask clearance on them).
- **Check JLC's DFM preview** for the mic: its rotation, and that the copper ring round the 0.5 mm port isn't trimmed (JLC may remove thin copper rings at NPTHs).
- 4 layers at 1.0 mm.
- U2's GND via sits in the exposed pad, between the paste windows: expect a little solder wicking.
- Only a small ring slot (H1) in the PCB: a keyring with keys goes on the case. J1's 2.4 mm clip holes can take locating pegs from the case's front half; on the back they're under the cell, so pegs from that side must stop short of it.
- No reverse-cell protection: a reversed AAA puts −1.5 V on the TLV61220 (abs. min −0.3 V). The case must key the cell's direction.
- Assemble a few boards: one becomes the antenna unit for the trim search below.
