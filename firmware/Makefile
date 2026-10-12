# dbfob firmware for the CH32V003 (rev A board). See README.md.
#   make build   - compile (needs riscv64-elf-gcc, e.g. Arch `riscv64-elf-gcc riscv64-elf-newlib`)
#   make flash   - build and flash with minichlink through a WCH-LinkE or ESP32-S2 (REMOVE THE CELL FIRST)
#   make flash PRINTF=swio && make monitor
#                - bring-up: printf over the SWIO wire, shown through the programmer (no USB-UART);
#                  `monitor` is ch32fun's target (minichlink -T)
#   make test    - host test of the DSP path (src/dsp.c) against IEC 61672 A-weighting
#   make check   - build, verify no software multiply in the hot path, run the host tests
#   make bench   - DSP instruction count per second of audio, under qemu-riscv32
#   make filters - regenerate src/filters.h and src/cic_tables.h
#   make dose-log - read the last dosimeter run from flash and decode it (cell out, programmer on)
all : build

TARGET := dbfob
TARGET_MCU ?= CH32V003
ADDITIONAL_C_FILES := src/dsp.c
EXTRA_CFLAGS := -Isrc
# PRINTF=swio: printf over the programming wire instead of the TX pad (see funconfig.h)
ifeq ($(PRINTF),swio)
EXTRA_CFLAGS += -DDBFOB_SWIO_PRINTF
endif

include ch32fun/ch32fun/ch32fun.mk

flash : cv_flash
clean : cv_clean

test :
	python3 test/test_dsp.py

# build + hot-path check + host tests: run before flashing anything
check : build
	@test $$(stat -c %s $(TARGET).bin) -le 15360 || { echo "firmware reaches the dose log at 0x3C00"; exit 1; }
	tools/check_hotpath.sh
	python3 test/test_dsp.py

# instruction count of the DSP under qemu-riscv32 (see test/bench.sh)
bench :
	test/bench.sh

filters :
	python3 tools/design_filters.py

dose-log :
	$(MINICHLINK)/minichlink -r dose.bin 0x08003C00 1024
	python3 tools/dose_log.py dose.bin

.PHONY : test filters check bench dose-log
