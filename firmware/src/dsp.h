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
	uint64_t energy;              // sum of y^2
	int32_t peak;                 // largest |y| seen while accumulating
	int32_t pcm_peak;             // largest |x| straight after the CIC (before weighting)
#ifdef DSP_DIAG
	// Diagnostic build (make DIAG=1): where the quiet-room floor lives. Set r128 after
	// dsp_reset for a 3 MHz PDM clock (R = 128, same output rate).
	uint8_t r128;
	int32_t dc;                   // DC estimate for the unweighted level, Q10
	int32_t lp[3][4];             // low-pass biquads on the weighted signal: x1 x2 y1 y2
	uint64_t e_lp8, e_lp2, e_z;   // energy of A below 8 kHz, A below 2 kHz, unweighted (> 20 Hz)
	int16_t *raw;                 // if set: the next raw_max CIC outputs (centred, before weighting)
	uint16_t raw_n, raw_max;
#endif
} dsp_t;

#define DSP_MS_FRAC 8             // fraction bits of the mean square in the level calculation

void dsp_reset(dsp_t *d, uint32_t skip_samples);
// Feed PDM bytes, MSB first in time. Any length; state carries across calls.
void dsp_feed(dsp_t *d, const uint8_t *buf, uint32_t len);
// A-weighted level relative to a full-scale sine (amplitude DSP_FS), in dB Q8: a full-scale
// 1 kHz sine reads 0. Returns INT32_MIN if nothing was accumulated.
int32_t dsp_level_dbfs_q8(const dsp_t *d);

// Mean square of the weighted signal, with DSP_MS_FRAC fraction bits (0 if nothing accumulated),
// and its level in dBFS Q8. Mean squares can be averaged (the dosimeter) before taking the level.
#define DSP_MS_FS (1ULL << (31 + DSP_MS_FRAC))   // a full-scale sine's mean square
uint64_t dsp_mean_square(const dsp_t *d);
int32_t dsp_ms_dbfs_q8(uint64_t ms);

#ifdef DSP_DIAG
enum { DSP_DIAG_LP8, DSP_DIAG_LP2, DSP_DIAG_Z };
int32_t dsp_diag_dbfs_q8(const dsp_t *d, int which);
#endif

// Exposed for the test: 10*log10(x) in Q8 for x >= 1
int32_t dsp_db10_q8(uint64_t x);
