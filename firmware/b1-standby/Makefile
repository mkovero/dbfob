# B1 Standby test for the CH32L103 (rev B stick): for measuring the sleep current. Not the meter firmware.
#   make         - compile
#   make flash   - flash (CELL OUT). If the board is asleep, press its button first: it then stays
#                  awake for 8 s (red LED blinking), and the programmer can only attach in that time.
all : build

TARGET := b1standby
TARGET_MCU := CH32L103
TARGET_MCU_PACKAGE := CH32L103F8U6

include ../ch32fun/ch32fun/ch32fun.mk

build : $(TARGET).bin
flash : cv_flash
clean : cv_clean
