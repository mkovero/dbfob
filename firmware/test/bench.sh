#!/bin/sh
# Count the RV32EC instructions dsp_feed executes per second of audio, under qemu user mode.
# Input: 0.1 s of a -12 dBFS 1 kHz sine from a 2nd-order sigma-delta modulator, fed in 64-byte
# chunks as the DMA ISR does. Instructions are not cycles: the V2A core adds flash wait states
# and branch penalties (~1.2-1.5 cycles per instruction); the firmware measures the real ISR load.
set -e
cd "$(dirname "$0")/.."
B=build/bench; mkdir -p $B
python3 - "$B/pdm.h" <<'PY'
import sys, math, numpy as np
n = int(0.1 * 1.5e6); u = 0.25 * np.sin(2 * math.pi * 1000 * np.arange(n) / 1.5e6)
v1 = v2 = 0.0; y = -1.0; bits = np.zeros(n, np.uint8)
for i in range(n):
    v1 += u[i] - y; v2 += v1 - y; y = 1.0 if v2 >= 0 else -1.0; bits[i] = y > 0
b = np.packbits(bits)
open(sys.argv[1], 'w').write('static const unsigned char PDM[%d]={%s};\n' % (len(b), ','.join(map(str, b))))
PY
riscv64-elf-gcc -Os -march=rv32ec -mabi=ilp32e -nostdlib -static -Isrc -I$B test/bench.c src/dsp.c \
	-Lch32fun/misc -lgcc -o $B/bench.elf
qemu-riscv32-static -one-insn-per-tb -d exec,nochain -D /dev/stdout $B/bench.elf 2>/dev/null |
	grep '^Trace' | awk '{print $NF}' | sort | uniq -c | sort -rn |
	awk '{t += $1; print} END {printf "%.1f M instructions per second of audio (%.0f%% of 48 MHz at 1 instr/cycle)\n", t / 1e5, t / 1e5 / 48 * 100}'
