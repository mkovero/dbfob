# B1 bring-up test for the CH32L103 (rev B stick). Not the meter firmware.
#   make         - compile
#   make flash   - flash through the ESP32-S2 programmer or a WCH-LinkE (CELL OUT)
#   make monitor - printf over the debug wires (minichlink -T)
all : build

TARGET := b1test
TARGET_MCU := CH32L103
TARGET_MCU_PACKAGE := CH32L103F8U6

include ../ch32fun/ch32fun/ch32fun.mk

build : $(TARGET).bin
flash : cv_flash
clean : cv_clean
