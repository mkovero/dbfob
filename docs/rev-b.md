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
| Parts | about $3 (+ about $0.4 NFC, + ferrite sheet) | about $12–20 |
| Retail | give-away / €5 | €50–80 |
| Main risks | few | wearing position, iOS, LiPo shelf life, EU removability rule, Qi coupling, certification |

**Decision (2026-10-29): B1.** Keep the scope on what matters for measuring and reading the log, not on features. If logs are to be processed on a phone, an NFC tag chip does it without blowing up the cost. Size target: **half of rev A**. B2 stays parked. See [B1 target](#b1-target).

**The review's recommendation, which led to this:**
- Build B1 next.
- Park B2 until a specific buyer asks for it, such as a venue study, a festival or a band.
- If BLE happens anyway: a certified nRF54L module, a coin cell (CR2450), advertising only, and the live spectrum as a developer tool.
- Run the [experiments](#experiments-before-any-board) first. Most of them run on rev A hardware.

## B1 target

**Goal:** rev A's proven metering, half the size, with the log readable on a phone by tapping. Nothing that does not serve measuring correctly or getting the log out.

**Size: half of rev A.** Rev A is 30 × 52.5 mm with every part on top and the CR2032 holder taking most of it. Target about **30 × 26 mm**:
- **Cell: CR2032, under the board** (decided 2026-10-29). It sits on the back in a low-profile holder.
  - Kept because it fits the half-size footprint and is everywhere.
  - Smaller cells only help below half size or for thinness, and their higher internal resistance fights rev A's >10 mA peaks against the V003's 2.7 V minimum. CR1632 (16 mm, ~130 mAh) is the option if the board shrinks further, with a bulk capacitor and dimmer LED peaks.
  - Two stacked CR2016s give 6 V, which is over the mic's 3.6 V. Not an option.
  - A CR2450 (24.5 mm, 620 mAh) just fits in 30 × 26, if adaptive metering ever needs the capacity.
- **Parts on the top side:** MCU, mic, NFC chip, four LEDs, button, 0402 passives.
- **Keyring hole or clip** in one corner.
- The mic port is centred, and stays clear of fingers and the clip.

**NFC readout.** Survey on 2026-10-29. Stock and prices are from JLC's parts library.

| # | Part (LCSC) | Memory / type | Field detect | VCC current | Package | Stock, price | Lifecycle |
|---|---|---|---|---|---|---|---|
| 1 | **NXP NT3H2111W0FHKH**, NTAG I2C plus 1k (C710403) | 888 B + 64 B SRAM, **Type 2** | FD pin, open drain, works from RF with VCC off | 185–240 µA, no standby mode: power it from a GPIO | **XQFN8 1.6 × 1.6** | **48,188; $0.35 @100** | active, NXP longevity program |
| 2 | ST ST25DV04KC-IE8C3 (C5221756) | 512 B, Type 5, 256 B mailbox | GPO, works from RF | standby 72–76 µA; low-power-down (LPD) pin only on the 12-pin / WLCSP versions | UFDFPN8 2 × 3 | 36; $2.11 @100 | current; the older ST25DV04K is NRND |
| 3 | NXP NTP5332, NTAG 5 link (C3301642) | 2 KB + 256 B SRAM, Type 5 | event pin | standby 6 µA, power-down 0.25 µA | XQFN16 1.8 × 2.6 | 89; $1.32 @100 | active |
| 4 | NXP NT3H2211W0FHKH, NTAG I2C plus 2k (C2905792) | 1912 B, Type 2 | as #1 | as #1 | XQFN8 1.6 × 1.6, same footprint as #1 | 50; $1.15 @100 | active |

- **Recommended: NT3H2111.** Smallest, cheapest, deep stock, and Type 2 is the safest tag type for iPhone background reading.
  - 888 B holds the 156 B summary URL easily.
  - VCC comes from an MCU GPIO. Keep SDA/SCL low or floating while it is off, so the chip isn't powered through them.
  - Its FD pin can wake the MCU from the phone's field alone.
  - The NT3H2211 (2 KB) fits the same footprint, for the full log.
  - Specs ([datasheet](https://www.farnell.com/datasheets/2148700.pdf)): VCC 1.67–3.6 V, I2C writes 4.5 ms per 16 B block, ≥500k write cycles, 20-year retention.
  - The first draft's "ST25DV04K about $0.5–0.7" was wrong: the 04K is NRND, and the 04KC in 2 × 3 is about $2 with thin stock.
- **Write on a schedule, not on tap.**
  - A refresh is about 10–16 blocks, roughly 70 ms at 0.2 mA, about 4 nAh. Every 10 minutes that is about 0.6 µAh a day, which is negligible.
  - Make the encoding append-friendly so an update rewrites only 1–2 blocks. Then 144 writes a day stays within endurance for about 9.5 years.
  - Writing just in time on a tap won't work: the phone reads tens of ms after its field comes up, a cold write takes 50–80 ms, and RF access blocks I2C. Use FD to wake the MCU for a "phone was here" event instead.
- **Antenna.**
  - NTAG I2C plus wants about 2.75 µH (50 pF internal), roughly 8–10 turns around a 20–24 mm area (Wheeler estimate, 0.2 mm trace and gap). Confirm with NXP AN11276 and tune on the bench.
  - **The CR2032 behind the coil is the main risk.** Eddy currents in the cell drop inductance and add loss; read range may collapse ([Würth ANP022](https://www.we-online.com/components/media/o109046v410%20ANP022c%20EN.pdf)).
  - Fix: a 0.1–0.2 mm NFC-grade ferrite sheet between the board and the cell (Würth WE-FSFS, 364 material, [ANP016](https://www.we-online.com/components/media/o109045v410%20ANP016c%20EN.pdf)). Not stocked at JLC, so it's a hand-assembly step. Tune with the ferrite and cell in place.
  - No app note found for coin cells specifically, so **prototype this first** (experiment 4).
- **Phones.**
  - **iPhone** ([Apple](https://developer.apple.com/documentation/corenfc/adding-support-for-background-tag-reading)):
    - Needs an XS or later, with the screen on and the phone unlocked at least once since boot.
    - Doesn't read while the camera, Wallet or airplane mode is active.
    - Uses the first URI record, https only. The user taps a notification and Safari opens.
    - Type 2 is the safe choice; Type 5 background reading is reported to work but can be slow.
  - **Android:** reads Type 2 and Type 5 with the screen on and unlocked, and opens the browser.
  - Put the data in the URL's `#fragment`, so it never reaches the web server.
- **Readable with the cell dead:** yes. The tag is read over the air, powered by the phone's field.
- **What it can't do:** stream live levels. That stays the UART's job on the bench.

**Mic.** The IM69D130 (`IM69D130V01XTSA1`) is "not for new design" at Infineon, with no named replacement. Survey on 2026-10-29, requiring PDM, ≥130 dB SPL AOP, ±1 dB and running from a CR2032 without an LDO:

| # | Part | AOP and clock | Sens. | VDD | Current @1.5 / @3 MHz | Package | Status | Price |
|---|---|---|---|---|---|---|---|---|
| 1 | **Infineon IM67D130A** (AEC-Q103 automotive) | 130 in all modes: 1.05–1.9 MHz and 2.9–3.3 MHz | −36 ±1 | 1.62–3.6 | 620 / 980 µA | 4 × 3 × 1.3, bottom port, same pin order as IM69D130 | active | $1.19 @1k (Digi-Key); LCSC C3098141, $1.77 @100, thin stock |
| 2 | **Knowles SPW0690LM4H-1** | 133 min / 135 typ, 1.1–4.8 MHz | −41 ±1 | 1.65–3.6 | 750 / ~1,225 µA | 3.1 × 2.5 × 0.95, bottom | active | $1.01 reel (Digi-Key); LCSC C3171749 |
| 3 | Infineon IM66D130M | 130 in all modes: 1.34–1.72 and 2.84–3.44 MHz | −37 ±1 | 1.6–**3.465** | 420 / 540 µA | 3 × 2 × 0.98, bottom | active, preferred | $0.66 @1k (Digi-Key); LCSC 0 stock |
| 4 | Infineon IM66D130A | 130, 2.9–3.3 MHz only | −36 ±1 | 1.62–3.6 | – / 1,100 µA | 3.5 × 2.65, bottom | active, preferred to 2034+ | $0.97 @1k |
| – | Infineon IM72D128 | **128**: misses the requirement | −36 ±1 | 1.62–3.6 | – / 980 µA | 4 × 3 | active, preferred | best stocked: LCSC C5119248, 3.5k pcs |

- **B1 mic: IM66D130M, decided 2026-10-29.** Availability, specs and current all favour it. The IM67D130A stays only as a drop-in for rev A boards.
  - IM66D130M: Mouser stocks it in quantity.
    - Its normal-mode clock band (1.34–1.72 MHz) contains rev A's 1.5 MHz, so the firmware keeps its clock.
    - The sensitivity is 1 dB lower (−37 dBFS), which is one calibration constant.
    - Current is 420 µA against 620 µA, and the 3 × 2 mm package helps the half-size board.
    - Its 3.465 V operating maximum (3.6 V absolute) is fine on a CR2032 and at 3.3 V on the bench or the WCH-LinkE. Never test it above 3.4 V.
    - If LCSC still has no stock, use JLC Global Sourcing or consignment.
    - **Footprint is new, not a variant of rev A's** (datasheet v1.1, Figures 13 and 15):

      | | IM69D130 (rev A) | IM66D130M |
      |---|---|---|
      | Body | 4 × 3 mm | 3 × 2 mm |
      | Pads | 4 × 0.45 × 0.75 mm, solder mask defined, columns 0.8 mm apart | 4 × 0.42 × 0.625 mm, non-solder-mask defined, columns 0.6 mm apart (0.18 mm gap), rows 1.11 mm |
      | Ground ring (port) | Ø2.06 / Ø1.16 | Ø1.4 / Ø0.76 |
      | PCB sound hole | Ø0.8 mm | **Ø0.375 mm** |
      | Pin order | 1 DATA, 2 VDD, 3 CLK, 4 SELECT, 5 GND ring | 1 DATA, 2 LR, **3 GND ring**, 4 CLK, 5 VDD |

    - Draw a new footprint from Figure 15, and re-route.
    - The 0.375 mm sound hole is about JLC's smallest plated drill, so check their minimum. It also changes the port acoustics: experiment 3 should use this hole.
    - Use **ENIG** for these small non-solder-mask-defined pads. HASL leaves them uneven.
  - First boards: check the level against the AC2, then set the calibration constant.
- **Drop-in for rev A boards: IM67D130A.** Same 4 × 3 mm body and pin order, the same clock bands, sensitivity and AOP. So rev A's firmware at 1.5 MHz should carry over unchanged. SNR is 67 against 69 dB(A). **Overlay the two footprint drawings before calling it a drop-in**; the datasheet drawings only looked the same by eye. ([product](https://www.infineon.com/part/IM67D130A), [datasheet](https://www.infineon.com/assets/row/public/documents/30/49/infineon-im67d130a-datasheet-en.pdf))
- **Second source: SPW0690LM4H-1.** The most headroom (133 dB guaranteed), and works at 1.5 or 3 MHz. But it needs a new footprint, and its sensitivity is 5 dB lower, which costs some noise floor. ([datasheet](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/559/SPW0690LM4H-1_DS.pdf))
- **Dropped:**
  - TDK T5818, rev A's planned second source: now **EOL**.
  - TDK T5838/T5837: 1.62–1.98 V, needs an LDO.
  - T5848: I²S.
  - ICS-41350/1: EOL, 120 dB.
  - ST MP23DB01HP: obsolete / NRND, and 135 dB only at ≥1.5 MHz.
  - IM69D128S and IM69D127: under 130 dB.
- **Not checked:**
  - Knowles SPH0690LM4H-1: VDD range.
  - Chinese parts on LCSC with −37 dBFS sensitivity (Gettop MD-HRA371-H10-3N, Goertek SD18OB371-077): datasheets give no AOP.

**MCU.** Survey on 2026-10-29. Stock and prices are from JLC's parts library, which feeds JLC assembly. Rev A's firmware is 13.2 KB of flash plus the 1 KB log, out of 16 KB, and 320 B of RAM.

| # | Part (LCSC) | Core / multiply | VDD | Flash / RAM | Standby with wake timer | Package | JLC stock, price | ch32fun |
|---|---|---|---|---|---|---|---|---|
| 1 | **CH32L103F8U6** (C22467836) | QingKe V4C RV32IMAC, single-cycle MUL and DIV, 96 MHz | **1.8–3.6 V** | 64 K / 20 K | **0.51–0.74 µA** (LSI, RTC) | QFN-20 3 × 3 | 1,878; $0.56 @1, $0.29 @1k | yes, thin: header plus blink and standby examples |
| 2 | PY32F003F16U6TR (C3018714); F18P6TR (C55338319) for 64 K / 8 K | Cortex-M0+ (MUL), 32 MHz | 1.7–5.5 V | 32 K / 4 K | 4.5–6 µA Stop, LPTIM/RTC wake | QFN-20 3 × 3 / TSSOP-20 | 7,992; $0.15 @6k. F18P6: 65,781 | no: arm-gcc, Puya LL, pyOCD |
| 3 | CH32V005F6P6 (C54824605) | QingKe V2C RV32EmC (MUL), 48 MHz | 2.0–5.5 V, **2.4 V with the ADC on** | 32 K / 6 K | 10.2 µA | TSSOP-20 only | **203**; $0.13 | yes |
| 4 | MSPM0L1306SRGER (C19189323); L1106 WQFN-16 2 × 3 (C32896732) | Cortex-M0+ (MUL), 32 MHz | 1.62–3.6 V | 64 K / 4 K | 1.0 µA | VQFN-24 4 × 4 | 7,831; $0.75 @1k | no: TI SDK + GCC |
| – | CH32V003F4P6, rev A | V2A, no MUL | 2.7 V | 16 K / 2 K | 7.6 µA | TSSOP-20 | 26,683; $0.15 | yes |

- **Recommended: CH32L103F8U6.** The only in-stock part with all of these:
  - hardware multiply, so the A-weighting stops costing 65 % of the CPU;
  - a 1.8 V minimum, which removes the 2.7 V cutoff problem;
  - 64 K flash for the NFC driver, bootloader and log, plus 20 K RAM;
  - standby under 1 µA, against about 8 µA board total now;
  - it stays in ch32fun.

  It costs about twice the V003. Its SPI/DMA/I2C registers follow the CH32V20x model, so the port is mostly clock setup and `rv32imac` build flags. Watch-outs:
  - **Waking from Standby resets the chip.** RAM can be retained, but the firmware flow changes from rev A's WFE-and-continue.
  - **PB6/PB7 have built-in 5.1 kΩ USB Type-C pull-downs.** About 5 µA in Standby unless configured off; reported forced on in Standby on some lots. Assign those pins with care.
  - **Thin ch32fun support.** No SPI-DMA example, so budget bench time.
  - **PDM clock:** the 8 MHz HSI through the PLL to 24 or 48 MHz, divided by 16 or 32, gives 1.5 MHz (PLL setup not checked).
- **Fallback: PY32F003**, if price or stock wins over toolchain continuity. It's cheap and well stocked, with DMA on SPI and a 1.7 V minimum, but it moves to ARM tooling and a different programmer.
- **CH32V005F6P6** only if rev A pin compatibility mattered. It doesn't, since B1 is a new board. Thin stock, a 2.4 V floor with the ADC on, and worse standby than the V003.
- **MSPM0L1306:** best power figures and a clean 1.62 V minimum, at 5–7× the price. A non-WCH fallback.
- **Excluded:**
  - CH32V002/004/006/007 and CH32M007: no JLC stock; some codes are marked no longer manufactured.
  - CH32X035/X033: standby 51 µA, 528 µA with the wake timer on.
  - PY32F002A/B: no DMA.
  - STM32C011: Stop current 72–80 µA.
  - MSPM0C110x: too little RAM or stock.
  - STM32U031: no stock.
- **Not verified:**
  - CPU load with hardware multiply (estimated, not measured);
  - L103 PLL and SPI-DMA in ch32fun;
  - LCSC stock (as opposed to JLC);
  - WCH and Puya lifecycle status.
- Sources:
  - [CH32L103 datasheet (mirror)](https://git.tangentheavy.com/THI/tertiary/raw/branch/main/Documents/CH32L103DS0.PDF), [openwch/ch32l103](https://github.com/openwch/ch32l103)
  - [CH32V005/006 datasheet](https://atta.szlcsc.com/upload/public/pdf/source/20251215/55744532B0660A1F292C8E9A62911D5C.pdf)
  - [CH32X035 datasheet](https://atta.szlcsc.com/upload/public/pdf/source/20251203/17E2E459F0796680698329147EAAD418.pdf)
  - [PY32F003 datasheet](https://atta.szlcsc.com/upload/public/pdf/source/20220816/E4DA13E8427F79CD08E079FD58592346.pdf)
  - [MSPM0L1306](https://www.ti.com/product/MSPM0L1306)
  - [ch32fun](https://github.com/cnlohr/ch32fun)

**Also in B1:**
- Calibration stored in flash, per board.
- A UART bootloader, or updates over the NFC tag's mailbox.
- Rev A's low-battery lockout, and the overload flag in the log.

**Out of B1:** BLE, LiPo, wireless charging, live spectrum on a phone.

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

- **NFC readout without BLE.** A dynamic NFC tag chip with I2C (NTAG I2C plus, about $0.35, or ST25DV; PCB antenna) works with any MCU; see [B1 target](#b1-target). The fob writes a dose summary into a URL the tag serves (NDEF record). The 10-minute summary from [log-readout.md](log-readout.md) is about 156 B. iPhone (background tag reading) and Android open the web page with no app and no pairing, **even with the fob's cell dead.** This replaces most of log-readout.md and the BLE readout for both directions.
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
   - An NTAG I2C plus (NT3H2111) breakout with the dose summary in a tag URL, **over a CR2032, with and without a ferrite sheet**.
   - Tap with an iPhone (screen on, and locked) and an Android, and confirm the page opens with no app.
   - This decides the readout for both directions.
5. **Only if Qi stays:**
   - A cheap receiver module with a 20 mm coil, on three common pads, inside a closed printed box with a thermocouple on the cell.
   - Does the pad accept it, at what current, at what temperature?

Bonus if going nRF anyway: an nRF54L15 DK plus an IM69D130 breakout. Run PDM at about 3 MHz into about 48 kHz with the CPU asleep, and measure continuous and advertising-only current. That replaces the runtime guesses with numbers.

## Open questions

- Clip or keyfob, or both as two tiers: after experiment 1.
- Continuous, adaptive or sampled: after experiment 2.
- Not yet verified: CC2340 price; nRF52833 WLCSP price; ESP32-C6 PDM; nRF54L module prices; PTX30W price; TP4054 at ≤30 mA; Bluetooth SIG fee; real lab quotes.
