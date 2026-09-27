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

int32_t db10_q8(uint64_t x) { return dsp_db10_q8(x); }
