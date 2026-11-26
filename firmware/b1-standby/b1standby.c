// B1 Standby test: for measuring the board's sleep current and proving the button wakes it.
//
// After power-on or a wake it stays awake for 8 s, blinking the red LED D3 (the window in which a
// programmer can attach), then goes to Standby with every pin released. The button (PA0 = WKUP,
// rising edge) wakes it, which is a reset. A wake from Standby shows as two green flashes first;
// a power-on shows as one yellow flash.
//
// In Standby the debug wires are dead: press the button, then flash within the 8 s.

#include "ch32fun.h"
#include <stdio.h>

#define LED_G  PA3
#define LED_Y  PA2
#define LED_O  PA1

static void flash( int pin, int n, int ms )
{
	for( int i = 0; i < n; i++ )
	{
		funDigitalWrite( pin, 1 ); Delay_Ms( ms );
		funDigitalWrite( pin, 0 ); Delay_Ms( ms );
	}
}

int main()
{
	SystemInit();
	funGpioInitAll();
	RCC->APB1PCENR |= RCC_PWREN;

	uint32_t csr = PWR->CSR;
	int woke = ( csr & PWR_CSR_WUF ) && ( csr & PWR_CSR_SBF );

	funPinMode( LED_G, GPIO_CFGLR_OUT_10Mhz_PP );
	funPinMode( LED_Y, GPIO_CFGLR_OUT_10Mhz_PP );
	funPinMode( LED_O, GPIO_CFGLR_OUT_10Mhz_PP );

	printf( "b1standby: %s (PWR_CSR %08lx)\n", woke ? "woke from Standby" : "power-on or reset", (unsigned long)csr );
	if( woke ) flash( LED_G, 2, 100 ); else flash( LED_Y, 1, 300 );

	flash( LED_O, 16, 250 );                   // 8 s awake: the programmer's window

	// Release every pin (analog input) except the debug wires, which Standby drops anyway.
	// PA0 becomes an input with pull-down by EWUP. PB2 has no pin on this package: pull it down.
	GPIOA->CFGLR = 0;
	GPIOA->CFGHR = ( GPIOA->CFGHR & 0x0ff00000 ) | 0;   // keep PA13, PA14
	GPIOB->CFGLR = 0x00000800;                 // PB2 input with pull (down: OUTDR bit is 0)
	GPIOB->CFGHR = 0;
	GPIOB->OUTDR = 0;

	PWR->CTLR |= PWR_CTLR_CWUF | PWR_CTLR_CSBF;
	PWR->CSR |= PWR_CSR_EWUP;
	// as ch32fun's examples_l103/standby: no RAM retention, flash in low power, Standby on deep sleep
	PWR->CTLR &= ~( PWR_RAMLV | PWR_CTLR_R18KVBAT | PWR_CTLR_R2KVBAT | PWR_CTLR_R18KSTY |
		PWR_CTLR_R2KSTY | PWR_CTLR_LDO_EC | PWR_CTLR_AUTO_LDO_EC | PWR_CTLR_FLASH_LP | PWR_CTLR_PVDE );
	PWR->CTLR |= PWR_CTLR_FLASH_LP_REG | PWR_CTLR_FLASH_LP_1 | PWR_CTLR_PDDS;
	NVIC->SCTLR |= ( 1 << 2 );
	__WFI();

	while( 1 ) flash( LED_O, 1, 50 );          // not reached: fast red flicker means Standby was refused
}
