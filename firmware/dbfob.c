// dbfob firmware, rev A board (CH32V003F4P6 + IM69D130).
//
// Double click: spot check. The fob wakes from standby, powers the mic, captures 3 s of PDM over
// SPI1+DMA while the LED bar fills as a progress bar, A-weights it (src/dsp.c), and shows two
// verdicts on the LED bar for ~2 s: steady LED = bare ear, blinking LED = with plugs giving 12 dB.
// Long press: dosimeter on / off; triple click shows the dose so far: the whole bar blinks with a
// period of 1 s at 0 % of the daily allowance, shrinking linearly to lit at 100 %.
// Every reading is also printed on USART1 TX (PD5, J1 "T") for calibration against a reference meter.
//
// Pins (hardware/README.md):
//   PC5 SPI1 SCK  -> MIC_CLK   1.5 MHz (48 MHz / 32)
//   PC7 SPI1 MISO <- MIC_DATA  sampled on the rising edge (SELECT = GND: data valid while CLK low)
//   PC6 GPIO      -> MIC_VDD   mic powered only while measuring
//   PD3 TIM2_CH2 D1 G, PD2 TIM1_CH1 D2 Y, PC4 TIM1_CH4 D3 O, PC3 TIM1_CH3 D4 R (anodes via R)
//   PC2           D4 cathode: low = can light; high then input = ambient light sense
//   PC0           button to GND, EXTI0 wake
//
// NOT YET VALIDATED ON HARDWARE. Constants marked BRINGUP are estimates to set on the bench.
#include "ch32fun.h"
#include <stdio.h>
#include "dsp.h"

// ---- measurement -----------------------------------------------------------------------------
#define FS_OUT_HZ_X2      46875          // 2 x 23,437.5 S/s
#define MEASURE_MS        3000
#define SETTLE_MS         150            // mic start-up (<= 50 ms after VDD + clock) + filter settling
// IM69D130: -36 dBFS at 94 dB SPL, so 0 dBFS = 130 dB SPL. BRINGUP: trim by substitution
// against a reference meter, and add the hand-held offset (README.md "Calibration").
#define CAL_DB_Q8         (130 * 256)
#define PLUG_DB           12             // the blinking LED's assumed attenuation
// PCM peak above this fraction of full scale (after the CIC) = treat as overload -> red
#define OVERLOAD_PCM      ((DSP_FS * 9) / 10)

// ---- battery ---------------------------------------------------------------------------------
// The V003 is specified from 2.7 V. Below this under load the reading is refused. BRINGUP: set
// from the qualification in hardware/README.md "Power".
#define VBAT_MIN_MV       2800
#define VREFINT_MV        1200           // datasheet 1.17-1.23 V; BRINGUP: calibrate per board

// ---- display ---------------------------------------------------------------------------------
// ---- button ----------------------------------------------------------------------------------
// A double click starts a measurement, a triple click shows the dose; a single press, or a short
// squeeze in a pocket, does nothing.
// BRINGUP: tune by feel.
#define CLICK_MAX_MS      500            // a click held longer than this is not a click
#define CLICK_GAP_MS      400            // the next click must start within this of the last release
#define DEBOUNCE_MS       20
#define RELEASE_QUIET_MS  300            // after letting go of a long press, before the first dose sample
#define LONG_PRESS_MS     2000           // starts / stops the dosimeter; long enough not to happen in a pocket by chance

// ---- dosimeter -------------------------------------------------------------------------------
#define DOSE_AWU_WINDOW   63             // AWU period = 61440 * 63 / LSI (128 kHz nominal) = ~30 s
#define DOSE_TICKS_PER_SAMPLE 2          // one sample per ~60 s
#define DOSE_SAMPLE_MS    1000           // 1 s/min: ~165 uA average, ~2 mAh per 12 h night (34461A, board 1)
#define DOSE_MAX_S        (12 * 3600UL)  // stops by itself after this

#define SHOW_MS           2000
#define BLINK_MS          250
#define DOSE_SHOW_MS      3000
#define DOSE_BLINK_SLOW_MS 1000          // blink period at 0 % of the daily allowance, shrinking linearly to 0 at 100 %
#define BAR_GAP_MS        200            // dark pause between the full progress bar and the verdict
#define PWM_TOP           999            // 48 kHz PWM
// light sense: D4 discharge time -> brightness. BRINGUP: both thresholds from bench readings.
#define LIGHT_BRIGHT_US   2000           // faster than this: daylight, full brightness
#define LIGHT_DARK_US     50000          // slower than this: dark room, minimum brightness
#define DUTY_MIN          10             // of PWM_TOP: dim enough for a dark club
#define DUTY_MAX          PWM_TOP

enum { LED_G, LED_Y, LED_O, LED_R, LED_NONE };

static volatile dsp_t dsp;
static uint8_t pdm[128];                 // DMA ring: two halves of 64 bytes = 8 output samples each
static volatile uint32_t isr_cycles, overruns;
static volatile uint8_t capturing;
#ifdef DBFOB_DIAG
static uint8_t mic_3mhz;                 // diagnostics: clock the mic at 3 MHz (48 MHz / 16, R = 128)
#endif

// ---- PDM capture: SPI1 RX-only master + DMA1 channel 2 ---------------------------------------
void DMA1_Channel2_IRQHandler(void) __attribute__((interrupt));
void DMA1_Channel2_IRQHandler(void)
{
	uint32_t t0 = SysTick->CNT;
	uint32_t f = DMA1->INTFR;
	DMA1->INTFCR = DMA1_IT_GL2 | DMA1_IT_HT2 | DMA1_IT_TC2;
	if ((f & DMA1_IT_HT2) && (f & DMA1_IT_TC2)) overruns++;   // both halves done: we fell behind
	if (capturing) {
		if (f & DMA1_IT_HT2) dsp_feed((dsp_t *)&dsp, pdm, 64);
		if (f & DMA1_IT_TC2) dsp_feed((dsp_t *)&dsp, pdm + 64, 64);
	}
	isr_cycles += SysTick->CNT - t0;
}

static void mic_start(void)
{
	funDigitalWrite(PC6, FUN_HIGH);                          // MIC_VDD
	funPinMode(PC5, GPIO_CFGLR_OUT_50Mhz_AF_PP);             // SCK
	funPinMode(PC7, GPIO_CFGLR_IN_FLOAT);                    // MISO

	RCC->AHBPCENR |= RCC_AHBPeriph_DMA1;
	RCC->APB2PCENR |= RCC_APB2Periph_SPI1;
	RCC->APB2PRSTR |= RCC_APB2Periph_SPI1;
	RCC->APB2PRSTR &= ~RCC_APB2Periph_SPI1;
	DMA1_Channel2->CFGR = 0;
	DMA1_Channel2->PADDR = (uint32_t)&SPI1->DATAR;
	DMA1_Channel2->MADDR = (uint32_t)pdm;
	DMA1_Channel2->CNTR = sizeof pdm;
	DMA1_Channel2->CFGR = DMA_Priority_VeryHigh | DMA_MemoryDataSize_Byte | DMA_PeripheralDataSize_Byte |
	                      DMA_MemoryInc_Enable | DMA_Mode_Circular | DMA_DIR_PeripheralSRC |
	                      DMA_IT_HT | DMA_IT_TC | DMA_CFGR1_EN;
	NVIC_EnableIRQ(DMA1_Channel2_IRQn);
	// CPOL 0 / CPHA 0: sample on the rising edge. RX-only master clocks continuously once enabled.
	SPI1->CTLR2 = SPI_CTLR2_RXDMAEN;
	// software NSS held high (SSI), or the master sees a mode fault and drops to slave
	SPI1->CTLR1 = SPI_NSS_Soft | SPI_NSSInternalSoft_Set | SPI_CPHA_1Edge | SPI_CPOL_Low | SPI_DataSize_8b | SPI_FirstBit_MSB |
	              SPI_Mode_Master | SPI_Direction_2Lines_RxOnly |
#ifdef DBFOB_DIAG
	              (mic_3mhz ? SPI_BaudRatePrescaler_16 : SPI_BaudRatePrescaler_32);
#else
	              SPI_BaudRatePrescaler_32;
#endif
	SPI1->CTLR1 |= CTLR1_SPE_Set;
}

static void mic_stop(void)
{
	capturing = 0;
	SPI1->CTLR1 &= CTLR1_SPE_Reset;
	NVIC_DisableIRQ(DMA1_Channel2_IRQn);
	DMA1_Channel2->CFGR = 0;
	RCC->APB2PRSTR |= RCC_APB2Periph_SPI1;                   // RX-only master: reset is the clean stop
	RCC->APB2PRSTR &= ~RCC_APB2Periph_SPI1;
	RCC->APB2PCENR &= ~RCC_APB2Periph_SPI1;
	RCC->AHBPCENR &= ~RCC_AHBPeriph_DMA1;
	funPinMode(PC5, GPIO_CFGLR_OUT_2Mhz_PP);
	funDigitalWrite(PC5, FUN_LOW);
	funDigitalWrite(PC6, FUN_LOW);                           // mic off: no standby current
}

// ---- VDD from the internal reference ---------------------------------------------------------
static void adc_init(void)
{
	RCC->APB2PCENR |= RCC_APB2Periph_ADC1;
	RCC->CFGR0 &= ~(0x1F << 11);                             // ADCCLK = HCLK / 2
	ADC1->RSQR1 = 0; ADC1->RSQR2 = 0;
	ADC1->RSQR3 = 8;                                         // channel 8: Vrefint
	ADC1->SAMPTR2 = 7 << (3 * 8);                            // longest sample time for Vrefint
	ADC1->CTLR2 = ADC_ADON | ADC_EXTSEL;
	Delay_Us(10);
	ADC1->CTLR2 |= ADC_RSTCAL; while (ADC1->CTLR2 & ADC_RSTCAL);
	ADC1->CTLR2 |= ADC_CAL; while (ADC1->CTLR2 & ADC_CAL);
}

static uint32_t vdd_mv(void)
{
	ADC1->CTLR2 |= ADC_SWSTART;
	while (!(ADC1->STATR & ADC_EOC));
	uint32_t raw = ADC1->RDATAR;
	return raw ? VREFINT_MV * 1023 / raw : 0;
}

// ---- LEDs: TIM1 CH1/3/4 + TIM2 CH2 PWM -------------------------------------------------------
static void leds_init(void)
{
	RCC->APB2PCENR |= RCC_APB2Periph_TIM1;
	RCC->APB1PCENR |= RCC_APB1Periph_TIM2;
	TIM1->PSC = 0; TIM1->ATRLR = PWM_TOP;
	TIM2->PSC = 0; TIM2->ATRLR = PWM_TOP;
	// PWM mode 1 with preload: TIM1 CH1 (PD2), CH3 (PC3), CH4 (PC4); TIM2 CH2 (PD3)
	TIM1->CHCTLR1 = TIM_OC1M_2 | TIM_OC1M_1 | TIM_OC1PE;
	TIM1->CHCTLR2 = TIM_OC1M_2 | TIM_OC1M_1 | TIM_OC1PE | ((TIM_OC1M_2 | TIM_OC1M_1 | TIM_OC1PE) << 8);
	TIM1->CCER = TIM_CC1E | TIM_CC3E | TIM_CC4E;
	TIM1->BDTR = TIM_MOE;
	TIM2->CHCTLR1 = (TIM_OC1M_2 | TIM_OC1M_1 | TIM_OC1PE) << 8;
	TIM2->CCER = TIM_CC2E;
	TIM1->CH1CVR = TIM1->CH3CVR = TIM1->CH4CVR = 0; TIM2->CH2CVR = 0;
	TIM1->SWEVGR = TIM_UG; TIM2->SWEVGR = TIM_UG;
	TIM1->CTLR1 = TIM_ARPE | TIM_CEN;
	TIM2->CTLR1 = TIM_ARPE | TIM_CEN;
}

static void leds_pins(void)
{
	funPinMode(PD3, GPIO_CFGLR_OUT_2Mhz_AF_PP);
	funPinMode(PD2, GPIO_CFGLR_OUT_2Mhz_AF_PP);
	funPinMode(PC4, GPIO_CFGLR_OUT_2Mhz_AF_PP);
	funPinMode(PC3, GPIO_CFGLR_OUT_2Mhz_AF_PP);
	funPinMode(PC2, GPIO_CFGLR_OUT_2Mhz_PP);
	funDigitalWrite(PC2, FUN_LOW);                           // D4 cathode to ground
}

static void led_set(int which, uint32_t duty)
{
	TIM2->CH2CVR = which == LED_G ? duty : 0;
	TIM1->CH1CVR = which == LED_Y ? duty : 0;
	TIM1->CH4CVR = which == LED_O ? duty : 0;
	TIM1->CH3CVR = which == LED_R ? duty : 0;
}

// Two LEDs at once (steady + blinking) share the bar by alternating at the PWM level:
static void leds_two(int steady, int blink, int blink_on, uint32_t duty)
{
	TIM2->CH2CVR = (steady == LED_G || (blink_on && blink == LED_G)) ? duty : 0;
	TIM1->CH1CVR = (steady == LED_Y || (blink_on && blink == LED_Y)) ? duty : 0;
	TIM1->CH4CVR = (steady == LED_O || (blink_on && blink == LED_O)) ? duty : 0;
	TIM1->CH3CVR = (steady == LED_R || (blink_on && blink == LED_R)) ? duty : 0;
}

// Progress bar: the lowest `n` LEDs lit (0 = all off)
static void leds_bar(int n, uint32_t duty)
{
	TIM2->CH2CVR = n > LED_G ? duty : 0;
	TIM1->CH1CVR = n > LED_Y ? duty : 0;
	TIM1->CH4CVR = n > LED_O ? duty : 0;
	TIM1->CH3CVR = n > LED_R ? duty : 0;
}

// ---- ambient light: D4 reverse-biased, time the photocurrent discharge ------------------------
static uint32_t light_us(void)
{
	funPinMode(PC3, GPIO_CFGLR_OUT_2Mhz_PP);                 // anode side (through R7) low
	funDigitalWrite(PC3, FUN_LOW);
	funDigitalWrite(PC2, FUN_HIGH);                          // cathode high: charge the junction
	Delay_Us(20);
	funPinMode(PC2, GPIO_CFGLR_IN_FLOAT);
	uint32_t t0 = SysTick->CNT, limit = (LIGHT_DARK_US * 2) * (FUNCONF_SYSTEM_CORE_CLOCK / 1000000);
	uint32_t dt;
	while ((dt = SysTick->CNT - t0) < limit && funDigitalRead(PC2));
	leds_pins();
	return dt / (FUNCONF_SYSTEM_CORE_CLOCK / 1000000);
}

static uint32_t duty_for_light(uint32_t us)
{
	if (us <= LIGHT_BRIGHT_US) return DUTY_MAX;
	if (us >= LIGHT_DARK_US) return DUTY_MIN;
	// geometric interpolation would be nicer; linear in log is BRINGUP work
	return DUTY_MIN + (DUTY_MAX - DUTY_MIN) * (LIGHT_DARK_US - us) / (LIGHT_DARK_US - LIGHT_BRIGHT_US);
}

// ---- verdicts --------------------------------------------------------------------------------
static int band(int32_t dba_q8)
{
	if (dba_q8 < (int32_t)(83.5 * 256)) return LED_G;         // <= 83
	if (dba_q8 < (int32_t)(90.5 * 256)) return LED_Y;         // 84-90
	if (dba_q8 < (int32_t)(96.5 * 256)) return LED_O;         // 91-96
	return LED_R;                                              // >= 97
}

static void show_invalid(uint32_t duty)                     // battery / invalid: G and R alternate
{
	for (int i = 0; i < 6; i++) { led_set(i & 1 ? LED_R : LED_G, duty); Delay_Ms(150); }
	led_set(LED_NONE, 0);
}

static void print_q8(const char *name, int32_t q8)
{
	if (q8 == INT32_MIN) { printf(" %s=none", name); return; }
	int32_t a = q8 < 0 ? -q8 : q8;
	printf(" %s=%s%ld.%01ld", name, q8 < 0 ? "-" : "", (long)(a >> 8), (long)(((a & 255) * 10) >> 8));
}

typedef struct {
	uint64_t ms;                                              // weighted mean square (dsp_mean_square)
	int32_t dba;                                              // Q8, INT32_MIN if nothing accumulated
	int overload, invalid;
} reading_t;

// Capture measure_ms of audio. With bar_duty set, the LED bar fills G -> R meanwhile: it confirms
// the press and shows when the verdict comes. Prints one line, tagged `tag`.
static reading_t measure(const char *tag, uint32_t measure_ms, uint32_t bar_duty, uint32_t light)
{
	reading_t r;
	uint32_t v_idle = vdd_mv(), v_min = v_idle;

	dsp_reset((dsp_t *)&dsp, SETTLE_MS * FS_OUT_HZ_X2 / 2000);
#ifdef DBFOB_DIAG
	dsp.r128 = mic_3mhz;
#endif
	isr_cycles = 0; overruns = 0;
	capturing = 1;
	uint32_t t0 = SysTick->CNT;
	mic_start();
	for (uint32_t ms = 0; ms < SETTLE_MS + measure_ms; ms += 50) {
		if (bar_duty) leds_bar((ms + 50) * 4 / (SETTLE_MS + measure_ms), bar_duty);
		// Busy-wait: sleeping here (WFI between DMA interrupts) hung on board 1 - the DMA
		// interrupt never woke the core. Running costs ~3 mA of the 8.4 mA a sample draws.
		Delay_Ms(50);
		uint32_t v = vdd_mv();                                 // VDD under load, throughout
		if (v < v_min) v_min = v;
	}
	mic_stop();
	leds_bar(0, 0);
	uint32_t total = SysTick->CNT - t0;

	r.ms = dsp_mean_square((dsp_t *)&dsp);
	int32_t dbfs = dsp_level_dbfs_q8((dsp_t *)&dsp);
	r.dba = dbfs == INT32_MIN ? INT32_MIN : dbfs + CAL_DB_Q8;
	r.overload = dsp.pcm_peak >= OVERLOAD_PCM;
	r.invalid = v_min < VBAT_MIN_MV || !dsp.n || overruns;

	printf("%s", tag);
	print_q8("dBA", r.dba); print_q8("dBFS", dbfs);
	printf(" n=%lu peak=%ld pcm_peak=%ld overload=%d vdd_idle=%lu vdd_min=%lu light_us=%lu duty=%lu"
	       " cpu=%lu%% overruns=%lu%s\n",
	       (unsigned long)dsp.n, (long)dsp.peak, (long)dsp.pcm_peak, r.overload, (unsigned long)v_idle,
	       (unsigned long)v_min, (unsigned long)light, (unsigned long)bar_duty,
	       (unsigned long)(total ? (uint64_t)isr_cycles * 100 / total : 0), (unsigned long)overruns,
	       r.invalid ? " INVALID" : "");
#ifdef DBFOB_DIAG
	// where the level lives: A-weighted below 8 kHz and below 2 kHz, and unweighted (dB re the
	// same calibration, so dBZ is only approximate)
	printf("%s_diag clk=%s", tag, mic_3mhz ? "3.0MHz" : "1.5MHz");
	print_q8("dBA", r.dba);
	static const char *const names[] = { "dBA_lt8k", "dBA_lt2k", "dBZ" };
	for (int w = 0; w < 3; w++) {
		int32_t q = dsp_diag_dbfs_q8((dsp_t *)&dsp, w);
		print_q8(names[w], q == INT32_MIN ? q : q + CAL_DB_Q8);
	}
	printf("\n");
#endif
	return r;
}

#ifdef DBFOB_DIAG
// Raw dump for tools/floor_spectrum.py: RAW_FRAMES frames of RAW_N samples (DC removed, before
// weighting) at one clock, printed as 4-digit hex. The capture keeps running while printing.
#define RAW_N      512
#define RAW_FRAMES 8
static int16_t raw[RAW_N];
static void raw_dump(int fast)
{
	mic_3mhz = fast;
	dsp_reset((dsp_t *)&dsp, SETTLE_MS * FS_OUT_HZ_X2 / 2000);
	dsp.r128 = fast;
	capturing = 1;
	mic_start();
	for (int f = 0; f < RAW_FRAMES; f++) {
		dsp.raw_n = 0; dsp.raw_max = RAW_N; dsp.raw = raw;
		while (dsp.raw_n < RAW_N);
		dsp.raw = 0;
		for (int i = 0; i < RAW_N; i += 32) {
			char line[32 * 4 + 1], *p = line;
			for (int k = 0; k < 32; k++)
				for (int sh = 12; sh >= 0; sh -= 4) *p++ = "0123456789abcdef"[((uint16_t)raw[i + k] >> sh) & 15];
			*p = 0;
			printf("raw clk=%s fsb=18 f=%d i=%d %s\n", fast ? "3.0" : "1.5", f, i, line);
		}
	}
	mic_stop();
	mic_3mhz = 0;
}
#endif

// Two verdicts at once: steady = bare ear, blinking = with plugs (only if different)
static void show_two(int bare, int plugs, uint32_t duty)
{
	for (uint32_t ms = 0; ms < SHOW_MS; ms += BLINK_MS) {
		leds_two(bare, plugs == bare ? LED_NONE : plugs, (ms / BLINK_MS) & 1, duty);
		Delay_Ms(BLINK_MS);
	}
	led_set(LED_NONE, 0);
}

static void spot_check(void)
{
	uint32_t light = light_us();
	uint32_t duty = duty_for_light(light);
#ifdef DBFOB_DIAG
	mic_3mhz = 1;                                             // first at 3 MHz, LEDs off ...
	measure("dbfob3", MEASURE_MS, 0, light);
	mic_3mhz = 0;                                             // ... then the normal 1.5 MHz one
#endif
	reading_t r = measure("dbfob", MEASURE_MS, duty, light);
	Delay_Ms(BAR_GAP_MS);                                     // dark gap: the verdict reads as separate
	if (r.invalid) { show_invalid(duty); return; }
#ifdef DBFOB_DIAG
	raw_dump(0);                                              // spectra: tools/floor_spectrum.py
	raw_dump(1);
#endif
	show_two(r.overload ? LED_R : band(r.dba), r.overload ? LED_R : band(r.dba - PLUG_DB * 256), duty);
}

// ---- dosimeter -------------------------------------------------------------------------------
// Long press starts it: the fob then wakes on the auto-wakeup timer (AWU, from the LSI) every
// ~30 s and samples DOSE_SAMPLE_MS every DOSE_TICKS_PER_SAMPLE ticks, with the LEDs off. Each
// sample stands for the time since the last one. A single click shows the dose so far, a long
// press stops it, and it stops by itself after DOSE_MAX_S. The dose is the NIOSH one: 85 dBA for
// 8 h = 100 %, 3 dB exchange, so dose = (T / 8 h) * 10^((LAeq - 85) / 10), within 0.05 dB of 2^(x/3).
enum { DOSE_OFF, DOSE_ON, DOSE_DONE };
static struct {
	uint8_t state;
	uint32_t tick_ms;                                         // AWU period, measured at start
	uint32_t ticks, samples, valid;
	uint64_t sum_ms;                                          // sum of the valid samples' mean squares
} dose;

static void awu_start(uint32_t psc, uint32_t window)
{
	RCC->APB1PCENR |= RCC_APB1Periph_PWR;
	RCC->RSTSCKR |= RCC_LSION;
	while (!(RCC->RSTSCKR & RCC_LSIRDY));
	EXTI->EVENR |= EXTI_Line9;                                // AWU wakes as an event, like the button
	EXTI->FTENR |= EXTI_Line9;
	PWR->AWUCSR = 0;
	PWR->AWUPSC = psc;
	PWR->AWUWR = window;
	PWR->AWUCSR = PWR_AWUCSR_AWUEN;
}

static void awu_stop(void)
{
	PWR->AWUCSR = 0;
	EXTI->EVENR &= ~EXTI_Line9;
	RCC->RSTSCKR &= ~RCC_LSION;                               // no LSI current when not dosing
}

// The LSI is only loosely trimmed, so time one short AWU period against the 48 MHz clock (in
// sleep, where SysTick keeps running) and scale it to the dosimeter's period.
static uint32_t awu_tick_ms(void)
{
	awu_start(PWR_AWUPSC_1024, DOSE_AWU_WINDOW);              // ~0.5 s
	PFIC->SCTLR &= ~(1 << 2);                                 // plain sleep, not standby
	__WFE(); __WFE();                                         // drop a stale event, then align
	uint32_t t0 = SysTick->CNT;
	__WFE();
	uint32_t cycles = SysTick->CNT - t0;
	awu_start(PWR_AWUPSC_61440, DOSE_AWU_WINDOW);
	return (uint32_t)((uint64_t)cycles * (61440 / 1024) / (FUNCONF_SYSTEM_CORE_CLOCK / 1000));
}

static uint32_t dose_elapsed_s(void) { return (uint32_t)((uint64_t)dose.ticks * dose.tick_ms / 1000); }

// Dose in dB relative to 100 %, Q8; INT32_MIN if there is nothing to show
static int32_t dose_db_q8(void)
{
	if (!dose.valid) return INT32_MIN;
	int32_t laeq = dsp_ms_dbfs_q8(dose.sum_ms / dose.valid) + CAL_DB_Q8;
	uint32_t t = dose_elapsed_s();
	return laeq - 85 * 256 + dsp_db10_q8(t ? t : 1) - dsp_db10_q8(8 * 3600);
}

static void dose_print(const char *what)
{
	int32_t db = dose_db_q8();
	printf("dose %s elapsed_s=%lu samples=%lu valid=%lu tick_ms=%lu", what, (unsigned long)dose_elapsed_s(),
	       (unsigned long)dose.samples, (unsigned long)dose.valid, (unsigned long)dose.tick_ms);
	print_q8("LAeq", dose.valid ? dsp_ms_dbfs_q8(dose.sum_ms / dose.valid) + CAL_DB_Q8 : INT32_MIN);
	print_q8("dose_dB", db);
	printf("\n");
}

// ---- dose log in flash ----------------------------------------------------------------------
// The last run is kept in the last 1 KB of flash, so it survives taking the cell out and can be
// read later with the programmer (`make dose-log`, tools/dose_log.py). Layout, little endian:
//   0x00 u16 DOSE_LOG_MAGIC   0x02 u16 CAL_DB_Q8   0x04 u32 tick_ms
//   0x08 u16 ticks per sample 0x0A u16 sample ms   0x0C... one byte per sample:
//   1-250 = dBA (code / 2 + 20, 0.5 dB steps), 0 = invalid, 0xFD = stopped, 0xFE = auto-off,
//   0xFF = not written. The 1 KB is erased once per run and written a half-word (two samples) at a
//   time, so a run costs one erase of each 64-byte page.
#define DOSE_LOG_ADDR     0x08003C00     // the firmware must stay below this: `make check` tests it
#define DOSE_LOG_SIZE     1024
#define DOSE_LOG_MAGIC    0xDB01
#define DOSE_LOG_HDR      12
#define LOG_STOPPED       0xFD
#define LOG_AUTO_OFF      0xFE

static struct { uint16_t pos; int16_t pending; } dlog;      // pending: low byte waiting for a pair, or -1

static void flash_unlock(void)
{
	FLASH->KEYR = FLASH_KEY1; FLASH->KEYR = FLASH_KEY2;
	FLASH->MODEKEYR = FLASH_KEY1; FLASH->MODEKEYR = FLASH_KEY2;   // fast page erase
}

static void flash_write16(uint32_t addr, uint16_t v)
{
	if (addr < DOSE_LOG_ADDR || addr >= DOSE_LOG_ADDR + DOSE_LOG_SIZE) return;   // never the firmware
	flash_unlock();
	FLASH->CTLR = CR_PG_Set;
	*(volatile uint16_t *)addr = v;
	while (FLASH->STATR & FLASH_STATR_BSY);
	FLASH->CTLR = CR_LOCK_Set;
}

static void dose_log_start(void)
{
	flash_unlock();
	for (uint32_t a = DOSE_LOG_ADDR; a < DOSE_LOG_ADDR + DOSE_LOG_SIZE; a += 64) {   // 64-byte pages
		FLASH->CTLR = CR_PAGE_ER;
		FLASH->ADDR = a;
		FLASH->CTLR = CR_STRT_Set | CR_PAGE_ER;
		while (FLASH->STATR & FLASH_STATR_BSY);
	}
	FLASH->CTLR = CR_LOCK_Set;
	flash_write16(DOSE_LOG_ADDR + 0, DOSE_LOG_MAGIC);
	flash_write16(DOSE_LOG_ADDR + 2, (uint16_t)CAL_DB_Q8);
	flash_write16(DOSE_LOG_ADDR + 4, (uint16_t)dose.tick_ms);
	flash_write16(DOSE_LOG_ADDR + 6, (uint16_t)(dose.tick_ms >> 16));
	flash_write16(DOSE_LOG_ADDR + 8, DOSE_TICKS_PER_SAMPLE);
	flash_write16(DOSE_LOG_ADDR + 10, DOSE_SAMPLE_MS);
	dlog.pos = DOSE_LOG_HDR; dlog.pending = -1;
}

static void dose_log_byte(uint8_t b)
{
	if (dlog.pos >= DOSE_LOG_SIZE) return;                    // full: ~17 h at one sample a minute
	if (dlog.pending < 0) { dlog.pending = b; return; }
	flash_write16(DOSE_LOG_ADDR + dlog.pos, (uint16_t)(dlog.pending | (b << 8)));
	dlog.pos += 2; dlog.pending = -1;
}

static void dose_log_end(uint8_t marker)
{
	dose_log_byte(marker);
	if (dlog.pending >= 0) dose_log_byte(0xFF);               // flush: 0xFF stays "not written"
}

static uint8_t dose_log_code(const reading_t *r)
{
	if (r->invalid || r->dba == INT32_MIN) return 0;
	int32_t c = (r->dba - 20 * 256 + 64) >> 7;                // (dBA - 20) * 2, rounded
	return c < 1 ? 1 : c > 250 ? 250 : (uint8_t)c;
}

static void dose_sample(void)
{
	reading_t r = measure("dose_sample", DOSE_SAMPLE_MS, 0, 0);
	dose_log_byte(dose_log_code(&r));
	dose.samples++;
	if (!r.invalid) { dose.sum_ms += r.ms; dose.valid++; }
}

static int pressed(void);
static void dose_start(void)
{
	leds_bar(4, DUTY_MIN * 4);                                // acknowledge: all on while the LSI is timed
	dose = (typeof(dose)){ .state = DOSE_ON };
	dose.tick_ms = awu_tick_ms();
	dose_log_start();
	for (int i = 0; i < 2; i++) { leds_bar(0, 0); Delay_Ms(150); leds_bar(4, DUTY_MIN * 4); Delay_Ms(150); }
	leds_bar(0, 0);
	dose_print("start");
	// The long press is reported with the button still held: let go of it first, or the release
	// click lands in the first sample, right at the mic (one read 101.5 dBA = 10 % of a dose)
	while (pressed()) Delay_Ms(10);
	Delay_Ms(RELEASE_QUIET_MS);
	dose_sample();                                            // the first sample stands for the first period
}

static void dose_stop(int state)
{
	awu_stop();
	dose_log_end(state == DOSE_DONE ? LOG_AUTO_OFF : LOG_STOPPED);
	dose.state = state;
	dose_print(state == DOSE_DONE ? "auto_off" : "stop");
}

// Dose as a fraction of the allowance, in permille (capped at 1000), from dose_db_q8
static uint32_t dose_permille(int32_t db_q8)
{
	if (db_q8 >= 0) return 1000;
	uint32_t n = -db_q8, f = 1000 << 16;                      // permille, Q16
	for (; n >= 10 * 256; n -= 10 * 256) f /= 10;             // whole 10 dB steps
	for (; n >= 256; n -= 256) f = (uint64_t)f * 52057 >> 16; // whole 1 dB steps: x 10^-0.1
	f -= (uint64_t)f * (n * 13481 >> 8) >> 16;                // the rest, linearly: < 1 % off
	return f >> 16;
}

static void dose_show(void)
{
	uint32_t duty = duty_for_light(light_us());
	int32_t db = dose_db_q8();
	dose_print("show");
	if (db == INT32_MIN || dose.valid * 2 < dose.samples) { show_invalid(duty); return; }
	// Blink period linear in the dose: 1 s at 0 %, 0.5 s at 50 %, 0.1 s at 90 %, lit at 100 %
	uint32_t period = DOSE_BLINK_SLOW_MS - DOSE_BLINK_SLOW_MS * dose_permille(db) / 1000;
	if (!period) { leds_bar(4, duty); Delay_Ms(DOSE_SHOW_MS); leds_bar(0, 0); return; }
	for (uint32_t ms = 0; ms < DOSE_SHOW_MS; ms += period) {
		leds_bar(4, duty); Delay_Ms(period / 2);
		leds_bar(0, 0); Delay_Ms(period - period / 2);
	}
}

// Woken by the AWU with the button up
static void dose_tick(void)
{
	dose.ticks++;
	if (dose.ticks % DOSE_TICKS_PER_SAMPLE == 0) dose_sample();
	if (dose_elapsed_s() >= DOSE_MAX_S) dose_stop(DOSE_DONE);  // kept: a click still shows it
}

// ---- button ----------------------------------------------------------------------------------
enum { EV_NONE, EV_SINGLE, EV_DOUBLE, EV_TRIPLE, EV_LONG };
static int pressed(void) { return !funDigitalRead(PC0); }

// Called with the button down. A long press is reported as soon as it is long enough, while
// still held, so the LEDs can acknowledge it under the finger. Clicks are counted up to three; a
// double click is reported only once no third one follows, so its measurement starts with the
// button already released.
static int button_event(void)
{
	for (int clicks = 1;; clicks++) {
		uint32_t ms = 0;
		for (; pressed(); ms += 5) {
			if (ms >= LONG_PRESS_MS) return clicks == 1 ? EV_LONG : EV_NONE;
			Delay_Ms(5);
		}
		if (ms > CLICK_MAX_MS) return EV_NONE;                // neither a click nor a long press
		if (clicks == 3) return EV_TRIPLE;
		Delay_Ms(DEBOUNCE_MS);
		for (ms = 0; ms < CLICK_GAP_MS && !pressed(); ms += 5) Delay_Ms(5);   // another click?
		if (pressed()) Delay_Ms(DEBOUNCE_MS);
		if (!pressed()) return clicks == 1 ? EV_SINGLE : EV_DOUBLE;
	}
}

// ---- power -----------------------------------------------------------------------------------
static void pins_init(void)
{
	RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC | RCC_APB2Periph_GPIOD | RCC_AFIOEN;
	// unused pins: pulled down, no floating inputs in standby
	funPinMode(PA1, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PA1, FUN_LOW);
	funPinMode(PA2, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PA2, FUN_LOW);
	funPinMode(PC1, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PC1, FUN_LOW);
	funPinMode(PD0, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PD0, FUN_LOW);
	funPinMode(PD4, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PD4, FUN_LOW);
	funPinMode(PD6, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PD6, FUN_LOW);
	// mic: unpowered, clock low, data pulled down (never drive a powered-down part's pins high)
	funPinMode(PC6, GPIO_CFGLR_OUT_2Mhz_PP); funDigitalWrite(PC6, FUN_LOW);
	funPinMode(PC5, GPIO_CFGLR_OUT_2Mhz_PP); funDigitalWrite(PC5, FUN_LOW);
	funPinMode(PC7, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PC7, FUN_LOW);
	// button: pull-up, EXTI line 0 on port C, falling edge as a wake event
	funPinMode(PC0, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PC0, FUN_HIGH);
	AFIO->EXTICR = (AFIO->EXTICR & ~(3u << 0)) | (2u << 0);   // line 0 <- port C
	EXTI->EVENR |= EXTI_Line0;
	EXTI->FTENR |= EXTI_Line0;
	leds_pins();
}

static void standby(void)
{
	RCC->APB1PCENR |= RCC_APB1Periph_PWR;
	PWR->CTLR |= PWR_CTLR_PDDS;
	PFIC->SCTLR |= 1 << 2;                                    // SLEEPDEEP
	// The ADC keeps its analog block powered through standby: ~0.57 mA measured on board 1.
	ADC1->CTLR2 &= ~ADC_ADON;
	__WFE();
	SystemInit();                                             // back to 48 MHz after wake
	adc_init();                                               // power up and recalibrate (~20 us)
}

int main(void)
{
	SystemInit();
	pins_init();
	adc_init();
	leds_init();
	printf("\ndbfob rev A fw " __DATE__ " vdd=%lu\n", (unsigned long)vdd_mv());
	// Stay awake 3 s after reset so a programmer can attach before the first standby.
	for (int i = 0; i < 4; i++) { led_set(i, DUTY_MIN * 4); Delay_Ms(750); }
	led_set(LED_NONE, 0);
	for (;;) {
		standby();
		// A press reads low within 1 ms of its wake edge. Checking that early keeps the dosimeter's
		// timer-only wakes short: at 6.7 mA, a 20 ms wake every 30 s was ~4 uA of average current.
		Delay_Ms(1);
		if (!pressed()) {                                     // the AWU
			if (dose.state == DOSE_ON) dose_tick();
			continue;
		}
		Delay_Ms(DEBOUNCE_MS);
		if (!pressed()) continue;                             // a bounce
		switch (button_event()) {
		case EV_DOUBLE: spot_check(); break;
		case EV_TRIPLE: if (dose.state != DOSE_OFF) dose_show(); break;
		case EV_LONG:
			if (dose.state == DOSE_ON) {
				// stop: the bar empties R -> G
				for (int n = 4; n >= 0; n--) { leds_bar(n, DUTY_MIN * 4); Delay_Ms(250); }
				dose_stop(DOSE_OFF);
			} else dose_start();
			break;
		}
		while (pressed()) Delay_Ms(10);                       // wait for release
	}
}
