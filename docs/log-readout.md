# Reading the dose log without a programmer

Ideas, parked. Rev A's job is to prove that simple metering like this can be done; rev B will be a different board, so this is input for its design rather than work planned for rev A.

Not built. Today the flash dose log is read with the programmer and `sudo make dose-log`. That is fine on the bench but means nobody else can use the log. Everything here would also work on rev A as it is: four LEDs, one button, the light-sensing red LED and the TX pad on J1. The board has no speaker or buzzer, so sending the log as sound is out.

Written 2026-10-13. The numbers below were measured on [dose-example.bin](dose-example.bin) (fob A's busy night: music, drums, the walk home), using `firmware/tools/log_summary.py`.

## Three ways out, in order

### 0. The dose on the LEDs

Done on rev A, more simply: a triple click blinks the whole bar with a period of 1 s at 0 % of the allowance, shrinking linearly to lit at 100 % (see the [README](../README.md#modes)). A blink count for the exact percentage would be the next step.

### 1. A phone camera reads the bar

A web page opens the phone camera, finds the four LEDs, decodes the blinks and draws the same graph as `dose_log.py`. No app and no cable.

- **Coding.** One LED is the clock: it toggles every symbol, so the page needs no timing of its own. The other three each carry one bit per symbol. The page tells the LEDs apart by position. Yellow, orange and red look too alike to a camera to separate by colour.
- **Speed.** A symbol has to stay up for 2–3 camera frames: about 10 symbols/s at 30 fps, so 30 bit/s; 20 symbols/s at 60 fps, so 60 bit/s.
- **Framing.** A start pattern, the header, the data and a CRC. Send it all twice. The page shows OK or "try again".
- **Brightness.** The bar is deliberately dim. During the transfer, run the LEDs at full current (about 0.5–1 mA for under a minute: negligible on the cell). The page should lock exposure where the browser allows it.
- **Later.** Rolling-shutter decoding, where an LED blinking at kHz rates shows up as stripes within one frame, could reach hundreds of bit/s. It depends on the phone model, so prove the frame-based version first.

### 2. A cable to the TX pad

J1's `T` pad is PD5, USART1 TX, already on the board. With a cheap USB-serial adapter, the firmware prints the full log on request: no programmer, no sudo, no minichlink. Power the board from its cell and leave the adapter's 3.3 V unconnected (see the cell warning in [hardware/README.md](../hardware/README.md)). This is the developer path: full resolution, for AC2 comparisons.

### Bonus: data into the fob with the phone screen

The red LED doubles as a light sensor (D4's cathode is on PC2). A phone screen flashing at the fob could send it a few bits per second: enough for a calibration offset or the clock time. Calibration would then need no programmer. Last on the list.

## What to send: a summary, not the full log

The full log is 656 B: 12 B header plus one byte per 67 s sample. At 30 fps that takes about 3 min.

### Compression doesn't help much

Samples are 67 s apart, so during music the level jumps several dB between samples: only 21 % of consecutive samples are equal, and 37 % are within ±0.5 dB.

| Method | Size | vs raw |
|---|---|---|
| Raw | 656 B | 100 % |
| Run-length (value, count) | 1028 B | 157 % |
| Differences, 4-bit codes | 526 B | 80 % |
| Differences, Rice code k=3 | 448 B | 68 % |
| zlib -9 / lzma (reference) | 463 / 473 B | 71 / 72 % |

A quiet night should do better: the floor sits at 35.5–35.8 dBA for hours, so most differences are 0 or ±1 step. Estimated, not measured.

### Summarising per block helps a lot

Send the energy average (LAeq) and the loudest sample (Lmax) of each block, one byte each in 1 dB steps:

| Block | Blocks | LAeq only | LAeq + Lmax | Dose from the blocks |
|---|---|---|---|---|
| 5 min | 161 | 161 B | 322 B | 3.06 % |
| **10 min** | 72 | 72 B | **144 B** | **3.00 %** |
| 15 min | 50 | 50 B | 100 B | 3.04 % |
| 30 min | 24 | 24 B | 48 B | 3.09 % |
| Full log | 643 samples | | 656 B | 3.05 % |

- **The dose survives** because the blocks average energy, and the dose depends only on energy. The fob can also put its exact dose in the header.
- **Lmax brings back the peaks** that an average would smooth away.
- **The graph doesn't need more.** A phone screen is about 350 px wide, so a 12 h night is about 2 min per pixel. What the blocks lose is the up and down inside them: median 2 dB, 90th percentile 7 dB at 10 min.

Sending only turning points, a new point whenever the level leaves ±T dB of the last one, did not beat this on a busy night: 466 B at T = 3 dB, and the dose fell to 2.70 %. Blocks also have a size known in advance.

**Transfer time:** 10 min blocks plus LAeq and Lmax is about 156 B with the header. That is about 45 s at 30 fps or 20 s at 60 fps, sent once.

## Plan

- **Phone camera:** the 10 min summary, which gives the dose and a graph with peaks.
- **TX pad:** the full log.
- **The log format stays as it is.** The fob computes the summary from flash when it sends. The CH32V003 has no multiplier, so the energy sum uses a small table of 2^(x/3) for 0.5 dB steps, plus shifts. That adds roughly 100–200 B of code, against about 2.8 KB free (12,520 B of 15,360).
- **Order:**
  1. The dose on the LEDs.
  2. The TX dump.
  3. The camera transfer and its web page. The web page is most of the work.
  4. Input through the light sensor.
