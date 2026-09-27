// See dsp.h. Written for the CH32V003 (RV32EC, no multiplier): every multiply in the per-sample
// path is by a compile-time constant, which GCC turns into shifts and adds, except the one
// runtime multiply that squares each sample.
// -O2, not the project's -Os: at -Os GCC calls the software __mulsi3 for every multiply by a
// constant (9 per sample, ~half the CPU); at -O2 it emits shifts and adds. -O3 unrolls and is
// worse again. Checked by tools/check_hotpath.sh on the linked firmware.
#pragma GCC optimize("O2")
#include "dsp.h"
#include "filters.h"

// Closed form of four integrators stepped over 8 input bits x0..x7 (x0 first):
//   i4 += 8 i3 + 36 i2 + 120 i1 + W4[b]
//   i3 += 8 i2 + 36 i1 + W3[b]
//   i2 += 8 i1 + W2[b]
//   i1 += W1[b]
// Wk[b] counts the paths from each set bit to the end of the byte through k integrators; the
// tables are generated (const, in flash) by tools/design_filters.py.
#include "cic_tables.h"

void dsp_reset(dsp_t *d, uint32_t skip_samples)
{
	uint8_t *p = (uint8_t *)d;
	for (uint32_t k = 0; k < sizeof(*d); k++) p[k] = 0;
	d->skip = skip_samples;
}

// One first-order high-pass section: zero at DC, pole P (Q13).
#define HP(k, P) do { \
	int32_t y_ = x - d->hx[k] + ((d->hy[k] * (P)) >> FILT_Q); \
	d->hx[k] = x; d->hy[k] = y_; x = y_; } while (0)

#ifdef DSP_TEST_HOOK
void dsp_test_cic(uint32_t cic);          // host test: sees every raw CIC output
#endif

// s^2 for s < 2^16 without a multiplier: s = 256 a + b, 2ab = ((a + b)^2 - (a - b)^2) / 2.
// Four table reads instead of ~130 instructions of software __mulsi3.
static inline uint32_t square(uint32_t s)
{
	uint32_t a = s >> 8, b = s & 255;
	uint32_t m = a > b ? a - b : b - a;
	return (SQ[a] << 16) + ((SQ[a + b] - SQ[m]) << 7) + SQ[b];
}

static inline void sample(dsp_t *d, uint32_t cic)
{
#ifdef DSP_TEST_HOOK
	dsp_test_cic(cic);
#endif
	// CIC output is 0..2^24 for 0..100 % ones; centre and scale to +-DSP_FS
	int32_t x = ((int32_t)cic - (1L << 23)) >> 7;
	int32_t ax = x < 0 ? -x : x;
	HP(0, HP_P0);
	HP(1, HP_P1);
	HP(2, HP_P2);
	HP(3, HP_P3);
	// Correction biquad, direct form I. Products can exceed 31 bits, but the true result
	// (y << FILT_Q) fits: unsigned wrap-around makes the intermediate overflow harmless.
	uint32_t acc = (uint32_t)x * BQ_B0 + (uint32_t)d->bx1 * BQ_B1 + (uint32_t)d->bx2 * BQ_B2
	             - (uint32_t)d->by1 * BQ_A1 - (uint32_t)d->by2 * BQ_A2;
	int32_t y = (int32_t)acc >> FILT_Q;
	d->bx2 = d->bx1; d->bx1 = x;
	d->by2 = d->by1; d->by1 = y;
	if (d->skip) { d->skip--; return; }
	if (ax > d->pcm_peak) d->pcm_peak = ax;
	int32_t a = y < 0 ? -y : y;
	if (a > d->peak) d->peak = a;
	d->energy += square(((uint32_t)(y < 0 ? -y : y) + (1u << (DSP_SQ_SHIFT - 1))) >> DSP_SQ_SHIFT);   // rounded: truncation biases quiet rooms low
	d->n++;
}

// One byte of the order-4 CIC in closed form (see the tables above).
#define CIC_BYTE(b) do { \
	i4 += (i3 << 3) + (i2 << 5) + (i2 << 2) + (i1 << 7) - (i1 << 3) + W4[b]; \
	i3 += (i2 << 3) + (i1 << 5) + (i1 << 2) + W3[b]; \
	i2 += (i1 << 3) + W2[b]; \
	i1 += W1[b]; } while (0)

static inline uint32_t comb(dsp_t *d, uint32_t i4)
{
	uint32_t c1 = i4 - d->d1; d->d1 = i4;
	uint32_t c2 = c1 - d->d2; d->d2 = c1;
	uint32_t c3 = c2 - d->d3; d->d3 = c2;
	uint32_t c4 = c3 - d->d4; d->d4 = c3;
	return c4;
}

void dsp_feed(dsp_t *d, const uint8_t *buf, uint32_t len)
{
	uint32_t i1 = d->i1, i2 = d->i2, i3 = d->i3, i4 = d->i4;
	uint8_t phase = d->phase;
	const uint8_t *end = buf + len;
	// Fast path, which is every call from the DMA ISR (64-byte halves): whole output samples of
	// 8 bytes each, no per-byte phase bookkeeping.
	if (!phase) {
		while (end - buf >= 8) {
			for (int k = 0; k < 8; k++) { uint8_t b = buf[k]; CIC_BYTE(b); }
			buf += 8;
			sample(d, comb(d, i4));
		}
	}
	for (; buf < end; buf++) {               // anything else, byte by byte
		uint8_t b = *buf;
		CIC_BYTE(b);
		if (++phase == 8) { phase = 0; sample(d, comb(d, i4)); }
	}
	d->i1 = i1; d->i2 = i2; d->i3 = i3; d->i4 = i4;
	d->phase = phase;
}

// 10*log10(x) in Q8, integer only. log2 by leading-bit position plus 12 rounds of
// square-and-compare on a Q15 mantissa; 10*log10(2) = 3.0103.
int32_t dsp_db10_q8(uint64_t x)
{
	if (!x) return INT32_MIN;
	int32_t e = 63;
	while (!(x >> e)) e--;
	// mantissa m in [1, 2) as Q15
	uint32_t m = e >= 15 ? (uint32_t)(x >> (e - 15)) : (uint32_t)(x << (15 - e));
	int32_t frac = 0;                          // Q12 fraction of log2
	for (int bit = 11; bit >= 0; bit--) {
		m = (m * m + (1u << 14)) >> 15;        // square (rounded): log2 doubles
		if (m >= (2u << 15)) { m >>= 1; frac |= 1 << bit; }
	}
	int32_t log2_q8 = (e << 8) + ((frac + 8) >> 4);
	return (int32_t)(((int64_t)log2_q8 * 197283 + 32768) >> 16);   // * 3.0103 (197283 / 2^16)
}

int32_t dsp_level_dbfs_q8(const dsp_t *d)
{
	if (!d->n) return INT32_MIN;
	// mean square, and the full-scale sine's mean square in the same units:
	// amplitude DSP_FS >> DSP_SQ_SHIFT = 2^14, mean square 2^27
	uint64_t ms = d->energy / d->n;
	if (!ms) ms = 1;
	return dsp_db10_q8(ms) - dsp_db10_q8(1ULL << 27);
}
