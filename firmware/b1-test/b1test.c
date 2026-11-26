// B1 bring-up test: proves the MCU, the debug link, the four LEDs and the button.
// It never sleeps, so the programmer can always reattach.
//
// LED sweep green -> yellow -> red -> red, one step per 200 ms. While the button is held, all
// four are lit. Once a second it prints a count and the button state over the debug wires.
//
// Pins (hardware/b1/README.md): PA3 green D1, PA2 yellow D2, PA1 red D3, PA8 red D4 with its
// cathode on PA10 (held low here), PA0 button to VDD (input with pull-down; never an output).

#include "ch32fun.h"
#include <stdio.h>

#define LED_G  PA3
#define LED_Y  PA2
#define LED_O  PA1
#define LED_R  PA8
#define LED_RK PA10
#define BTN    PA0

static const uint8_t leds[4] = { LED_G, LED_Y, LED_O, LED_R };

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

	unsigned step = 0;
	while( 1 )
	{
		int pressed = funDigitalRead( BTN );
		for( int i = 0; i < 4; i++ )
			funDigitalWrite( leds[i], ( pressed || i == (int)( step & 3 ) ) ? FUN_HIGH : FUN_LOW );
		if( step % 5 == 0 )
			printf( "b1test %u btn=%d\n", step / 5, pressed );
		step++;
		Delay_Ms( 200 );
	}
}
