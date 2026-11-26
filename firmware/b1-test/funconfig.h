#ifndef _FUNCONFIG_H
#define _FUNCONFIG_H

// 16 MHz: HSI 8 MHz x 2 (ch32fun's default for this chip is 96 MHz, and its header does not
// build without the PLL). The mic clock is then 16 / 8 = 2 MHz.
#define FUNCONF_PLL_MULTIPLIER 2

// printf goes over the debug wires (ch32fun's default): read it with `make monitor`.

#endif
