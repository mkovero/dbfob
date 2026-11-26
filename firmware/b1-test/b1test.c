// B1 bring-up test: proves the MCU, the debug link, the LEDs, the button, the cell sense, the NFC
// tag's I2C side and the mic's data line. It never sleeps, so the programmer can always reattach.
// Not the meter firmware.
//
// - LED sweep green -> yellow -> red -> red, one step per 200 ms; all four lit while the button is held.
// - Once a second: a line with the button, VDD and the cell voltage (PA7 through R11).
// - At start and at every button press: reads the tag's first block over I2C, and clocks the mic
//   for a moment and reports how many of its bits were ones.
//
// Pins (hardware/b1/README.md): PA3 green D1, PA2 yellow D2, PA1 red D3, PA8 red D4 with its
// cathode on PA10 (held low here), PA0 button to VDD (input with pull-down; never an output),
// PA7 cell sense, PB14 tag supply, PB10 SCL, PB11 SDA, PA4 mic supply, PA5 mic clock, PA6 mic data.

#include "ch32fun.h"
#include <stdio.h>

#define LED_G   PA3
#define LED_Y   PA2
#define LED_O   PA1
#define LED_R   PA8
#define LED_RK  PA10
#define BTN     PA0
#define VSENSE  PA7
#define NFC_VCC PB14
#define SCL     PB10
#define SDA     PB11
#define MIC_PWR PA4
#define MIC_CLK PA5
#define MIC_DAT PA6

#define VREFINT_MV 1200   // CH32L103 datasheet, typical
#define TAG_ADDR   0x55   // NT3H2111 factory I2C address

static const uint8_t leds[4] = { LED_G, LED_Y, LED_O, LED_R };

// ---- ADC: one conversion of a channel, longest sample time (PA7 has 4.7 kOhm in series) ----

static uint32_t adc_calval;

static void adc_init( int calibrate )
{
	RCC->APB2PCENR |= RCC_APB2Periph_ADC1;
	RCC->APB2PRSTR |= RCC_APB2Periph_ADC1;
	RCC->APB2PRSTR &= ~RCC_APB2Periph_ADC1;
	funPinMode( VSENSE, GPIO_CFGLR_IN_ANALOG );
	ADC1->SAMPTR1 = 0x00ffffff;                // 239.5 cycles on every channel
	ADC1->SAMPTR2 = 0x3fffffff;
	ADC1->RSQR1 = 0;                           // one conversion
	ADC1->CTLR2 = ADC_ADON | ADC_EXTSEL | ADC_EXTTRIG | ADC_TSVREFE;   // software start, Vrefint on
	Delay_Ms( 2 );
	if( !calibrate ) return;
	ADC1->CTLR2 |= ADC_RSTCAL;
	while( ADC1->CTLR2 & ADC_RSTCAL ) { }
	ADC1->CTLR2 |= ADC_CAL;
	while( ADC1->CTLR2 & ADC_CAL ) { }
	adc_calval = ADC1->RDATAR;
}

static uint32_t adc_read( int channel )      // sum of 16 conversions
{
	uint32_t sum = 0;
	ADC1->RSQR3 = channel;
	for( int i = 0; i < 17; i++ )
	{
		ADC1->CTLR2 |= ADC_SWSTART;
		while( !( ADC1->STATR & ADC_EOC ) ) { }
		uint32_t v = ADC1->RDATAR & 0xfff;
		if( i ) sum += v;                      // the first one after a channel change is dropped
	}
	return sum;
}

// ---- I2C by hand on PB10 / PB11 (open drain, the board's pull-ups go to NFC_VCC) ----

static void i2c_delay( void ) { Delay_Us( 10 ); }
static void scl( int v ) { funDigitalWrite( SCL, v ); i2c_delay(); }
static void sda( int v ) { funDigitalWrite( SDA, v ); i2c_delay(); }

static void i2c_start( void ) { sda( 1 ); scl( 1 ); sda( 0 ); scl( 0 ); }
static void i2c_stop( void )  { sda( 0 ); scl( 1 ); sda( 1 ); }

static int i2c_write( uint8_t b )            // returns 1 on ACK
{
	for( int i = 0; i < 8; i++, b <<= 1 ) { sda( b >> 7 & 1 ); scl( 1 ); scl( 0 ); }
	sda( 1 );
	scl( 1 );
	int ack = !funDigitalRead( SDA );
	scl( 0 );
	return ack;
}

static uint8_t i2c_read( int ack )
{
	uint8_t b = 0;
	sda( 1 );
	for( int i = 0; i < 8; i++ ) { scl( 1 ); b = b << 1 | funDigitalRead( SDA ); scl( 0 ); }
	sda( !ack ); scl( 1 ); scl( 0 ); sda( 1 );
	return b;
}

static void nfc_test( void )
{
	uint8_t blk[16];
	funDigitalWrite( SCL, 1 );
	funDigitalWrite( SDA, 1 );
	funPinMode( SCL, GPIO_CFGLR_OUT_10Mhz_OD );
	funPinMode( SDA, GPIO_CFGLR_OUT_10Mhz_OD );
	funPinMode( NFC_VCC, GPIO_CFGLR_OUT_10Mhz_PP );
	funDigitalWrite( NFC_VCC, 1 );
	Delay_Ms( 10 );
	int idle = funDigitalRead( SCL ) | funDigitalRead( SDA ) << 1;   // both should be high: 3

	i2c_start();
	int a1 = i2c_write( TAG_ADDR << 1 );
	int a2 = i2c_write( 0 );                   // block 0
	i2c_stop();
	i2c_start();
	int a3 = i2c_write( TAG_ADDR << 1 | 1 );
	for( int i = 0; i < 16; i++ ) blk[i] = i2c_read( i < 15 );
	i2c_stop();

	// lines to analog before the tag's supply drops (README: firmware notes)
	funPinMode( SCL, GPIO_CFGLR_IN_ANALOG );
	funPinMode( SDA, GPIO_CFGLR_IN_ANALOG );
	funDigitalWrite( NFC_VCC, 0 );

	printf( "nfc idle=%d ack=%d%d%d block0:", idle, a1, a2, a3 );
	for( int i = 0; i < 16; i++ ) printf( " %02x", blk[i] );
	printf( "\n" );
}

// ---- mic: 2 MHz clock from SPI1, count the ones in its bit stream ----

static void mic_run( int cpha )
{
	SPI1->CTLR1 = 0;
	SPI1->CTLR1 = SPI_CTLR1_MSTR | SPI_CTLR1_SSM | SPI_CTLR1_SSI | ( 2 << 3 ) | ( cpha ? 1 : 0 );   // PCLK2 / 8
	SPI1->CTLR1 |= SPI_CTLR1_SPE;
	uint32_t ones = 0, lo = 9999, hi = 0, win = 0;
	for( int i = 0; i < 12288 + 4096; i++ )   // 49 ms to settle, then 16 ms counted
	{
		SPI1->DATAR = 0;
		while( !( SPI1->STATR & SPI_STATR_RXNE ) ) { }
		uint8_t b = SPI1->DATAR;
		if( i < 12288 ) continue;
		int n = __builtin_popcount( b );
		ones += n;
		win += n;
		if( ( i & 63 ) == 63 ) { if( win < lo ) lo = win; if( win > hi ) hi = win; win = 0; }
	}
	SPI1->CTLR1 = 0;
	printf( "mic edge=%d ones=%lu/32768 (%lu pct), per 512 bits min %lu max %lu\n",
		cpha, (unsigned long)ones, (unsigned long)( ones * 100 / 32768 ), (unsigned long)lo, (unsigned long)hi );
}

static void mic_test( void )
{
	RCC->APB2PCENR |= RCC_APB2Periph_SPI1;
	funPinMode( MIC_PWR, GPIO_CFGLR_OUT_10Mhz_PP );
	funDigitalWrite( MIC_PWR, 1 );
	Delay_Ms( 20 );
	funPinMode( MIC_DAT, GPIO_CFGLR_IN_FLOAT );
	funPinMode( MIC_CLK, GPIO_CFGLR_OUT_50Mhz_AF_PP );
	mic_run( 0 );
	mic_run( 1 );
	// clock and data to analog before the mic's supply drops (README: firmware notes)
	funPinMode( MIC_CLK, GPIO_CFGLR_IN_ANALOG );
	funPinMode( MIC_DAT, GPIO_CFGLR_IN_ANALOG );
	funDigitalWrite( MIC_PWR, 0 );
}

int main()
{
	SystemInit();
	funGpioInitAll();

	funPinMode( BTN, GPIO_CFGLR_IN_PUPD );
	funDigitalWrite( BTN, FUN_LOW );           // pull-down
	funPinMode( LED_RK, GPIO_CFGLR_OUT_10Mhz_PP );
	funDigitalWrite( LED_RK, FUN_LOW );
	for( int i = 0; i < 4; i++ )
	{
		funPinMode( leds[i], GPIO_CFGLR_OUT_10Mhz_PP );
		funDigitalWrite( leds[i], FUN_LOW );
	}
	adc_init( 1 );

	unsigned step = 0;
	int was_pressed = 1;                       // run the tests once at start
	while( 1 )
	{
		int pressed = funDigitalRead( BTN );
		for( int i = 0; i < 4; i++ )
			funDigitalWrite( leds[i], ( pressed || i == (int)( step & 3 ) ) ? FUN_HIGH : FUN_LOW );
		if( step == 0 || ( pressed && !was_pressed ) )
		{
			nfc_test();
			mic_test();
		}
		was_pressed = step ? pressed : 0;
		if( step % 25 == 0 )                    // ADC diagnostics: raw counts (0..4095), without and with calibration
		{
			for( int cal = 0; cal < 2; cal++ )
			{
				adc_init( cal );
				printf( "adc cal=%d calval=%lu raw: pa7=%lu temp=%lu vref=%lu cal18=%lu\n", cal, (unsigned long)adc_calval,
					(unsigned long)adc_read( 7 ) / 16, (unsigned long)adc_read( 16 ) / 16,
					(unsigned long)adc_read( 17 ) / 16, (unsigned long)adc_read( 18 ) / 16 );
			}
		}
		if( step % 5 == 0 )
		{
			uint32_t ref = adc_read( 17 ), cell = adc_read( 7 );
			if( !ref ) ref = 1;
			printf( "b1test %u btn=%d vdd=%lu mV cell=%lu mV\n", step / 5, pressed,
				(unsigned long)( VREFINT_MV * 4095u * 16u / ref ), (unsigned long)( cell * VREFINT_MV / ref ) );
		}
		step++;
		Delay_Ms( 200 );
	}
}
