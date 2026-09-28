# dbfob

**A dirt-cheap keyfob that tells you how loud it is — and how long your ears can take it.**

Press the button, look at the colour. Green means you're fine. Red means leave.

dbfob is an open-hardware sound level indicator sized for a keyring. It exists because nobody pulls out a phone on a dark dance floor to run a sound level meter, but everybody can glance at an LED. It is meant to be cheap enough that a venue, a festival or a hearing-health campaign can hand them out at the door next to the free earplugs.

## Status

**Rev A prototype, not yet validated on hardware.**

| Part | State |
|---|---|
| [Hardware](hardware/README.md) | 5 assembled boards ordered from JLCPCB, 2026-09-27. DRC-clean, placement verified against JLC's footprints. |
| [Firmware](firmware/README.md) | Builds for the CH32V003 and passes the host DSP tests (A-weighting within 0.02 dB, 50 Hz–8 kHz). Not yet run on a board. |
| [Case](hardware/case/README.md) | Two-shell SLA case modelled, fit-checked and exported. Not yet printed. |

Next steps are bring-up and calibration against a reference meter. See [Next](#next).

## How it works

1. Press the button. The fob wakes from standby.
2. A PDM MEMS microphone samples the room for 3 seconds.
3. The firmware A-weights the signal and computes the equivalent continuous level (LAeq).
4. A four-LED bar shows two verdicts for 2 seconds: a steady LED for a bare ear and a blinking LED for ear plugs. See below.

The LEDs are deliberately dim, since clubs are dark, and they auto-dim using one LED as a light sensor. Each reading is also printed on a UART pad for calibration.

### Colour bands

The bands are **levels at the ear**, not safety guarantees. The times are the full daily allowance at that level under the NIOSH / EU occupational curve, `T = 8 h × 2^((85 − L)/3)`: 85 dBA for 8 hours, 3 dB exchange rate.

| Colour | At the ear (dBA) | Daily allowance at that level |
|---|---|---|
| Green | ≤ 83 | Below the 85 dBA / 8 h limit |
| Yellow | 84–90 | About 10 h down to 2.5 h |
| Orange | 91–96 | About 2 h down to 40 min |
| Red | ≥ 97 | Under about 30 min |

A 3-second spot reading describes the room right now, not your night. The allowance is for a whole day starting from zero, so anything you've already heard today uses part of it. Green means this level is below the limit, not that the whole night is safe.

### Two LEDs, two questions

Every reading answers two questions at once, so there is no mode to set or forget:

- **Steady LED: what reaches a bare ear.** This is the room level itself: measured, with no assumptions.
- **Blinking LED: what would reach the ear through plugs that really give 12 dB.** This is a conditional estimate, not a measurement and not a safety verdict. The fob cannot know how well your plugs fit. Foam plugs claim 30+ dB on the box, but inserted in a hurry by someone who's had a drink, 10–15 dB is realistic. A badly seated plug can give much less. Individual fit testing is the only way to know your own attenuation, and NIOSH recommends it.

In a 100 dBA room, red glows steady and yellow blinks: you're in the red, and well-fitted plugs could bring you to yellow. When both answers are the same, only one steady LED lights.

The obvious alternative was a mode switch, but either default misleads someone. Assume plugs, and people without them get a falsely reassuring answer. Assume no plugs, and people who do wear them always see red, so the device looks useless to the people doing the right thing. Showing both removes the default, and the gap between the two LEDs is itself the argument for plugs.

### Modes

- **Single press — spot check.** Measures the current level and shows a colour for a few seconds. This is the mode that is always trustworthy, because you are holding the device out in front of you.
- **Double press — dosimeter.** *Not implemented; an idea for later.* The fob would sample for a couple of seconds every minute and accumulate dose. A single press would then show dose as a fraction of the daily allowance, bare ear and with plugs the same way.

The catch is that a keyfob lives in a pocket. A pocket reads 10–20 dB low with the high end rolled off, so an unsupervised dose would be a comforting lie. Dosimeter mode would need to detect occlusion from the spectrum, since the high-band to low-band energy ratio collapses in a pocket. It would refuse to count those samples and flag the dose as incomplete. For a real dosimeter, clip it to your shoulder.

## Hardware

No radio, no display, no app. The design goal was **under €2 all-in**. The rev A parts come to about $1.85 per board at 1,000 units. A 130 dB-capable mic alone is about €1.2, so sub-€1 is out unless mic prices drop.

| Block | Part | Why |
|---|---|---|
| Microphone | Infineon **IM69D130**, PDM | **Acoustic overload ≥ 130 dB SPL.** Hobby-favourite digital mics clip at about 120 dB, which a club sub stack exceeds. It is digital, with ±1 dB sensitivity, so a batch can be calibrated rather than each unit, and the reading doesn't drift with battery voltage. |
| MCU | WCH **CH32V003F4P6** | The CH32V002/V006 are pin-compatible drop-ins, but were out of stock. The V003 has no hardware multiplier (handled in firmware) and needs at least 2.7 V. |
| LEDs | 4 × 0603 low-Vf LEDs as a bar: yellow-green, yellow, orange, red | InGaN green and blue LEDs need about 3 V and fade on a coin cell. The bar position also encodes the level for colour-blind users. D4 doubles as the light sensor. |
| Power | CR2032 in a Keystone 3034 | Standby is about 7.6 µA, so an idle fob lasts about 3 years. The mic is powered only while measuring. |
| Input | 1 × tactile switch | Wakes the MCU. |
| Case | 3D-printed two-part shell, one M2 screw | Mic and LEDs at one end, keyring at the other. |

Background and trade-offs:
- The part comparison is in [docs/mic-mcu-options.md](docs/mic-mcu-options.md).
- An independent hardware audit, with the response to each finding, is in [docs/hardware-audit-2026-09-27.md](docs/hardware-audit-2026-09-27.md).

### Accuracy

Cheap MEMS parts are ±3 dB sensitivity; better ones are ±1 dB and factory-calibrated. Either is fine for four colour bands. The real uncertainty in this device is placement (held out vs. cupped in a hand vs. in a pocket) and earplug fit, not the microphone. Design effort goes into making "not trustworthy" visible, not into the last dB.

### Calibration

A 94 dB pistonphone won't couple to a MEMS port. Calibrate by substitution instead: place the fob next to a measurement mic in a room with pink noise at a few levels, note the offset, store it in flash. Also characterise the offset when hand-held vs. on a table, since that is how people will actually use it.

## Repository layout

```
hardware/        KiCad project, generated from the tables in hardware/tools/ (schematic, PCB, JLC outputs)
hardware/case/   FreeCAD case script, STEP/STL for printing, board geometry it is built from
firmware/        CH32V003 firmware on ch32fun: PDM capture, A-weighting, LAeq, LEDs, standby; host tests
docs/            part selection, hardware audit
```

## Next

- [ ] Bring-up on rev A: power, programming, mic capture, CPU load, standby current. See [firmware/README.md](firmware/README.md#bring-up-checklist).
- [ ] Calibrate against a reference meter, in the case: the level offset and the hand-held offset.
- [ ] Qualify the battery: the supply voltage under load across cell charge and temperature, then set the cutoff.
- [ ] Print the case and check the tolerances, the button flexure and the mic seal.
- [ ] A calibration procedure anyone can repeat with a known-good meter.
- [ ] Rev B board: centre the mic port, add UART RX for a bootloader, CH32V002/V006 if in stock, possibly a power latch for shelf life.
- [ ] Dosimeter mode with occlusion detection.
- [ ] Get a batch into a venue and see if people use them.

## Non-goals

- Bluetooth, apps, logging to the cloud. The point is that nothing needs to be looked at except one LED.
- Certified measurement accuracy. This is a warning light, not a Class 1 meter.

## Why

Hearing damage is cumulative and irreversible, and the people most at risk are the ones who go out the most. Earplugs are cheap and effective, but people don't put them in unless they have a reason to. A colour that says "you are in the red" is a reason.

## License

Hardware: CERN-OHL-P. Firmware: MIT. Documentation: CC BY 4.0.
