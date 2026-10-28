#ifndef COMPACT_DEVICE_ATTINY88_INC
#define COMPACT_DEVICE_ATTINY88_INC
#include <avr/io.h>
#define SREG_N 2
#define SREG_S 4
#include "../variants/strict_usb_verified/led_config.h"
#include "../variants/strict_usb_verified/led_macros.inc"
#ifndef BOOT_AT
#if LED_MODE == NONE
#define BOOT_AT 0x1c00
#else
#define BOOT_AT 0x1bc0
#endif
#endif
#define LOW8(value) ((value) & 0xff)
#define HIGH8(value) (((value) >> 8) & 0xff)
#define AVR_WORD_BYTES 2
#define AVR_RJMP_OPCODE 0xc000
#define AVR_RJMP_OFFSET_MASK 0x0fff
#define FLASH_PAGE_BYTES SPM_PAGESIZE
#define FLASH_PAGE_OFFSET_MASK (FLASH_PAGE_BYTES - 1)
#define FLASH_PAGE_ALIGN_MASK (0xff ^ FLASH_PAGE_OFFSET_MASK)
#define EEPROM_BYTES (E2END + 1)
#define FLASH_ERASED_BYTE 0xff
#define POSTSCRIPT_BYTES 4
#define APP_LIMIT (BOOT_AT - POSTSCRIPT_BYTES)
#define USB_MINUS_BIT PD1
#define USB_PLUS_BIT PD2
#define USB_LINE_MASK ((1 << USB_MINUS_BIT) | (1 << USB_PLUS_BIT))
#if PCIF2 != USB_PLUS_BIT
#error Pass34 EOP W1C reuses DDRD bit 2 to clear PCIF2
#endif
#define USB_LINES_CLEAR_MASK (0xff ^ USB_LINE_MASK)
#define USB_INTERRUPT_ENABLE_MASK (1 << PCINT18)
#define WATCHDOG_UNLOCK_MASK ((1 << WDCE) | (1 << WDE))
#define SPM_BUFFER_LOAD (1 << SELFPRGEN)
#define SPM_PAGE_ERASE ((1 << PGERS) | SPM_BUFFER_LOAD)
#define SPM_PAGE_WRITE ((1 << PGWRT) | SPM_BUFFER_LOAD)
#define SPM_BUFFER_CLEAR ((1 << CTPB) | SPM_BUFFER_LOAD)
#define CPU_CLOCK_HZ 16000000
#if HIGH8(_SFR_MEM_ADDR(WDTCSR)) != 0
#error Shared startup register base requires WDTCSR below 0x0100
#endif
#if (_SFR_MEM_ADDR(PCMSK2) < _SFR_MEM_ADDR(WDTCSR)) || ((_SFR_MEM_ADDR(PCMSK2) - _SFR_MEM_ADDR(WDTCSR)) > 63)
#error PCMSK2 must fit a positive STD offset from WDTCSR
#endif
#if (_SFR_MEM_ADDR(PCICR) < _SFR_MEM_ADDR(WDTCSR)) || ((_SFR_MEM_ADDR(PCICR) - _SFR_MEM_ADDR(WDTCSR)) > 63)
#error PCICR must fit a positive STD offset from WDTCSR
#endif
#endif
