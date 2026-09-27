// qemu-user bench (test/bench.sh): feed 0.1 s of PDM through dsp_feed in 64-byte chunks (as the DMA ISR does),
// then exit via the Linux exit syscall. RV32E: syscall number in t0.
#include "dsp.h"
#include "pdm.h"
static dsp_t d;
void *memset(void *p, int c, unsigned n) { unsigned char *q = p; while (n--) *q++ = c; return p; }
void __attribute__((noinline, used, noreturn)) body(void)
{
#ifndef EMPTY
	dsp_reset(&d, 0);
	for (unsigned k = 0; k < sizeof PDM; k += 64) dsp_feed(&d, PDM + k, 64);
#endif
	register long a0 asm("a0") = d.n & 0x7f;
	asm volatile("li t0, 93\n ecall" :: "r"(a0));
	for (;;);
}
char stack[4096] __attribute__((aligned(16)));
void __attribute__((naked, noreturn)) _start(void) { asm volatile("la sp, stack+4096\n j body"); }
