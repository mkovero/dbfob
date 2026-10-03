#ifndef _FUNCONFIG_H
#define _FUNCONFIG_H

// 48 MHz from the HSI PLL (ch32fun default for the CH32V003)
#define FUNCONF_USE_HSI 1
#define FUNCONF_USE_PLL 1
// SysTick at the core clock: Delay_* and the ISR cycle counter share it
#define FUNCONF_SYSTICK_USE_HCLK 1
#ifdef DBFOB_SWIO_PRINTF
// Bring-up builds (make PRINTF=swio): printf over the SWIO programming wire, shown by
// `make monitor` through the same programmer (WCH-LinkE or ESP32-S2) - no USB-UART needed.
// Each printf waits up to ~200 ms when no programmer is listening, so not for normal use.
#define FUNCONF_USE_DEBUGPRINTF 1
#define FUNCONF_USE_UARTPRINTF 0
#else
// Normal builds: readings over USART1 TX on PD5 (J1 pin 4, "T"), 115200 8N1, never blocks
#define FUNCONF_USE_UARTPRINTF 1
#define FUNCONF_UART_PRINTF_BAUD 115200
#define FUNCONF_USE_DEBUGPRINTF 0
#endif

#endif
