// Host-side test helper for test_dsp.py: drives the real dsp.c with a simulated PDM mic.
#include <math.h>
#include <stdlib.h>
#include "dsp.h"

static dsp_t D;

// raw CIC outputs captured through DSP_TEST_HOOK
static uint32_t *cap; static uint32_t cap_n, cap_max;
void dsp_test_cic(uint32_t cic) { if (cap && cap_n < cap_max) cap[cap_n++] = cic; }

// 2nd-order single-bit sigma-delta modulator at 1.5 MHz standing in for the microphone.
// A sine of amplitude amp (1.0 = full scale) at f Hz, for seconds; returns the A-weighted
// level in dBFS Q8 from dsp.c after skipping skip output samples.
int32_t run_sine(double f, double amp, double seconds, uint32_t skip, int32_t *peak, int32_t *pcm_peak)
{
	dsp_reset(&D, skip);
	double v1 = 0, v2 = 0, y = 0, ph = 0, dph = 2 * M_PI * f / 1.5e6;
	uint64_t nbytes = (uint64_t)(seconds * 1.5e6 / 8);
	uint8_t buf[64]; uint32_t k = 0;
	for (uint64_t i = 0; i < nbytes; i++) {
		uint8_t b = 0;
		for (int j = 0; j < 8; j++) {
			double u = amp * sin(ph); ph += dph;
			v1 += u - y; v2 += v1 - y;
			y = v2 >= 0 ? 1.0 : -1.0;
			b = (b << 1) | (y > 0);
		}
		buf[k++] = b;
		if (k == sizeof buf) { dsp_feed(&D, buf, k); k = 0; }
	}
	if (k) dsp_feed(&D, buf, k);
	*peak = D.peak; *pcm_peak = D.pcm_peak;
	return dsp_level_dbfs_q8(&D);
}

#ifdef DSP_DIAG
// As run_sine, at modulator clock fs (1.5e6 or 3e6, the latter with the R = 128 CIC); also returns
// the diagnostic levels: A below 8 kHz, A below 2 kHz, unweighted.
int32_t diag_level(int w) { return dsp_diag_dbfs_q8(&D, w); }
void diag_restart(void) { D.n = 0; D.energy = D.e_lp8 = D.e_lp2 = D.e_z = 0; }
void feed_more(const uint8_t *bytes, uint32_t n, uint32_t skip) { D.skip = skip; dsp_feed(&D, bytes, n); }

static int16_t *raw_buf; static uint16_t raw_len;
void set_raw(int16_t *buf, uint16_t n) { raw_buf = buf; raw_len = n; }

int32_t run_sine_diag(double f, double amp, double seconds, double fs, uint32_t skip, int32_t *diag)
{
	dsp_reset(&D, skip);
	D.r128 = fs > 2e6;
	D.raw = raw_buf; D.raw_max = raw_len;
	double v1 = 0, v2 = 0, y = 0, ph = 0, dph = 2 * M_PI * f / fs;
	uint64_t nbytes = (uint64_t)(seconds * fs / 8);
	uint8_t buf[64]; uint32_t k = 0;
	for (uint64_t i = 0; i < nbytes; i++) {
		uint8_t b = 0;
		for (int j = 0; j < 8; j++) {
			double u = amp * sin(ph); ph += dph;
			v1 += u - y; v2 += v1 - y;
			y = v2 >= 0 ? 1.0 : -1.0;
			b = (b << 1) | (y > 0);
		}
		buf[k++] = b;
		if (k == sizeof buf) { dsp_feed(&D, buf, k); k = 0; }
	}
	if (k) dsp_feed(&D, buf, k);
	for (int w = 0; w < 3; w++) diag[w] = dsp_diag_dbfs_q8(&D, w);
	return dsp_level_dbfs_q8(&D);
}
#endif

// Feed arbitrary bytes in uneven chunks and capture raw CIC outputs, for comparison with a
// bit-by-bit reference integrator in Python.
uint32_t run_bytes(const uint8_t *bytes, uint32_t n, uint32_t *out, uint32_t out_max)
{
	dsp_reset(&D, 0);
	cap = out; cap_n = 0; cap_max = out_max;
	uint32_t pos = 0, chunk = 1;
	while (pos < n) {
		uint32_t c = chunk < n - pos ? chunk : n - pos;
		dsp_feed(&D, bytes + pos, c);
		pos += c; chunk = chunk % 13 + 1;         // uneven chunk sizes: state must carry
	}
	cap = 0;
	return cap_n;
}

void dsp_test_sample(dsp_t *d, uint32_t cic);

// Filter input x (at the DSP_FS = 2^18 scale) fed straight to the filters, bypassing the CIC.
int32_t run_x(const int32_t *xs, uint32_t n, uint32_t skip)
{
	dsp_reset(&D, skip);
	for (uint32_t i = 0; i < n; i++) dsp_test_sample(&D, (uint32_t)(xs[i] * 32 + (1L << 23)));
	return dsp_level_dbfs_q8(&D);
}

// A constant input for n samples (idle and DC must not leave a limit cycle).
int32_t run_const(int32_t x, uint32_t n, uint32_t skip)
{
	dsp_reset(&D, skip);
	for (uint32_t i = 0; i < n; i++) dsp_test_sample(&D, (uint32_t)(x * 32 + (1L << 23)));
	return dsp_level_dbfs_q8(&D);
}

int32_t db10_q8(uint64_t x) { return dsp_db10_q8(x); }
