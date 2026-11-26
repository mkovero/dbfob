// B1 bring-up test: proves the MCU, the debug link, the LEDs, the button, the cell sense, the NFC
// tag's I2C side and the mic's data line. It never sleeps, so the programmer can always reattach.
// Not the meter firmware.
//
// - LED sweep green -> yellow -> red -> red, one step per 200 ms; all four lit while the button is held.
// - Once a second: a line with the button, VDD and the cell voltage (PA7 through R11).
// - At start and at every button press: reads the tag's first three blocks over I2C, and clocks the
//   mic for a moment and reports how many of its bits were ones.
// - At start it also formats a blank tag: NDEF capability bytes and a URL (see nfc_format).
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

// No ADC_CAL: on the bench (2026-11-26) the calibration sequence known from the other CH32 parts
// left every reading 2048 counts too high, or at zero. Without it the readings are right to a few
// counts, and channel 18 (the internal calibration channel, half scale) shows the offset, which
// is taken off here.
static void adc_init( void )
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

static void nfc_power( int on )
{
	if( on )
	{
		funDigitalWrite( SCL, 1 );
		funDigitalWrite( SDA, 1 );
		funPinMode( SCL, GPIO_CFGLR_OUT_10Mhz_OD );
		funPinMode( SDA, GPIO_CFGLR_OUT_10Mhz_OD );
		funPinMode( NFC_VCC, GPIO_CFGLR_OUT_10Mhz_PP );
		funDigitalWrite( NFC_VCC, 1 );
		Delay_Ms( 10 );
	}
	else
	{
		// lines to analog before the tag's supply drops (README: firmware notes)
		funPinMode( SCL, GPIO_CFGLR_IN_ANALOG );
		funPinMode( SDA, GPIO_CFGLR_IN_ANALOG );
		funDigitalWrite( NFC_VCC, 0 );
	}
}

static int nfc_read_block( int n, uint8_t * blk )   // returns the three ACKs as 0..7 (7 = all)
{
	i2c_start();
	int a = i2c_write( TAG_ADDR << 1 );
	a = a << 1 | i2c_write( n );
	i2c_stop();
	i2c_start();
	a = a << 1 | i2c_write( TAG_ADDR << 1 | 1 );
	for( int i = 0; i < 16; i++ ) blk[i] = i2c_read( i < 15 );
	i2c_stop();
	return a;
}

static int nfc_write_block( int n, const uint8_t * blk )   // returns 1 if every byte was ACKed
{
	i2c_start();
	int ok = i2c_write( TAG_ADDR << 1 ) & i2c_write( n );
	for( int i = 0; i < 16; i++ ) ok &= i2c_write( blk[i] );
	i2c_stop();
	Delay_Ms( 10 );                            // EEPROM write time (4 ms in the datasheet)
	return ok;
}

static void print_block( const char * name, int ack, const uint8_t * blk )
{
	printf( "%s ack=%d:", name, ack );
	for( int i = 0; i < 16; i++ ) printf( " %02x", blk[i] );
	printf( "\n" );
}

// NDEF message for blocks 1 and 2 (the tag's user memory starts at block 1):
// TLV 03, length 29; one URI record (D1 01 19 55), prefix 04 = "https://", then the address; FE ends it.
static const uint8_t ndef[32] = {
	0x03, 0x1d, 0xd1, 0x01, 0x19, 0x55, 0x04,
	'g','i','t','h','u','b','.','c','o','m','/','m','k','o','v','e','r','o','/','d','b','f','o','b',
	0xfe };

// Formats a blank tag: capability container E1 10 6D 00 (NTAG I2C plus 1k) and the URL above.
// Writes only what differs, so it does nothing on a tag that is already set up.
static void nfc_format( void )
{
	uint8_t blk[16];
	if( nfc_read_block( 0, blk ) != 7 ) { printf( "nfc format: no tag\n" ); return; }
	if( blk[12] != 0xe1 || blk[13] != 0x10 || blk[14] != 0x6d || blk[15] != 0x00 )
	{
		// Block 0 over I2C: byte 0 is the tag's I2C address (it always reads back as 04), so it
		// must be written as 0xAA, or the tag moves to another address. Bytes 1-9 are the serial
		// number and internal bytes (read-only), 10-11 the static lock bits (left at 0).
		if( blk[10] || blk[11] ) { printf( "nfc format: lock bits set, not touching block 0\n" ); return; }
		blk[0] = TAG_ADDR << 1;
		blk[12] = 0xe1; blk[13] = 0x10; blk[14] = 0x6d; blk[15] = 0x00;
		printf( "nfc format: block 0 written, ok=%d\n", nfc_write_block( 0, blk ) );
	}
	for( int n = 1; n <= 2; n++ )
	{
		const uint8_t * want = ndef + ( n - 1 ) * 16;
		int same = nfc_read_block( n, blk ) == 7;
		for( int i = 0; i < 16; i++ ) same &= blk[i] == want[i];
		if( !same ) printf( "nfc format: block %d written, ok=%d\n", n, nfc_write_block( n, want ) );
	}
}

static void nfc_test( int format )
{
	uint8_t blk[16];
	nfc_power( 1 );
	int idle = funDigitalRead( SCL ) | funDigitalRead( SDA ) << 1;   // both should be high: 3
	printf( "nfc idle=%d\n", idle );
	if( format ) nfc_format();
	for( int n = 0; n <= 2; n++ )
	{
		int a = nfc_read_block( n, blk );
		print_block( n == 0 ? "nfc block0" : n == 1 ? "nfc block1" : "nfc block2", a, blk );
	}
	nfc_power( 0 );
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
	adc_init();

	unsigned step = 0;
	int was_pressed = 1;                       // run the tests once at start
	while( 1 )
	{
		int pressed = funDigitalRead( BTN );
		for( int i = 0; i < 4; i++ )
			funDigitalWrite( leds[i], ( pressed || i == (int)( step & 3 ) ) ? FUN_HIGH : FUN_LOW );
		if( step == 0 || ( pressed && !was_pressed ) )
		{
			nfc_test( step == 0 );             // formats a blank tag once, at start
			mic_test();
		}
		was_pressed = step ? pressed : 0;
		if( step % 5 == 0 )
		{
			// sums of 16 conversions; the offset is what channel 18 reads above half scale
			int32_t off = (int32_t)adc_read( 18 ) - 2048 * 16;
			int32_t ref = (int32_t)adc_read( 17 ) - off, cell = (int32_t)adc_read( 7 ) - off;
			if( ref < 1 ) ref = 1;
			if( cell < 0 ) cell = 0;
			printf( "b1test %u btn=%d vdd=%lu mV cell=%lu mV (adc offset %ld)\n", step / 5, pressed,
				(unsigned long)( VREFINT_MV * 4095u * 16u / (uint32_t)ref ),
				(unsigned long)( (uint32_t)cell * VREFINT_MV / (uint32_t)ref ), (long)( off / 16 ) );
		}
		step++;
		Delay_Ms( 200 );
	}
}
