# dbfob firmware

Firmware for the rev A board: a CH32V003F4P6 with an IM69D130 PDM mic. It is built on [ch32fun](https://github.com/cnlohr/ch32fun), included as a submodule.

**Status: builds and passes host tests, but has never run on hardware.** Every constant marked `BRINGUP` in `dbfob.c` is an estimate that must be set on the bench.

## What it does

1. The board sits in standby until the button (PC0) is pressed.
2. It senses ambient light through D4 to set LED brightness.
3. It powers the mic from PC6 and clocks it at **1.5 MHz**: SPI1 SCK on PC5, 48 MHz / 32.
4. It captures PDM from MISO (PC7) by DMA into a 128-byte ring. Each 64-byte half is processed in the DMA interrupt.
5. It discards 150 ms of mic start-up and filter settling, then integrates **3 s** of A-weighted energy. VDD is read under load every 50 ms throughout.
6. It shows two verdicts for 2 s (see the [top-level README](../README.md#colour-bands)):
   - **Steady LED:** bare ear.
   - **Blinking LED:** with plugs giving 12 dB.
   - **Alternating G/R:** invalid reading (battery below the cutoff, no samples, or DMA overrun).
7. It prints one line per reading on USART1 TX (PD5, J1 pin 4 "T", 115200 8N1), then returns to standby.

Example output line:

```
dbfob dBA=94.2 dBFS=-35.7 n=70313 peak=1873 pcm_peak=1510 overload=0 vdd_idle=3012 vdd_min=2941 light_us=38210 duty=112 cpu=31% overruns=0
```

## Signal chain

Everything below is in `src/dsp.c`. The same file is compiled into the firmware and into the host test.

| Stage | Rate | Implementation |
|---|---|---|
| PDM in | 1.5 Mbit/s | SPI RX-only master, CPOL 0 / CPHA 0 (SELECT = GND: DATA valid while CLK low, sampled on the rising edge) |
| CIC, order 4, R = 64 | → 23,437.5 S/s | Closed-form byte step: 4 table lookups per byte (`src/cic_tables.h`, in flash) |
| A-weighting | 23,437.5 S/s | 4 first-order high-pass sections (the A curve's real poles), then 1 biquad fitted to the rest: the 12,194 Hz pole pair, CIC droop, and matched-z error. Q13 constants. |
| Energy | per sample | Σ y², square by table (`SQ[]`), 64-bit accumulator |
| Level | once | Integer 10·log10, Q8 dB |

**No hardware multiplier.** The V003 has none, and at `-Os` GCC calls libgcc's software multiply for every constant multiply. `dsp.c` is therefore compiled at `-O2`, where constant multiplies become shifts and adds, and the one runtime multiply (the square) is a table lookup. `tools/check_hotpath.sh` fails the build check if a software multiply reappears in the capture path.

**Verified on the host** (`make test`, with UBSan on):
- The CIC matches a bit-by-bit reference exactly.
- The chain is within **0.02 dB of IEC 61672 A-weighting from 50 Hz to 8 kHz**, and 0.09 dB at 31.5 Hz and 10 kHz.
- It is linear to within 0.12 dB from −60 to −6 dBFS.
- At −3 dBFS it has headroom: the peak intermediate uses 53k of the 131k that the 32-bit products allow.
- The simulated mic is a 2nd-order sigma-delta modulator.

**CPU**, from `make bench`: **11.3 M RV32EC instructions per second of audio** (about 39 per byte, about 168 per sample). The V2A core needs roughly 1.2–1.5 cycles per instruction, so this estimates **28–35 % of 48 MHz**. The firmware measures the real ISR share and prints it as `cpu=`.

**Resources:** flash 10.1 KB of 16 KB, static RAM 256 B of 2 KB.

## Build

```sh
git submodule update --init         # ch32fun
make check                          # build + hot-path check + host DSP tests
make bench                          # optional: instruction count under qemu-riscv32
```

This needs `riscv64-elf-gcc` and `riscv64-elf-newlib` (Arch: `pacman -S riscv64-elf-gcc riscv64-elf-newlib`). The host tests also need `gcc`, `python3`, `numpy` and `scipy`, and `make bench` needs `qemu-riscv32-static`.

`make filters` regenerates `src/filters.h` and `src/cic_tables.h` from `tools/design_filters.py`. The script checks the quantized response against the A curve and fails if it is off by more than 1 dB.

## Flash

**Take the coin cell out first.** J1 pin 1 is wired straight to the cell's + terminal, and a programmer supplying 3.3 V would charge it (see [hardware/README.md](../hardware/README.md#programming)).

Connect a WCH-LinkE to J1 (`+ D G T` = 3V3, SWIO, GND, and TX to your USB-UART RX), then run `make flash`. The firmware stays awake for 3 s after reset, sweeping the LEDs, so the programmer can reattach later. In standby SWIO is not answering; press the button or power-cycle to get a window.

## Bring-up checklist

Work down this list in order and record the numbers in `hardware/README.md`.

1. **Before power.** Check VBAT to GND is not a short. Check part orientation against the placement review.
2. **First power, from the WCH-LinkE with no cell.** `make flash`, then look for the boot banner with `vdd=`. The LEDs sweep G Y O R dimly.
3. **Mic capture.** Press the button in a quiet room and check:
   - `n` is about 70,300 (3 s × 23,437.5).
   - `overruns=0`.
   - `cpu=` is recorded. The estimate is 28–35 %, and anything under about 70 % is fine.
   - `pcm_peak` is well below 58,982 (the overload flag).
4. **Level calibration.** Put pink noise at 85, 95 and 105 dBA from a reference meter at the same spot. Set `CAL_DB_Q8` from the mean difference, then repeat hand-held to get the hand-held offset.
5. **VDD reference.** Compare `vdd_idle` with a multimeter on VBAT and trim `VREFINT_MV`.
6. **Battery.** Feed J1 from a bench supply through about 30–50 Ω, to mimic a tired cell. Step down from 3.0 V and note where `vdd_min` crosses the V003's 2.7 V. Set `VBAT_MIN_MV` with margin and confirm the invalid pattern appears. Then repeat with real cells at different charge levels ([hardware/README.md § Power](../hardware/README.md#power-unqualified)).
7. **Light sense.** Record `light_us` in the dark, in room light and in daylight, then set `LIGHT_BRIGHT_US` and `LIGHT_DARK_US`. Check that the dark-room brightness (`DUTY_MIN`) is visible without lighting up the room.
8. **Standby current.** With the cell's path through a µA meter and the programmer disconnected, compare against the datasheet's 7.6 µA.

## Not done yet

- Storing calibration constants in flash, instead of setting them at compile time.
- Double-press dosimeter mode.
- Pocket (occlusion) detection.
- A clip heuristic beyond the PCM-peak flag, which is not validated as a safeguard.
- Logarithmic brightness mapping.
