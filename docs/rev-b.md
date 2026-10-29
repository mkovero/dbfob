# Rev B: a BLE fob on a rechargeable cell

Ideas, not a design. Rev A proves that simple metering works on a €2 coin-cell board. Rev B is the "medium" version of the same idea: a smaller fob, a rechargeable cell, a radio, and continuous full-band metering. Rev A stays as the cheap tier.

Written 2026-10-29 from a design discussion. **Every price here is from memory, about 1k-unit pricing, and not checked.** Verify on LCSC / Mouser / Digi-Key before using any number for a decision.

## Goals

- **BLE** for live levels, a live spectrum and the dose log on a phone.
- **About half rev A's size.** Rev A is 30 × 52.5 mm, mostly the CR2032 holder. Target about 30 × 26 mm or 20 × 35 mm.
- **A small rechargeable Li-ion / LiPo cell** instead of the CR2032.
- **Wireless charging** if at all possible, so the case can be sealed.
- **Continuous metering.** Rev A takes one 1 s sample a minute. In a club log ([test3](#why-continuous)) the song gaps are hit or missed by luck.
- **Full-band A-weighting to 20 kHz.** Rev A stops at 11.7 kHz (see [firmware/README.md § Signal chain](../firmware/README.md#signal-chain)). High-frequency content is exactly what a listener stops noticing after a few drinks, and loud exposure itself first dulls the high frequencies.

## MCU: nRF52833

| Option | Price (unverified) | Notes |
|---|---|---|
| **nRF52833** | $2–3 | Hardware PDM interface. VDDH input up to 5.5 V: runs straight from a LiPo, and its internal regulator can feed the mic. NFC tag. M4F with FPU. **Preferred.** |
| nRF52820 | ~$2 | Also has VDDH. Check PDM and NFC. |
| nRF52810 | $1.5–2 | Has PDM, no VDDH: needs a regulator. |
| nRF54L05 / L10 | check | Newer and lower power. Check PDM support and stock. |
| TI CC2340 | $0.6–1 | Cheapest serious BLE chip. No PDM hardware as far as known. |
| WCH CH592 | ~$0.5 | Same vendor family as rev A. No PDM: the SPI trick again. Weaker SDK and radio. |
| ESP32-H2 / C3 | ~$1 chip, ~$2–2.5 certified module | Cheapest certified modules and a good toolchain. But BLE transmit draws tens of mA, against 5–7 mA on the nRF52. Keeping BLE alive in light sleep costs 0.1–1 mA, against a few µA. Deep sleep wakes are a full reboot (100+ ms). Wrong for a 25–60 mAh cell. The H2 (BLE, no Wi-Fi) is the fallback if a bigger cell is accepted. Skip the C3/C6: Wi-Fi is useless on a fob. Check which ESP32s can receive PDM in hardware: the S3 can. |

What the nRF52833's PDM peripheral solves at once:
- **Full band.** A 3.072 MHz mic clock decimated by 64 in hardware gives 48 kHz samples, so A-weighting runs to 20 kHz. The mic's own response is loose up there (+9/−2 dB at 15 kHz), so it needs a calibration.
- **CPU load.** EasyDMA collects the samples while the CPU sleeps. Rev A uses 65 % of 24 MHz on a software CIC.
- **The clock trade-off.** No 24 vs 48 MHz choice against cell sag as on rev A.

Radio support parts: a 32 MHz crystal ($0.15–0.3); a PCB-trace antenna (free, but needs a 5–10 mm keep-out at an edge) or a chip antenna ($0.1–0.3); matching parts ($0.1); a DC-DC inductor.

**Certification.** Putting the chip on our own board needs our own radio approval (CE RED / FCC), several k€ of testing. A pre-certified module ($5–10 for nRF, for example Raytac, Insight SiP, Fanstel) avoids most of it. At small volumes the module wins despite the price, and small modules exist (Insight ISP1807, about 8 × 8 mm).

## Battery

- **Not salvaged e-cig cells.** Disposable vapes use 13300 / 13350 cylinders: 13 mm across, 30–35 mm long, 300–550 mAh. That makes the fob bigger, not smaller. Their health and cycle count are also unknown: fine on the bench, not in a product.
- **A LiPo pouch.** 301012 (3 × 10 × 12 mm, about 25 mAh) up to 401020 (about 60 mAh), $0.8–1.5. It sits under the board.
- **Charger and protection.** A Li-ion charger IC ($0.1–0.2, unless the wireless receiver includes one) and protection (DW01 + FS8205, about $0.1), or a cell with built-in protection.
- **The mic needs ≤ 3.6 V.** The IM69D130's maximum is 3.6 V, and a LiPo reaches 4.2 V. On the nRF52833, VDDH plus the internal REG0 gives a regulated VDD that can feed the mic from a GPIO, as on rev A.
- A LIR2032 (rechargeable coin cell, 3.6–4.2 V, about 40 mAh) is the same size as a CR2032, so it does not help with the size.

### Runtime estimates (unmeasured)

| Mode | Average | On 40 mAh |
|---|---|---|
| Rev A-style sampling, 1 s a minute, plus BLE advertising every 1 s | 50–100 µA mic and capture, plus 10–20 µA advertising | about 2 weeks of nights |
| Continuous metering, BLE idle | about 1–1.5 mA | about 30 h |
| Live streaming to a phone (mic, PDM, FFT, BLE at 15–30 ms interval) | about 2–3 mA | 15–20 h |

### Why continuous

The test3 club log (2026-10-21, LAeq 95 dBA over about 1 h 45 min) jumps between about 96 dBA and 55–75 dBA. A dip shows only when the one 1 s sample a minute happens to land in a song gap. Continuous metering with a rechargeable cell removes that sampling luck, at the cost of charging every night or two. Possible middle ground: continuous while loud, sampled while quiet.

## Wireless charging

**Qi receiver.** Charges on any phone charging pad.
- TI BQ51050B: a Qi receiver plus Li-ion charger in one, $2–3, a small chip-scale (WCSP) package.
- A 20–25 mm receiver coil with ferrite backing, 0.5–1 mm thick, $0.5–1. It fits on the back of a 30 × 26 mm board, under the cell.
- Pad coils are about 40 mm, so a 20 mm coil couples poorly and charges slowly. That is fine here: a 40 mAh cell needs about 40 mA, a full charge in about an hour.
- The ferrite shield between coil and cell is mandatory. Watch the cell temperature while charging.
- Earbud cases do this at this scale. About +$3–4.

**NFC wireless charging (NFC Forum WLC).**
- NXP PTX30W listener, $1–2. A 10–15 mm coil, possibly on the PCB. Up to about 250 mW.
- Used in smart rings and styluses.
- Few phones and pads support it yet, so it needs its own charger.

**Fallback.** Magnetic pogo pins like a smartwatch, about $0.5 plus a cable. Still a sealed case.

**The win in every case: no USB opening.** A sealed case survives pockets, rain and spilled drinks at the club.

## Live spectrum over BLE

BLE is the right link as long as the fob computes the spectrum and sends results, not audio.

| What is sent | Rate | Over BLE |
|---|---|---|
| 1/3-octave bands, 31 × 1 B × 10 fps | about 0.3 kB/s | trivial |
| FFT, 256 bins × 1 B × 10 fps | about 2.5 kB/s | easy |
| FFT, 512 bins × 2 B × 20 fps | about 20 kB/s | fine |
| Raw audio, 16 kHz × 16 bit | 32 kB/s | works |
| Raw audio, 48 kHz × 16 bit | 96 kB/s | at the limit: use BLE Audio (LC3) on an nRF5340 instead |

- BLE 5 with the 2M PHY and data length extension realistically carries 50–100 kB/s on an nRF52833.
- A 512-point FFT in CMSIS-DSP on the M4F takes a fraction of a millisecond at 64 MHz. Feed it the same 48 kHz PDM stream as the A-weighting, so the spectrum is full band.
- 1/3-octave bands are the classic sound-level-meter display and the cheapest to send. An FFT gives the analyser look.
- Streaming is for minutes at a time. Normal use stays at dosimeter current and switches to streaming only while a phone is connected.
- Wi-Fi is not needed. It would only matter for streaming raw audio to a PC, and its power rules it out on a fob.

## Phone side

- **Web Bluetooth.** A plain web page connects to the fob and draws levels, the spectrum and the dose log, with no app to install. It works in Chrome on Android and desktop, not in Safari on iOS (Bluefy, or a native app, there).
- **NFC tap.** The nRF52833's NFC tag holds a URL. Tapping the fob opens the web page, which then connects over BLE. A quick dose check could even be in the NFC record itself, with no BLE at all. This replaces rev A's log readout ideas ([log-readout.md](log-readout.md)).
- **Why not the phone's own mic?** Phone mics are uncalibrated, use automatic gain and filtering, sit in a pocket or hand, and clip far below 130 dB SPL. The fob's mic is calibrated, worn on the body, and good to 130 dB SPL.

## Size

- The LiPo pouch goes under the board; parts go on both sides; 0402 passives.
- The antenna keep-out shares a corner with the keyring hole.
- Thickness is about the same as rev A: a 3–4 mm pouch against about 4.5 mm for the coin cell in its holder. Add 0.5–1 mm for a Qi coil.
- The LEDs, button and mic port stay. The four-LED bar still answers "am I fine" without a phone.

## Cost (all unverified)

| Block | nRF52833 on our board + Qi |
|---|---|
| nRF52833, crystal, antenna, matching, DC-DC | $3–4 |
| IM69D130 mic | about $1.3 |
| LiPo, charger, protection | $1.2–1.8 |
| Qi receiver and coil | $3–4 |
| LEDs, button, passives | about $0.5 |
| **Total** | **about $9–13** |

With a certified module instead of the chip on our own board, add about $3–7 and drop most of the certification cost. Rev A is about $1.85. Rev B is a €20–30 retail device rather than a €2 give-away, which is why the two are separate tiers.

## Open questions

- Verify every price and stock level above.
- nRF52833 vs nRF54L: PDM support, power use, VDDH, NFC, price.
- Which pouch cell fits, and does its holder area beat a CR2032's.
- Qi coupling with a 20 mm coil on common pads: charge current and heating, measured.
- Module vs our own board, given the expected volume.
- Continuous vs adaptive sampling, against charging interval.
- 1/3-octave bands vs FFT for the live view; what the web page shows.
