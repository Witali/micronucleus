/* ATtiny88 hardware and LED configuration. Byte addresses use the handoff's
 * assembler-only AVR header; the missing N/S flag bits are corrected here.
 * Entry is through hardware/watchdog RESET, with the reset stack already valid.
 */
#ifndef COMPACT_DEVICE_ATTINY88_INC
#define COMPACT_DEVICE_ATTINY88_INC
#include <avr/io.h>
/* Missing from the handoff subset; AVR SREG bit positions. */
#define SREG_N 2
#define SREG_S 4
#include "../variants/strict_usb_verified/led_config.h"
#include "../variants/strict_usb_verified/led_macros.inc"
#ifndef BOOT_AT
#define BOOT_AT 0x1b40
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
#define USB_LINES_CLEAR_MASK (0xff ^ USB_LINE_MASK)
#define USB_INTERRUPT_ENABLE_MASK (1 << PCINT18)
#define WATCHDOG_UNLOCK_MASK ((1 << WDCE) | (1 << WDE))
#define SPM_BUFFER_LOAD (1 << SELFPRGEN)
#define SPM_PAGE_ERASE ((1 << PGERS) | SPM_BUFFER_LOAD)
#define SPM_PAGE_WRITE ((1 << PGWRT) | SPM_BUFFER_LOAD)
#define SPM_BUFFER_CLEAR ((1 << CTPB) | SPM_BUFFER_LOAD)
#define CPU_CLOCK_HZ 16000000

#endif /* COMPACT_DEVICE_ATTINY88_INC */
