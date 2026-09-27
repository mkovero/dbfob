# Hardware and production audit — 2026-09-27

Audited revision: `d752502` (rev A). The starting worktree was clean. This audit adds only this report; all rebuilds and negative tests used copies under `/tmp/dbfob-audit`.

The committed PCB passes electrical connectivity, geometric DRC, schematic parity, and the existing placement check. Its manufacturing outputs agree with the board. It is suitable for prototype bring-up, but the clock specification, power qualification, product claims, and release checks need work before production release. No physical hardware or firmware was available for functional validation.

P1 means resolve before production use; P2 means a material production or maintenance risk to resolve before a repeatable release.

1. **P1 — The specified PDM clock is unsupported by the selected microphone and MCU clock plan.**

   Location: [hardware/README.md](../hardware/README.md), line 28; [docs/mic-mcu-options.md](mic-mcu-options.md), “Next steps”.

   The design specifies 1.024 MHz, decimation by 64, and 16 kHz audio. Infineon's operating bands stop at 950 kHz and resume at 1.05 MHz, so 1.024 MHz sits in an unspecified transition band. WCH's SPI divider is a power of two from 2 through 256; the fitted board's nominal 48 MHz internal clock cannot generate 1.024 MHz through it. Implementing the documented configuration therefore either uses an unspecified microphone clock or produces a different sample rate, invalidating filter coefficients designed for 16 kHz.

   Choose an attainable clock inside a specified band, then define the actual sample rate, decimator, and A-weighting coefficients together. For example, 48 MHz / 32 gives 1.5 MHz; decimation by 64 gives 23,437.5 samples/s. This example still needs processing and acoustic validation. Also count microphone startup delay from application of both supply and clock, not supply alone.

   Evidence: [Infineon IM69D130 datasheet, tables 4–5](https://www.infineon.com/assets/row/public/documents/24/49/infineon-im69d130-datasheet-en.pdf); [WCH reference manual, SPI_CTLR1 BR field](https://www.spinics.net/lists/trinity-users/attachments/pdfXz01Gp8QpG.pdf) (manufacturer document hosted on a mirror).

2. **P1 — The protected-ear verdict assumes protection the device cannot measure.**

   Location: [README.md](../README.md), lines 24–48; [hardware/tools/make_pcb.py](../hardware/tools/make_pcb.py), `SILK_B`.

   Subtracting 12 dB for every wearer can show blinking green at a room level of 95 dBA even when poorly fitted plugs provide substantially less attenuation. Calling that subtraction conservative does not establish a lower bound on protection. Showing the bare-ear LED simultaneously does not fix the meaning of the protected-ear verdict. NIOSH now recommends individual quantitative fit testing to determine received attenuation.

   The time labels also exceed what a three-second spot measurement establishes. Under the stated 85 dBA / 8 h / 3 dB curve, 96 dBA corresponds to about 38 minutes for a full daily dose, rather than an hour; previous exposure reduces the remaining allowance. A spot measurement cannot establish that an entire night is safe.

   Define the blinking result explicitly as a conditional estimate for a stated, verified attenuation, or remove the protected-ear safety verdict. Replace unconditional safety and remaining-time claims with level/risk indications. Update the PCB legend consistently before release.

   Evidence: [NIOSH individual fit-testing recommendation](https://www.cdc.gov/niosh/docs/2025-104/); [NIOSH exposure limits and exchange rate](https://www.cdc.gov/niosh/bulletin/2016/noise.html). Calculation: `T = 8 × 2^((85 − L)/3)` hours.

3. **P1 — The coin-cell capacity estimate ignores the supply margin during measurement.**

   Location: [hardware/README.md](../hardware/README.md), line 57; [hardware/tools/gen_sch.py](../hardware/tools/gen_sch.py), U1, C2, and BT1.

   The claim that switching to the V003 loses only the final 10–15% of capacity is unsupported for this load. The MCU requires at least 2.7 V and its documented 48 MHz HSI run current is approximately 4.0–6.4 mA before adding the microphone. Energizer characterizes a comparable 6.8 mA pulse at 2.7 V; its headline capacity is measured at approximately 0.19 mA down to 2.0 V. Those are different operating conditions.

   A 3.0 V cell with 50 ohms of effective source resistance reaches 2.7 V at 6 mA. The ideal 10 uF capacitor supports that current through a 0.3 V drop for only 0.5 ms, not the three-second acquisition. This establishes a qualification risk, not a measured failure of this PCB. The MCU can also remain out of its guaranteed operating range before its internal reset threshold is reached.

   Qualify actual cells across state of charge and intended temperature, logging minimum VDD throughout acquisition and display. Define an under-load battery cutoff with margin and an explicit invalid-reading state. Reconsider the MCU/supply if usable capacity is insufficient. Standby budgeting also needs revision: the documented typical 7.6 uA is about 66.6 mAh/year, before other leakage, so self-discharge alone does not set shelf life.

   Evidence: [WCH datasheet, supply/current/reset tables](https://www.jc-net.co.jp/pdf/CH32V003DS0-EN.pdf) (manufacturer document hosted on a mirror); [Energizer CR2032 datasheet](https://data.energizer.com/pdfs/cr2032.pdf). These are datasheet estimates; board current remains unmeasured.

4. **P2 — ERC/DRC are not enforced as production release gates.**

   Location: [hardware/tools/make_pcb.py](../hardware/tools/make_pcb.py), lines 347–383; [hardware/tools/fab.py](../hardware/tools/fab.py), lines 70–104.

   `make_pcb.py` prints remaining DRC errors, open nets, and parity violations, then returns normally. It also drops every library-footprint mismatch rather than distinguishing missing library configuration from a changed footprint. `fab.py` performs no ERC, DRC, or parity preflight and writes the Gerber ZIP before checking the CPL. Consequently, a later broken design can still produce an apparently successful, uploadable release.

   Reproduced with an isolated harness: supplying one `shorting_items` error to the final check printed `errors: 1` and returned normally. This was a control-flow test, not a short in the committed PCB.

   Make unresolved electrical/geometric/parity failures return nonzero. Allow only specifically justified warnings. Run preflight from the fabrication entry point, write into a staging directory, and publish the release files only after all checks pass.

5. **P2 — The CPL validator accepts missing parts and incorrect assembly sides.**

   Location: [hardware/tools/check_cpl.py](../hardware/tools/check_cpl.py), lines 73–108.

   The checker iterates only over CPL rows; it does not require each BOM reference to appear exactly once, and it never checks the `Layer` field. In independent copies, deleting U1's CPL row returned status 0. Restoring U1 and changing only its layer to `Bottom` also returned status 0 and printed `ok U1`.

   Require exact BOM/CPL reference-set equality, unique designators, and agreement between CPL layer and PCB footprint side before checking geometry. The current committed files have all 15 intended placements on Top, so these are validator defects rather than a present placement omission.

6. **P2 — The programming interface needs an explicit battery-isolation procedure.**

   Location: [hardware/tools/gen_sch.py](../hardware/tools/gen_sch.py), lines 62–70; [hardware/README.md](../hardware/README.md), line 45.

   J1 pin 1 and the CR2032 positive contact share VBAT without isolation. Connecting a powered programming fixture while a cell is installed therefore connects the fixture supply directly across the cell. A fixture voltage above the cell voltage can charge it; the Energizer specification allows only 1 uA reverse charge. The current programming instructions do not require battery removal or distinguish power output from voltage sensing.

   Specify programming and powered calibration with the battery removed, insert the battery afterward, and make the fixture enforce that sequence. If powered servicing with a cell present is required, add a suitable isolation arrangement. Verify the chosen programmer's power and signal voltages as part of the fixture specification.

   Evidence: schematic net assignment and [Energizer CR2032 reverse-charge limit](https://data.energizer.com/pdfs/cr2032.pdf).

7. **P2 — The selected microphone has a lifecycle risk absent from the production decision.**

   Location: [hardware/tools/gen_sch.py](../hardware/tools/gen_sch.py), lines 52–55; [docs/mic-mcu-options.md](mic-mcu-options.md), “Decision”.

   Infineon currently marks the exact `IM69D130V01XTSA1` ordering code as **not for new design**. Distributor stock alone is insufficient evidence for repeat production. This does not mean existing stock is unusable, but it needs an explicit prototype/limited-build decision and supply plan, or a supported replacement with its footprint and signal processing revalidated.

   Evidence checked 2026-09-27: [Infineon IM69D130 product status](https://www.infineon.com/part/IM69D130). Live distributor stock and assembly pricing were not rechecked in this audit.

**Checks completed**

| Check | Result |
|---|---|
| KiCad version | 10.0.6 |
| ERC, all severities | No errors; 37 missing-library configuration warnings and the documented GPIO/PWR_FLAG warning |
| PCB DRC, all track errors and schematic parity | No geometric errors, no open nets, no parity violations; 17 missing-footprint-library configuration warnings |
| Schematic regeneration | Byte-identical to the committed schematic |
| Complete PCB regeneration | Two independent runs produce byte-identical boards matching the committed board; the project also matches |
| Committed Gerbers and drills | Equal to fresh exports after excluding generation timestamps |
| Gerber ZIP | Exact member and byte agreement with the committed loose files |
| BOM/CPL membership | 12 BOM lines, 15 placements, matching designator sets |
| Existing CPL geometry check | All 15 placements pass, including mic port and battery-holder orientation |
| Drill inventory | Eleven 0.3 mm vias; four 1.0 mm header holes; 0.8 mm microphone port and 3.2 mm keyring NPTH |
| Visual inspection | Schematic PDF and top/bottom renders inspected |

The placed MCU's supply, SPI, UART, programming, LED timer pin assignments, and button EXTI capability agree with its datasheet. The microphone's pin assignment and 0.8 mm port agree with Infineon's documentation. No definite PCB wiring or placement defect was found. Missing library-table configuration prevents claiming a complete installed-library comparison. The schematic is electrically readable but several reference/value labels overlap symbols, and the long bottom note enters the title block.

**Remaining physical and firmware qualification**

The repository contains no firmware, programming image, measured acoustic results, or production test limits. Before release, demonstrate uninterrupted PDM acquisition and decimation within the fitted V003's 2 KB RAM and CPU budget; verify microphone supply/clock sequencing and GPIO supply voltage; compare weighted levels across frequency, SPL, placement, and battery conditions; test invalid-data/overload behavior; measure sleep current; and establish programming, LED/button, current, and acoustic acceptance checks. Define the measurement bandwidth explicitly: the proposed 16 kHz output cannot retain sound above 8 kHz.

The statement in `docs/mic-mcu-options.md` that microphone clipping necessarily appears as exact full-scale PCM samples is also unproven: acoustic overload is specified by distortion, and decimation can remove exact rail values. Do not treat that proposed detector as a validated safeguard. The same section still uses a 108 dBA top-band threshold, whereas the current bare-ear red threshold is above 96 dBA.

Prototype checks should include battery insertion/removal, polarity mistakes, retention, keyring abrasion, sound-port occlusion, and the final case's acoustic response. The current render lacks models for the microphone and switch, so it is not sufficient evidence for their assembled mechanical fit. The committed no-water-wash instruction should be carried into the assembly order. Cost and quantity targets also need a complete assembly quote; the repository's hobby-quantity goal and 1,000-unit BOM estimate are not equivalent.

---

## Response

Each finding was checked against the cited source before acting.

| # | Verdict | Resolution |
|---|---|---|
| 1 | Confirmed: bands 0.40–0.95 / 1.05–1.9 / 2.1–2.65 / 2.9–3.3 MHz, SPI divider powers of two | Clock plan is now 1.5 MHz (48/32 or 24/16), decimated by 64 to 23,437.5 samples/s, with filters designed for that rate. Startup is counted from VDD *and* clock. [hardware/README.md § PDM clock plan](../hardware/README.md#pdm-clock-plan) |
| 2 | Confirmed: 96 dBA gives 38 min | The bands are now levels at the ear, with allowance times computed from `T = 8·2^((85−L)/3)`. A spot reading is stated not to be a dose. The blinking LED is a conditional estimate "if plugs really give 12 dB", with a pointer to fit testing. The back legend now reads "blink = plugs IF 12 dB". |
| 3 | Confirmed: V003 standby 7.6 µA typ (the V002 is *worse*, at 17.5 µA) | The 10–15 % claim is withdrawn. [§ Power](../hardware/README.md#power-unqualified) lists the qualification plan, an under-load cutoff with an invalid state, the ~67 mAh/year standby budget, and a power latch as a rev B option. |
| 4 | Confirmed | `make_pcb.py` exits nonzero. Only `lib_footprint_issues` (missing library table) is allowed, so a footprint mismatch now fails. `fab.py` preflights ERC/DRC/parity and allows only the library-table warnings and the MIC_VDD PWR_FLAG. It stages every output and publishes only after `check_cpl.py` passes. |
| 5 | Confirmed, reproduced | `check_cpl.py` now requires equal BOM/CPL sets, unique designators, and CPL layer = board side. Negative tests (missing U1, U1 on Bottom, duplicated C1) now fail. |
| 6 | Confirmed | The documented procedure is to remove the cell before programming or bench power. That is added to the back silk ("REMOVE CELL TO PROGRAM"), the schematic notes and [§ Programming](../hardware/README.md#programming). |
| 7 | Unresolved | DigiKey lists IM69D130V01XTSA1 as *Active* on 2026-09-27; Infineon's page could not be read to confirm "not for new design". Recorded as a prototype/limited-build decision, with the T5818 as the replacement to revalidate. [§ Microphone supply](../hardware/README.md#microphone-supply) |
| Other | | Schematic notes moved clear of the title block. The unproven clip detector is marked a heuristic, not a safeguard. The stale 108 dBA threshold is corrected. The remaining physical and firmware qualification items are added to *Not verified yet*. |
