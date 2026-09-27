// PDM -> A-weighted energy. Portable C: the same file builds for the CH32V003 and for the host
// test (test/test_dsp.py), so what is tested is what ships.
#pragma once
#include <stdint.h>

// Full scale: an all-ones PDM stream decimates to +DSP_FS (and all-zeros to -DSP_FS).
#define DSP_FS (1L << 16)

typedef struct {
	// CIC order 4: integrators run at the bit rate (8 bits per call of the byte step)
	uint32_t i1, i2, i3, i4;
	uint32_t d1, d2, d3, d4;      // comb delays
	uint8_t phase;                // bytes into the current output sample (0..7)
	// A-weighting: four first-order high-pass sections, then one correction biquad
	int32_t hx[4], hy[4];
	int32_t bx1, bx2, by1, by2;
	// results
	uint32_t skip;                // output samples still to discard (mic start-up, filter settling)
	uint32_t n;                   // samples accumulated
	uint64_t energy;              // sum of (y >> DSP_SQ_SHIFT)^2
	int32_t peak;                 // largest |y| seen while accumulating
	int32_t pcm_peak;             // largest |x| straight after the CIC (before weighting)
} dsp_t;

#define DSP_SQ_SHIFT 2            // |y| is at most ~2^17; >> 2 keeps it under 2^16 for the table square

void dsp_reset(dsp_t *d, uint32_t skip_samples);
// Feed PDM bytes, MSB first in time. Any length; state carries across calls.
void dsp_feed(dsp_t *d, const uint8_t *buf, uint32_t len);
// A-weighted level relative to a full-scale sine (amplitude DSP_FS), in dB Q8: a full-scale
// 1 kHz sine reads 0. Returns INT32_MIN if nothing was accumulated.
int32_t dsp_level_dbfs_q8(const dsp_t *d);

// Exposed for the test: 10*log10(x) in Q8 for x >= 1
int32_t dsp_db10_q8(uint64_t x);
