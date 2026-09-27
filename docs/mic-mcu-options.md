# Microphone and MCU options

Roadmap item: *Pick MCU + mic, breadboard, verify A-weighted LAeq against a reference meter.*

Prices are LCSC / DigiKey list prices seen in September 2026, in USD. Check them again before ordering.

## Decision (2026-09-27)

- **Digital (PDM) microphone.** Analog is ruled out; see the cost and calibration comparison below.
- **AOP ≥ 130 dB SPL is a hard requirement.** 120 dB parts, including the cheap MSM261D series and the I2S hobby modules, are out. The firmware still flags clipping, but only as a sanity check, not as a crutch.
- **Microphone: Infineon IM69D130.** AOP 130 dB SPL in *all* clock modes, including 768 kHz. −36 dBFS ±1 dB. Runs at 1.62–3.6 V, straight from a CR2032. About $1.38 at 1k.
  - Second source: **TDK T5818**. It is 1.65–3.63 V and ±1 dB, but it reaches 135 dB AOP only in high-quality mode (clock 2.0–3.3 MHz). Its low-power mode (400–800 kHz) drops to 120 dB. So on the T5818, firmware must run the clock at ≥2.048 MHz and decimate by 128. Keep the decimator's clock rate and decimation ratio configurable so either mic works.
- **MCU: WCH CH32V002.** Fall back to the CH32V006 if the internal op-amp or extra RAM is ever needed; it is pin-compatible. Not the CH32V003: it has no multiply and a 2.7 V minimum supply.
- PDM is read through SPI+DMA, with software CIC/FIR decimation to 16 kHz.

The survey below is kept for the record.

## Microphones

| Part | Type | AOP (dB SPL) | Sensitivity | VDD | Price | Notes |
|---|---|---|---|---|---|---|
| Goertek S15OT421-005 and similar | Analog | not checked (~120 typ.) | −38…−42 dBV, ±3 dB typ. | – | ~$0.09 | Also needs an op-amp (~$0.08) and passives, so ~$0.20 for the chain |
| TDK ICS-40618 | Analog, differential | **132** | ±1 dB | – | ~$1.80 (DigiKey qty 1) | Differential output, needs a real front end |
| MEMSensing MSM261DDB020 / DHT006 / DGT003 | PDM | 120 | −26 dBFS ±1 dB | 1.6–3.6 V | **$0.29–0.47** @1k, $0.58 qty 1 | 670 µA @ 2.4 MHz, 290 µA @ 768 kHz |
| **Infineon IM69D130** | PDM | **130** (<1 % THD to 128) | −36 dBFS ±1 dB | 1.62–3.6 V | ~$1.38 @1k, ~$2–3 qty 1 | 768 kHz / 1.536 / 2.4 / 3.072 MHz modes; the datasheet mentions "discotheque" as a use case |
| TDK T5818 | PDM | 135 (HQ mode) | ±1 dB | check | ~$1.2 @10k | Good parametric fallback |
| TDK T5838 | PDM | 133 (HQ mode) | −41 dBFS ±1 dB | **1.65–1.98 V** | $2.83 qty 1, $1.18 @10k | Needs an LDO. Poor fit for a coin cell |
| INMP441 / SPH0645 / ICS-43434 modules | I2S | ~120 | ±1 dB | 1.8–3.3 V | $1–2 module | Hobby favourites. I2S needs I2S hardware, so they don't fit the cheap MCUs |

### What AOP means for this device

The top band starts at 108 dBA LAeq. A bass-heavy room at that level can have unweighted peaks of 120–125 dB SPL, so a 120 dB AOP part clips in exactly the region where the answer matters most.

That can be handled in firmware. With a digital mic, clipping shows up exactly as full-scale samples after decimation. If more than a few samples in the window clip, the firmware shows **red**. The error then always points toward warning: a very bassy 104 dBA room may read red instead of orange, but a genuinely red room never reads orange.

- **130+ dB AOP part (IM69D130):** correct bands everywhere. Costs ~$1 more.
- **120 dB AOP part (MSM261D):** correct up to orange, and the red band may show more often than it should. Costs ~$0.30.

Measure this on the breadboard (see [Next steps](#next-steps)) before choosing between them.

## Analog vs digital: the price difference and what it means

### Cost

| | Analog | Digital (PDM) |
|---|---|---|
| Cheap tier | mic $0.06–0.09 + op-amp $0.08 + ~6 passives ≈ **$0.20** | mic ≈ **$0.30** + 1 decoupling cap |
| High-AOP tier | ICS-40618 $1.80 + front end | IM69D130 $1.38 |
| Board area / assembly | op-amp, gain network, bias, maybe 2 gain stages | 4 wires: VDD, GND, CLK, DATA (L/R tied) |

The difference is about **$0.10 at the cheap end and nothing at the high end.** It is the one place where spending a little more makes the device simpler.

### Calibration

Error sources in the analog chain, all of which add up per unit:

1. **Mic sensitivity:** ±3 dB on the $0.09 parts.
2. **ADC reference = VDD.** Cheap MCUs reference the ADC to the supply. A CR2032 sags from 3.0 V to about 2.2 V over its life, which moves the reading by `20·log10(3.0/2.2) ≈ 2.7 dB`. This can be fixed by measuring VDD against the internal bandgap on every press, but the bandgap is itself only accurate to a few percent.
3. **Dynamic range.** A 12-bit ADC gives 8–10 effective bits (~50–60 dB). Covering 80–130 dB SPL takes careful gain staging or two switchable gain ranges, and each range then needs its own calibration offset.
4. **Resistor and op-amp tolerance:** small, about 0.1–0.2 dB with 1 % parts.

With a PDM mic, error sources 2–4 go away. The mic's output is already digital, relative to its own full scale, and does not depend on the supply voltage. The IM69D130's ~105 dB dynamic range covers everything in one range. The only per-unit variable left is sensitivity, at **±1 dB**.

In practice, the colour bands are 6–7 dB wide:

- **Analog:** ±3 dB mic plus ±1–3 dB chain error. Every unit needs the substitution calibration from the README, stored in flash. That is a bench step per fob, which is the real cost at 1000 units.
- **Digital ±1 dB:** calibrate a *batch* instead. Characterise a few units for the hand-held offset and the frequency response, then flash the same constant into every unit. You can spot-check a sample from each reel.

The README's "calibration anyone can repeat" goal gets much easier. The procedure becomes a check that confirms a unit is within spec, not a step every unit must go through.

## MCUs

What the MCU has to do: run SPI with DMA as the PDM clock master (MISO = DATA), decimate 1-bit PDM at 768 kHz–1.024 MHz down to 16 kHz, run three A-weighting biquads, sum squares for 3 s, then drive one LED. Byte-wise lookup-table CIC/FIR decimation (ST AN5027 / OpenPDMFilter style) costs roughly a few percent of a 24–48 MHz core. A hardware multiplier matters for the biquads.

| Part | Core | Hardware multiply | VDD min | SPI+DMA | Price | Notes |
|---|---|---|---|---|---|---|
| **CH32V002** | RV32EmC 48 MHz, 16K/4K | **yes** | **2.0 V** | yes | ~$0.10–0.15 | 12-bit 3 Msps ADC, pin-compatible with V003, QFN12…TSSOP20. Tooling: WCH-LinkE (~$4), ch32fun |
| CH32V006 | RV32EmC 48 MHz | yes | ~2.0 V | yes | ~$0.14–0.26 | Adds an internal op-amp (would matter only for an analog mic) |
| CH32V003 | RV32EC 48 MHz | **no** | 2.7 V | yes | ~$0.10 | No multiply, and dies well before the coin cell is empty. Skip it |
| PY32F002A/003 | Cortex-M0+ 24–32 MHz | yes | 1.7 V | yes | ~$0.08–0.15 | Cheapest and best low-voltage range. Thinner docs and toolchain |
| **STM32C011** | Cortex-M0+ 48 MHz | yes | 2.0 V | yes, plus I2S | ~$0.30–0.70 | Best docs (AN5027 covers PDM over SPI), any ST-Link, NUCLEO-C031C6 dev board. I2S also opens up the I2S mic modules |

**Pick: CH32V002.** It is cheap, has a hardware multiply, runs down to 2 V, and its toolchain and programmer are cheap and widely used by hobbyists. Firmware written for the V002 ports to the V006 or PY32 with little change. If the WCH ecosystem gets in the way during bring-up, move to the STM32C011: it costs ~$0.30 more and has the easiest debugging.

Power: with the mic at ~0.3–1 mA plus the MCU at a few mA for about 3 s per press, each press uses well under 0.01 mAh. A CR2032 (~220 mAh) is limited by self-discharge and the MCU's standby current, not by use.

## Estimated BOM (digital path, 1k qty)

| Item | Cheap | High-AOP |
|---|---|---|
| Mic | MSM261D $0.30 | IM69D130 $1.38 |
| MCU | CH32V002 $0.12 | CH32V002 $0.12 |
| RGB LED | $0.03 | $0.03 |
| Switch, caps, resistors | $0.05 | $0.05 |
| CR2032 holder | $0.05 | $0.05 |
| CR2032 cell | $0.10 | $0.10 |
| PCB | ~$0.10 | ~$0.10 |
| **Total** | **~$0.75** | **~$1.85** |

**Chosen: the high-AOP column, ~$1.85.** It meets the "under €2 all-in" goal at 1k. "Well under €1 at volume" is not reachable with a 130 dB mic at current prices, because the mic alone is ~$1.2–1.4. Accepted trade-off: correct red band > €1.

## Next steps

1. Order an IM69D130 breakout (Infineon Shield2Go or any PDM breakout), a CH32V002 dev board and a WCH-LinkE. Optionally add a few T5818s on an adapter to validate the second source.
2. Bring up PDM over SPI at 1.024 MHz, decimate by 64 to 16 kHz, and implement A-weighting and LAeq.
3. Compare against a reference meter with pink noise at 85–115 dBA and with bass-heavy music. Confirm there is no clipping at club levels and measure the hand-held offset.

## Sources

- IM69D130 datasheet (Infineon): sensitivity −36 ±1 dBFS, AOP 130 dB SPL, VDD 1.62–3.6 V, clock modes
- [T5818 datasheet](https://media.digikey.com/pdf/Data%20Sheets/TDK%20PDFs/MMICT5818-00-012_DS.pdf): VDD 1.65–3.63 V, AOP 135 (HQ, 2.0–3.3 MHz) / 120 (LP, 400–800 kHz)
- MSM261DDB020 datasheet (LCSC C27636198): −26 ±1 dBFS, AOP 120 dB SPL, VDD 1.6–3.6 V
- [LCSC MSM261DHT006](https://www.lcsc.com/product-detail/C51928215.html) price breaks
- [DigiKey T5838](https://www.digikey.com/en/products/detail/tdk-invensense/MMICT5838-00-012/16903860), [T5818 highlight](https://www.digikey.com/en/product-highlight/i/invensense/t5818-pdm-microphone)
- [TDK ICS-40618](https://invensense.tdk.com/products/analog/ics-40618/)
- [Hackaday: audio input for 20 cents](https://hackaday.io/project/194511-1-dollar-tinyml/log/227784-audio-input-for-20-cents-usd) (analog chain costing)
- [CNX: CH32V002](https://www.cnx-software.com/2024/05/29/wch-ch32v002-32-bit-risc-v-mcu-comes-with-4kb-sram-supports-2v-to-5v-dc-supply-voltage/), [LCSC CH32V006](https://www.lcsc.com/product-detail/C52753342.html)
- [LCSC STM32C011F4P6](https://www.lcsc.com/product-detail/C5452432.html)
- [ST AN5027: PDM mics on STM32 over SPI](https://www.st.com/resource/en/application_note/dm00380469-interfacing-pdm-digital-microphones-using-stm32-mcus-and-mpus-stmicroelectronics.pdf)
