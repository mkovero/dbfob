#ifndef _FUNCONFIG_H
#define _FUNCONFIG_H

// 48 MHz from the HSI PLL (ch32fun default for the CH32V003)
#define FUNCONF_USE_HSI 1
#define FUNCONF_USE_PLL 1
// SysTick at the core clock: Delay_* and the ISR cycle counter share it
#define FUNCONF_SYSTICK_USE_HCLK 1
// Readings over USART1 TX on PD5 (J1 pin 4, "T"), 115200 8N1
#define FUNCONF_USE_UARTPRINTF 1
#define FUNCONF_UART_PRINTF_BAUD 115200
#define FUNCONF_USE_DEBUGPRINTF 0

#endif
