# dbfob

**A dirt-cheap keyfob that tells you how loud it is — and how long your ears can take it.**

Press the button, look at the colour. Green means you're fine. Red means leave.

dbfob is an open-hardware sound level indicator sized for a keyring. It exists because nobody pulls out a phone on a dark dance floor to run a sound level meter, but everybody can glance at an LED. It is meant to be cheap enough that a venue, a festival or a hearing-health campaign can hand them out at the door next to the free earplugs.

## Status

Concept / early hardware. Nothing here is verified yet. Contributions welcome — see [Roadmap](#roadmap).

## How it works

1. Press the button.
2. A MEMS microphone samples the room for ~3 seconds.
3. The firmware applies A-weighting and computes the equivalent continuous level (LAeq).
4. One LED lights in a colour that maps the level to a safe exposure time.

That's the whole product.

### Colour bands

Exposure times follow the NIOSH / EU occupational curve (85 dBA for 8 hours, 3 dB exchange rate), **assuming you are wearing earplugs with about 12 dB of real-world attenuation.** Without plugs, drop one band.

| Colour | Level (dBA) | Roughly means |
|---|---|---|
| Green | ≤ 95 | Several hours are fine with plugs |
| Yellow | 96–102 | About an hour |
| Orange | 103–108 | Fifteen minutes or so |
| Red (blinking) | > 108 | Remove yourself now |

The 12 dB assumption is deliberately conservative. Foam plugs on the box claim 30+ dB; in practice, inserted in a hurry by someone who's had a drink, 10–15 dB is realistic.

### Modes

- **Single press — spot check.** Measures the current level and shows a colour for a few seconds. This is the mode that is always trustworthy, because you are holding the device out in front of you.
- **Double press — dosimeter.** (Optional, later.) Samples for a couple of seconds every minute and accumulates dose. A single press then shows dose as a fraction of the daily allowance instead of instantaneous level.

Dosimeter mode has a fundamental problem: a keyfob lives in a pocket, and a pocket reads 10–20 dB low with the high end rolled off. An unsupervised dose would be a comforting lie. The firmware tries to detect occlusion from the spectrum (high-band to low-band energy ratio collapses in a pocket) and refuses to count those samples, flagging the dose as incomplete with a distinct blink pattern. If you want a real dosimeter, clip it to your shoulder. If you want a keyfob, use single press.

## Hardware

Design goal: **under €2 all-in at hobby quantities.** A 130 dB-capable mic alone is ~€1.2, so sub-€1 is off the table unless mic prices drop. No radio, no display, no app.

### Candidate parts

See [docs/mic-mcu-options.md](docs/mic-mcu-options.md) for the comparison. **Chosen:** Infineon IM69D130 PDM mic (130 dB SPL AOP, ±1 dB) + WCH CH32V002.

| Block | Options | Notes |
|---|---|---|
| MCU | **CH32V002** (alt. CH32V006) | PDM read via SPI+DMA, software decimation to 16 kHz. Hardware multiply for the A-weighting biquads; runs down to 2.0 V. |
| Microphone | **Infineon IM69D130** PDM (alt. TDK T5818 in HQ mode) | **Acoustic overload point ≥ 130 dB SPL required.** Many hobby-favourite digital parts clip at ~120 dB, which a club sub stack will exceed. Digital ±1 dB parts allow batch calibration instead of per-unit calibration. |
| LED | 4× discrete low-Vf LEDs as a bar: yellow-green, yellow, orange, red | InGaN green/blue need ~3 V and fade on a coin cell; the bar position also encodes the level for colour-blind users. |
| Power | CR2032 in a holder | MCU in stop mode between presses → years of shelf life. |
| Input | 1× tactile switch | Wakes the MCU. |
| Case | 3D-printed two-part shell, or bare PCB with a keyring hole | Print it at the library. |

An analog MEMS into a 10-bit ADC gives roughly 50 dB of usable dynamic range. Gain-stage it so that spans about 80–130 dB SPL and you cover everything that matters for this device. A 12-bit ADC or a digital mic relaxes this considerably.

### Accuracy

Cheap MEMS parts are ±3 dB sensitivity; better ones are ±1 dB and factory-calibrated. Either is fine for four colour bands. The real uncertainty in this device is placement (held out vs. cupped in a hand vs. in a pocket) and earplug fit, not the microphone. Design effort goes into making "not trustworthy" visible, not into the last dB.

### Calibration

A 94 dB pistonphone won't couple to a MEMS port. Calibrate by substitution instead: place the fob next to a measurement mic in a room with pink noise at a few levels, note the offset, store it in flash. Also characterise the offset when hand-held vs. on a table, since that is how people will actually use it.

## Repository layout (planned)

```
hardware/   KiCad project, generator scripts, BOM, gerbers
firmware/   MCU firmware (A-weighting, LAeq, colour mapping, sleep)
case/       3D-printable shell (STEP + STL)
docs/       Calibration procedure, measurement notes
```

## Roadmap

- [x] Pick MCU + mic ([options](docs/mic-mcu-options.md))
- [ ] Breadboard, verify A-weighted LAeq against a reference meter
- [ ] Define the hand-held offset and the occlusion detector
- [ ] First PCB, coin-cell powered — rev A designed, [hardware/](hardware/README.md), not yet built
- [ ] Printable case
- [ ] Calibration procedure anyone can repeat with a phone and a known-good meter
- [ ] Dosimeter mode
- [ ] Get a batch into a venue and see if people use them

## Non-goals

- Bluetooth, apps, logging to the cloud. The point is that nothing needs to be looked at except one LED.
- Certified measurement accuracy. This is a warning light, not a Class 1 meter.

## Why

Hearing damage is cumulative and irreversible, and the people most at risk are the ones who go out the most. Earplugs are cheap and effective, but people don't put them in unless they have a reason to. A colour that says "you are in the red" is a reason.

## License

Hardware: CERN-OHL-P. Firmware: MIT. Documentation: CC BY 4.0.
