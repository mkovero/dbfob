# B1 field-detect test for the CH32L103 (rev B stick): does a phone wake the board? Not the meter firmware.
#   make         - compile
#   make flash   - flash (CELL OUT). If the board is asleep, press its button first: it then stays
#                  awake for 8 s (yellow LED blinking), and the programmer can only attach in that time.
all : build

TARGET := b1fd
TARGET_MCU := CH32L103
TARGET_MCU_PACKAGE := CH32L103F8U6

include ../ch32fun/ch32fun/ch32fun.mk

build : $(TARGET).bin
flash : cv_flash
clean : cv_clean
