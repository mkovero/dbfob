#!/bin/sh
# The V003 has no multiplier: the per-byte and per-sample DSP code must not call libgcc's
# software multiply (__mulsi3/__muldi3). At -Os GCC does so for constant multiplies, which is
# why src/dsp.c is compiled at -O2 via a pragma - this catches that pragma being lost.
set -e
cd "$(dirname "$0")/.."
bad=$(riscv64-elf-objdump -d dbfob.elf | awk '/^[0-9a-f]+ <(dsp_feed|sample|DMA1_Channel2_IRQHandler)[.>]/{f=1;next} /^[0-9a-f]+ </{f=0} f' | grep -cE '<__mul(si|di)3>' || true)
if [ "$bad" -ne 0 ]; then echo "hot path calls software multiply $bad time(s)"; exit 1; fi
echo "hot path: no software multiply"
