# Rev B: directions, checked facts, experiments

Ideas, not a design. Rev A proves that simple metering works on a €2 coin-cell board. This doc collects what rev B could be.

History:
- **2026-10-29:** written as a BLE / LiPo / wireless-charging "medium" fob.
- **Same day, reworked** after three checks:
  - a search of prices and datasheets for the MCU and radio;
  - the same for power and charging;
  - an independent design review (Claude Fable).

The checks corrected several claims of the first draft, including the main reason for picking the nRF52833. Prices are web snapshots from 2026-10-29, in USD unless noted. Many come from aggregator pages, not distributor pages read directly. Re-check before ordering.

## Summary

Two directions are on the table:

| | **B1: "rev A done properly"** | **B2: BLE "pro" fob** |
|---|---|---|
| Idea | Same architecture: coin cell, LEDs, button. Adds NFC tap-to-read, calibration stored in flash, a bootloader, a centred mic port and a clip variant. | nRF54L module, rechargeable cell, live levels and spectrum on a phone. |
| Parts | about $3 | about $12–20 |
| Retail | give-away / €5 | €50–80 |
| Main risks | few | wearing position, iOS, LiPo shelf life, EU removability rule, Qi coupling, certification |

**The review's recommendation, which this doc follows for now:**
- Build B1 next.
- Park B2 until a specific buyer asks for it, such as a venue study, a festival or a band.
- If BLE happens anyway: a certified nRF54L module, a coin cell (CR2450), advertising only, and the live spectrum as a developer tool.
- Run the [experiments](#experiments-before-any-board) first. Most of them run on rev A hardware.

## The design review's main points

1. **B2 contradicts the project's founding sentence.** The README says "nobody pulls out a phone on a dark dance floor". A live spectrum, a web page and phone graphs all need the phone. What carries over without a phone: with continuous or adaptive metering, the LEDs can show **tonight's running dose** at a glance instead of the room right now.
2. **The buyer changes.** A clubgoer doesn't buy a €60 device that tells them to leave. People who would pay mostly own an Apple Watch, whose Noise app does continuous dBA with alerts for free. Certified personal dosimeters (Casella dBadge2, 3M Edge, IEC 61252) cost €600+ and are bought by employers. Etymotic's €50–100 consumer dosimeter (ER-200D) did not survive. The realistic B2 buyer is a venue, festival or study handing out a fleet. They want bulk log readout, not a spectrum.
3. **Wearing position matters more than the MCU.** A pocket reads 10–20 dB low (README, "comforting lie"). Continuous metering in a pocket is meaningless. Real dosimeters clip to the shoulder. A worn fob also hears clothing rub and handling noise. Decide clip vs keyfob first.
4. **A sealed case and a mic port conflict.** Sealing needs an acoustic membrane (Gore, Saati Acoustex): about 0.5–1 dB loss mid-band, more above 8 kHz. The port tube also has its own resonance in the top octaves. Together with the mic's +9/−2 dB at 15 kHz, **full band to 20 kHz is a nice-to-have, not a goal.** Rev A's band limit costs 0.2–0.9 dB on broadband noise and less on music, and A-weighting already discounts the high bands.
5. **The case for continuous metering is weaker than the first draft claimed.** In the test3 club log the dips to 55–75 dBA carry about 0.1 % of the energy. Missing them makes the graph prettier but barely changes the dose. With about 100 samples in 105 min, the sampling error on LAeq is a fraction of a dB. **Adaptive sampling** (continuous above about 80 dBA, 1 s a minute below) should give the same dose on rev A's power budget. Experiment 2 tests this.
6. **LiPo + Qi solve a problem rev A doesn't have.** Rev A has no USB opening either. What the LiPo brings instead: shelf discharge (a 40 mAh pouch behind protection is flat in 6–12 months in a drawer, against 3 years idle on a CR2032), swelling inside a sealed case, transport and safety certification, cold-night capacity loss, and a charging chore. See [Power](#power-checked) for the EU rule and the Qi coupling evidence.
7. **The phone side:**
   - Web Bluetooth doesn't work on iOS, half the audience.
   - A BLE device advertising a fixed address is trackable: use resolvable private addresses.
   - The log is a timeline of where the wearer was, so say what the page stores.
   - Over-the-air updates are one more thing to build.
8. **Claims.** A MEMS mic behind a printed port, with batch calibration and no windscreen, is not IEC 61672 class 2 or IEC 61252. Keep the disclaimer and keep hearing-safety claims modest.

## Alternatives that came out of the review

- **NFC readout without BLE.** An ST25DV dynamic NFC tag chip (I2C, about $0.6, PCB antenna) works with any MCU. The fob writes a dose summary into a URL the tag serves (NDEF record). The 10-minute summary from [log-readout.md](log-readout.md) is about 156 B. iPhone (background tag reading) and Android open the web page with no app and no pairing, **even with the fob's cell dead.** This replaces most of log-readout.md and the BLE readout for both directions.
- **A primary cell, continuous.** A CR2450 (620 mAh, 24.5 mm) is about the footprint of a 30 × 26 mm board. At about 1 mA continuous for 12 h nights that is about 50 nights on a €0.40 cell; a CR2032 gives about 15. All unmeasured.
- **nRF + coin cell, advertising only**, if BLE is wanted for bulk readout. A module plus CR2450 at 10–20 µA advertising keeps rev A's duty cycle and shelf life.
- **Clip, not fob.** Mic on the top edge facing up, spring clip on the back, lanyard hole. The keyfob stays as the spot-check tier.

## MCU and radio (checked)

**First-draft errors corrected here.** The nRF52833's PDM block cannot give 48 kHz, and its REG0 regulator cannot officially power external parts such as the mic. That removes the main reason for choosing it.

| Option | Price | Full-band PDM | LiPo direct | Notes |
|---|---|---|---|---|
| **nRF54L05 / L10 / L15** | L05 $2.12 @1k (Future); L10 $2.29–2.33 @1k; L15 $4.15 @1, $2.73 @100 (Mouser) | **Yes**: 8/16/32/48 kHz listed, ratios 32–128. From 32 MHz the nearest rates are about 47.6 or 50 kHz, fine with matching filters. | No: 1.7–3.6 V, needs an external buck or LDO, which can also feed the mic. | NFC, I2S. TX 0 dBm 4.8 mA, RX 3.4 mA, sleep 0.7–2.9 µA. CSP 2.45 × 2.25 mm, QFN40 5 × 5. **Best nRF choice.** 16-week lead time. |
| nRF52833 | $3.91 @1k (Mouser), $3.25 @1k (Arrow), $2.39 @1k (LCSC, thin stock) | **No**: PDM clock 1.000–1.333 MHz, ratio 64/80, so max 16 kHz output and a band ending near 8 kHz, worse than rev A. Undocumented faster settings are unsupported. | VDDH 1.7–5.5 V, but REG0 is LDO-only, and Nordic and Ezurio say external loads on VDD are not supported. | NFC, FPU. TX 4.8 mA, RX 4.6 mA. System ON with RTC 2.6 µA. |
| nRF52820 | €1.96 @1k (Farnell) | No PDM | VDDH | No PDM, I2S, NFC or FPU. **Not usable.** |
| nRF52810 | about $1.40 @1k (LCSC) | 16 kHz max | No | No NFC or FPU (not checked). |
| TI CC2340R5 / R2 | not found | **No I2S or PDM** | 1.71–3.8 V | Only SPI, UART, I2C. Out. |
| ESP32-H2 / C3 | H2-MINI-1 module $4.08 @1 (Mouser); C3-MINI-1 $5.77 @1, about $4 in volume | **Raw PDM only**: no PDM-to-PCM in hardware (only ESP32, S3, P4 have it). The C6 was not checked. | No: H2 needs 3.0–3.6 V | H2: BLE TX 0 dBm 36 mA, RX 24 mA, light sleep 25–85 µA, deep sleep 7 µA. **Out for a small cell.** |
| WCH CH592 | about $0.5 (not checked) | No PDM: the SPI trick again | | Same vendor family as rev A. Weaker SDK and radio. |

Sources:
- nRF52833 PDM: [nRF52833 PDM spec](https://docs.nordicsemi.com/r/bundle/ps_nrf52833/page/pdm.html), [forum: PDM at higher rates](https://devzone.nordicsemi.com/f/nordic-q-a/15150/single-pdm-microphone-at-higher-pcm-sampling-rate/57839).
- nRF52833 VDD: [forum: external power on VDD](https://devzone.nordicsemi.com/f/nordic-q-a/55545/nrf52833-vdd-external-power/238326), [Ezurio BL653 FAQ](https://www.ezurio.com/support/faqs/does-the-bl653-support-external-circuitry-on-vdd-using-high-voltage-mode).
- [nRF54L15 PDM spec](https://docs.nordicsemi.com/r/bundle/ps_nrf54l15/page/pdm.html), [nRF54L15 product page](https://www.nordicsemi.com/Products/nRF54L15), [nRF52820](https://www.nordicsemi.com/Products/nRF52820), [CC2340R5](https://www.ti.com/product/CC2340R5).
- [ESP-IDF I2S PDM support](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/api-reference/peripherals/i2s.html), [ESP32-H2 datasheet](https://documentation.espressif.com/esp32-h2_datasheet_en.html).

### Modules

- **nRF54L15 modules** ([Nordic list](https://www.nordicsemi.com/Products/nRF54L15/Modules)):
  - u-blox ANNA-B505, 6.5 × 6.5 mm, chip antenna
  - Ezurio BL54L15µ, 6.3 × 7.9 mm
  - Raytac AN54LV-15, 6.4 × 8.4 mm
  - Murata Type2NR, 7.0 × 7.4 mm
  - Insight ISP2454, 8 × 8 mm
  - Only one price found: BL54L15 (the 10 × 14 mm version), about AUD 8.6 at qty 1, AUD 7.1 at 100.
- **nRF52833 modules:**
  - Ezurio BL653µ 453-00059, 6.3 × 8.6 × 1.6 mm with PCB antenna, $8.24 @1k
  - u-blox ANNA-B402, 6.5 × 6.5 mm
  - Insight ISP1907-HT, 8 × 8 × 1 mm, $5.89 at reel
  - Raytac MDBT50Q
  - Ezurio BL653, 10 × 15 mm
- **Module $5–10 holds.** Vendors claim FCC/CE/IC for each module; not checked one by one.

### Certification

- **Chip on our own board:** TI estimates about $30k for certification plus RF equipment and design time, and puts the break-even above 200k units ([TI SLYP865](https://www.ti.com/lit/SLYP865)). Other sources give $10k–100k+. **Realistic: about €10–30k for CE RED and FCC.** The first draft's "several k€" was too low.
- **With a module:**
  - the host still needs RED 3.1(a) safety/EMF and 3.1(b) EMC, plus FCC Part 15B;
  - the antenna must stay within the module grant's conditions;
  - a Bluetooth SIG listing is needed.
  - Typically a few k€; no lab quotes yet ([module vs chip-down](https://punchthrough.com/ble-module-vs-chip-down/)).
- **Conclusion:** module, unless volume runs into the hundreds of thousands.

## Power (checked)

### The EU removability rule

**EU Battery Regulation, Article 11, from 18 Feb 2027:** portable batteries in products must be removable and replaceable by the end user ([summary](https://www.compliancegate.com/removable-and-replaceable-battery-requirements-european-union/)).
- There are exemptions, for example for wet environments.
- A July 2026 delegated act reportedly covers wearables such as smartwatches. Even then, replacement by an independent professional must stay possible ([report](https://en.reach24h.com/news/industry-news/sustainability/eu-portable-battery-removability-exemptions-2026)). Not confirmed in the Official Journal.
- **A sealed case with a built-in LiPo is legally awkward in the EU. A coin cell behind a hatch is not.**

### LiPo pouch cells

The size code is thickness × width × length in mm.

| Cell | Capacity | Price | Notes |
|---|---|---|---|
| 301012 (3 × 10 × 12) | 30 mAh | about $0.85 each in 10-packs (generic) | |
| 401120 (4.2 × 11.5 × 20) | 60 mAh | generic | 30 mA charge (0.5C), protection 4.28 / 3.0 V |
| **402025 (4 × 20 × 25)** | **140 mAh** (Jauch LP402025JU) | branded | **Fits a 30 × 26 mm footprint: 2–3× the first draft's 40 mAh at the same height** |
| Jauch LP501218JH+PCM (5.4 × 12.5 × 20) | 60 mAh | $10.77 @1, $6.38 @720 (Digi-Key) | |

- Branded cells (Jauch, EEMB) cost **5–10× generic** ones. Only branded suppliers reliably provide a **UN 38.3 test summary**, which shipping needs.
- **IATA, from 1 Jan 2026:** cells packed *with* equipment must ship at ≤30 % charge. Cells installed in the equipment are exempt ([Jauch](https://www.jauch.com/blog/en/un-38-3-new-regulations-for-the-air-transport-of-lithium-batteries-from-2026/)).
- A protection board (PCM) adds about 3–5 mm of length.

### Charger and protection

- **TP4054:** about $0.02 (LCSC). Check that a ≤30 mA charge setting is within spec.
- **MCP73831:** 15–500 mA.
- **BQ25100:** suits tiny cells (1 mA termination) but costs about $1.21 (LCSC), and TI shows a newer version.
- **XB5353A:** single-chip protection, $0.046 @3k. Its over-current trip is in the amps, so for a small cell it gives voltage protection only.
- **DW01A + FS8205A:** about $0.1.

### Mic supply

IM69D130: operating 1.62–3.6 V, **absolute maximum 4 V on any pin** (datasheet, Table 3). A LiPo at 4.2 V must never reach the mic. It needs a regulated rail; on the nRF54L, the external regulator gives one.

### Wireless charging

**Qi.**
- **BQ51050B** (TI): Active, Qi 1.2, includes the Li-ion charger. $2.86 @500, $2.61 @3k (Digi-Key). DSBGA-28 or 4.5 × 3.5 mm VQFN. Still **the only verified single-chip Qi receiver plus charger**. Its matching transmitter (bq500212A) is not recommended for new designs, so the platform is ageing.
- **Receiver-only alternatives:** BQ51003 (2.5 W), STWLC38 ($2.35 @2.5k), P9222-R (5 W, not 2.5 W as first written).
- **Coils:**
  - TDK WR202010-18M8-ID: 20 × 0.8 mm, $3.38 @1.
  - Würth 760308101214: 19 × 0.8 mm, about $8 @1.
  - Generic coils at volume may reach $0.5–1.
- **Coupling is the problem.** ST AN4900 says the transmitter coil's outer diameter should be about 1.8–2× the receiver's, with the windings at least partly overlapping. TI notes that small coils lose coupling fast when misaligned ([TI SLYT570](https://ti.com/lit/pdf/slyt570), [ST AN4900](https://www.st.com/resource/en/application_note/an4900-how-to-tune-stevalisb038v1-wireless-charging-evaluation-kit-for-wearable-applications-stmicroelectronics.pdf)).
  - A 20 mm receiver on a standard pad is **marginal**: the pad may not detect it, may treat it as a foreign object, or may charge only when it's centred. No data found showing it works.
  - The first draft's earbud comparison was wrong: earbud *cases* use a 30 mm+ coil, and the buds charge through contacts.
- **Heat:** at 50–60 % efficiency, about 100 mW turns into heat inside a sealed block, next to a cell that must stay under 45 °C while charging.

**NFC wireless charging.**
- **PTX30W is Renesas** (they bought Panthronics), not NXP. Up to **1 W**, with a Li-ion charger at 5–250 mA, WLCSP 1.78 × 1.78 mm ([Renesas](https://www.renesas.com/en/products/ptx30w)). No distributor price found.
- **No phone or pad ships as an NFC wireless charger**; only USI styluses use the NFC Forum standard. So it needs its own charger.

**Fallback:** magnetic pogo pins like a smartwatch, about $0.5 plus a cable.

## Live spectrum over BLE

If B2 happens, BLE is enough, as long as the fob computes the spectrum and sends results.

| What is sent | Rate |
|---|---|
| 1/3-octave bands, 31 × 1 B × 10 fps | about 0.3 kB/s |
| FFT, 256 bins × 1 B × 10 fps | about 2.5 kB/s |
| FFT, 512 bins × 2 B × 20 fps | about 20 kB/s |
| Raw audio, 16 kHz × 16 bit | 32 kB/s |

- BLE 5 with the 2M PHY carries about 50–100 kB/s in practice. A hand or a pocket detunes and blocks a 2.4 GHz antenna: a 1 m link survives, a 20 kB/s stream may not.
- Per the review, treat the live spectrum as a developer tool (or a UART stream on B1), not a headline feature.

## Experiments before any board

1. **Wearing position, on rev A.**
   - Positions: clip on the shoulder, lanyard, shirt pocket, trouser pocket, hand-held.
   - Compare each against the AC2 at 85–100 dBA pink noise and real music.
   - Record the level offset and the high/low band energy ratio.
   - This decides whether continuous metering means anything, and gives a pocket detector its thresholds.
2. **Sampled vs continuous dose.**
   - Record one loud night continuously, with the AC2 or with rev A streaming over UART.
   - Compute the dose from the full record and from 1 s-a-minute subsamples.
   - If they agree within 1 dB, drop continuous metering as a requirement and take adaptive sampling.
3. **Port and membrane sweep.**
   - Print three case variants: bare port, port with an acoustic membrane, short vs long port.
   - Measure the 1/3-octave response from 100 Hz to 20 kHz against the reference.
   - This decides whether a sealed case and full band are compatible, and whether 20 kHz is worth anything.
4. **NFC readout in one evening.**
   - An ST25DV breakout (or an nRF54L DK) with the dose summary in a tag URL.
   - Tap with an iPhone and an Android, and confirm the page opens with no app.
   - This decides the readout for both directions.
5. **Only if Qi stays:**
   - A cheap receiver module with a 20 mm coil, on three common pads, inside a closed printed box with a thermocouple on the cell.
   - Does the pad accept it, at what current, at what temperature?

Bonus if going nRF anyway: an nRF54L15 DK plus an IM69D130 breakout. Run PDM at about 3 MHz into about 48 kHz with the CPU asleep, and measure continuous and advertising-only current. That replaces the runtime guesses with numbers.

## Open questions

- Clip or keyfob, or both as two tiers: after experiment 1.
- Continuous, adaptive or sampled: after experiment 2.
- CR2032, CR2450 or LiPo. The EU rule and shelf life favour coin cells.
- B1's MCU: a CH32V00x with a hardware multiplier (CH32V006?) in stock, and whether its SPI reaches a 3 MHz mic clock for full band.
- Not yet verified: CC2340 price; nRF52833 WLCSP price; ESP32-C6 PDM; nRF54L module prices; PTX30W price; TP4054 at ≤30 mA; Bluetooth SIG fee; real lab quotes.
