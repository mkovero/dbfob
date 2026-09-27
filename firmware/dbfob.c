// dbfob firmware, rev A board (CH32V003F4P6 + IM69D130).
//
// Press the button: the fob wakes from standby, powers the mic, captures 3 s of PDM over SPI1+DMA,
// A-weights it (src/dsp.c), and shows two verdicts on the LED bar for ~2 s: steady LED = bare ear,
// blinking LED = with plugs giving 12 dB. Then back to standby. Every reading is also printed on
// USART1 TX (PD5, J1 "T") for calibration against a reference meter.
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
#define SHOW_MS           2000
#define BLINK_MS          250
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
	SPI1->CTLR1 = SPI_NSS_Soft | SPI_CPHA_1Edge | SPI_CPOL_Low | SPI_DataSize_8b | SPI_FirstBit_MSB |
	              SPI_Mode_Master | SPI_Direction_2Lines_RxOnly | SPI_BaudRatePrescaler_32;
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
	int32_t a = q8 < 0 ? -q8 : q8;
	printf(" %s=%s%ld.%01ld", name, q8 < 0 ? "-" : "", (long)(a >> 8), (long)(((a & 255) * 10) >> 8));
}

static void measure_and_show(void)
{
	uint32_t light = light_us();
	uint32_t duty = duty_for_light(light);
	uint32_t v_idle = vdd_mv(), v_min = v_idle;

	dsp_reset((dsp_t *)&dsp, SETTLE_MS * FS_OUT_HZ_X2 / 2000);
	isr_cycles = 0; overruns = 0;
	capturing = 1;
	uint32_t t0 = SysTick->CNT;
	mic_start();
	for (uint32_t ms = 0; ms < SETTLE_MS + MEASURE_MS; ms += 50) {
		Delay_Ms(50);
		uint32_t v = vdd_mv();                                 // VDD under load, throughout
		if (v < v_min) v_min = v;
	}
	mic_stop();
	uint32_t total = SysTick->CNT - t0;

	int32_t dbfs = dsp_level_dbfs_q8((dsp_t *)&dsp);
	int32_t dba = dbfs + CAL_DB_Q8;
	int overload = dsp.pcm_peak >= OVERLOAD_PCM;
	int invalid = v_min < VBAT_MIN_MV || !dsp.n || overruns;

	printf("dbfob");
	print_q8("dBA", dba); print_q8("dBFS", dbfs);
	printf(" n=%lu peak=%ld pcm_peak=%ld overload=%d vdd_idle=%lu vdd_min=%lu light_us=%lu duty=%lu"
	       " cpu=%lu%% overruns=%lu%s\n",
	       (unsigned long)dsp.n, (long)dsp.peak, (long)dsp.pcm_peak, overload, (unsigned long)v_idle,
	       (unsigned long)v_min, (unsigned long)light, (unsigned long)duty,
	       (unsigned long)(total ? (uint64_t)isr_cycles * 100 / total : 0), (unsigned long)overruns,
	       invalid ? " INVALID" : "");

	if (invalid) { show_invalid(duty); return; }
	int bare = overload ? LED_R : band(dba);
	int plugs = overload ? LED_R : band(dba - PLUG_DB * 256);
	for (uint32_t ms = 0; ms < SHOW_MS; ms += BLINK_MS) {
		leds_two(bare, plugs == bare ? LED_NONE : plugs, (ms / BLINK_MS) & 1, duty);
		Delay_Ms(BLINK_MS);
	}
	led_set(LED_NONE, 0);
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
	__WFE();
	SystemInit();                                             // back to 48 MHz after wake
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
		Delay_Ms(20);                                         // debounce
		if (funDigitalRead(PC0)) continue;                    // not a press
		measure_and_show();
		while (!funDigitalRead(PC0)) Delay_Ms(10);            // wait for release
	}
}
