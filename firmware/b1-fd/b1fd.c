// B1 field-detect test: does a phone's field wake the board out of Standby?
//
// The tag's FD pin (open drain, R3 pulls it up to VDD) goes low while a reader's field is present,
// with the tag's own supply off. It is on PB0, which is not the WKUP pin, so the wake has to come
// from EXTI line 0. Whether that works in Standby is the question; Stop is the fallback.
//
// At start, what woke the board:
//   one yellow flash     power-on or reset
//   two green flashes    Standby wake, WKUP flag set (the button)
//   three red flashes    Standby wake, FD low (a phone is on the coil)
//   three yellow         Standby wake, neither of the above
// Then 8 s awake (the programmer's window): yellow blinks, green is lit while FD is low.
// Then Standby. With the button held down at the end of the 8 s: Stop instead, announced by one
// long red flash; a wake from Stop shows as red and green alternating, then the board resets.
// In Stop the button does not wake (PA0 and PB0 share EXTI line 0): tap a phone or cycle the power.

#include "ch32fun.h"
#include <stdio.h>

#define LED_G  PA3
#define LED_Y  PA2
#define LED_O  PA1
#define BTN    PA0
#define FD     PB0

void EXTI0_IRQHandler( void ) __attribute__((interrupt));
void EXTI0_IRQHandler( void )
{
	EXTI->INTFR = 1;
}

static void flash( int pin, int n, int ms )
{
	for( int i = 0; i < n; i++ )
	{
		funDigitalWrite( pin, 1 ); Delay_Ms( ms );
		funDigitalWrite( pin, 0 ); Delay_Ms( ms );
	}
}

static void leds_on( void )
{
	funPinMode( LED_G, GPIO_CFGLR_OUT_10Mhz_PP );
	funPinMode( LED_Y, GPIO_CFGLR_OUT_10Mhz_PP );
	funPinMode( LED_O, GPIO_CFGLR_OUT_10Mhz_PP );
}

int main()
{
	SystemInit();
	funGpioInitAll();
	RCC->APB1PCENR |= RCC_PWREN;

	uint32_t csr = PWR->CSR;
	PWR->CTLR |= PWR_CTLR_CSBF;

	leds_on();
	funPinMode( BTN, GPIO_CFGLR_IN_PUPD );     // pull-down: OUTDR bit is 0
	funPinMode( FD, GPIO_CFGLR_IN_FLOAT );     // R3 pulls it up
	Delay_Ms( 1 );
	int fd_low = !funDigitalRead( FD );

	printf( "b1fd: PWR_CSR %08lx, FD %s\n", (unsigned long)csr, fd_low ? "low" : "high" );
	if( !( csr & PWR_CSR_SBF ) ) flash( LED_Y, 1, 300 );
	else if( fd_low )            flash( LED_O, 3, 100 );
	else if( csr & PWR_CSR_WUF ) flash( LED_G, 2, 100 );
	else                         flash( LED_Y, 3, 100 );

	for( int i = 0; i < 80; i++ )              // 8 s awake
	{
		funDigitalWrite( LED_G, !funDigitalRead( FD ) );
		funDigitalWrite( LED_Y, ( i % 5 ) == 0 );
		Delay_Ms( 100 );
	}
	funDigitalWrite( LED_G, 0 );
	funDigitalWrite( LED_Y, 0 );
	int stop = funDigitalRead( BTN );
	if( stop ) flash( LED_O, 1, 1000 );

	// EXTI line 0 from PB0, falling edge, as interrupt and as event.
	RCC->APB2PCENR |= RCC_AFIOEN;
	AFIO->EXTICR[0] = ( AFIO->EXTICR[0] & ~AFIO_EXTICR1_EXTI0 ) | AFIO_EXTICR1_EXTI0_PB;
	EXTI->RTENR &= ~1;
	EXTI->FTENR |= 1;
	EXTI->INTFR = 1;
	EXTI->INTENR |= 1;
	EXTI->EVENR |= 1;
	NVIC_EnableIRQ( EXTI0_IRQn );

	// Release every pin (analog input) except the debug wires and FD (floating input).
	// PB2 has no pin on this package: pull it down.
	GPIOA->CFGLR = 0;
	GPIOA->CFGHR = GPIOA->CFGHR & 0x0ff00000;  // keep PA13, PA14
	GPIOB->CFGLR = 0x00000804;
	GPIOB->CFGHR = 0;
	GPIOB->OUTDR = 0;

	// USB-PD pull-downs off (see b1-standby).
	RCC->AHBPCENR |= RCC_USBPD;
	USBPD->PORT_CC1 &= ~CC_PD;
	USBPD->PORT_CC2 &= ~CC_PD;

	uint32_t ctlr = PWR->CTLR;
	ctlr &= ~( PWR_CTLR_FLASH_LP | PWR_CTLR_PDDS | PWR_CTLR_LPDS );
	ctlr |= PWR_CTLR_FLASH_LP_1 | PWR_CTLR_CWUF;

	if( !stop )
	{
		PWR->CSR |= PWR_CSR_EWUP;
		PWR->CTLR = ctlr | PWR_CTLR_PDDS;
		NVIC->SCTLR |= ( 1 << 2 );
		__WFI();
		// Not reached if Standby was entered (or reached at once, if the EXTI interrupt is pending).
		leds_on();
		while( 1 ) flash( LED_G, 1, 50 );
	}

	PWR->CTLR = ctlr | PWR_CTLR_LPDS;          // Stop, regulator in low-power mode
	NVIC->SCTLR |= ( 1 << 2 );
	__WFI();
	NVIC->SCTLR &= ~( 1 << 2 );
	leds_on();                                 // now on the 8 MHz HSI: delays run twice as long
	for( int i = 0; i < 6; i++ ) { flash( LED_O, 1, 60 ); flash( LED_G, 1, 60 ); }
	NVIC_SystemReset();
	while( 1 );
}
