/* Compile-time LED configuration for the verified ATtiny88 assembly loader.
 * Override with -D; LED_MODE=NONE emits no instructions. Addresses are I/O-space
 * addresses, not SRAM addresses or avr-libc C register expressions.
 */
#ifndef T88_LED_CONFIG_H
#define T88_LED_CONFIG_H

#define NONE        0
#define ACTIVE_HIGH 1
#define ACTIVE_LOW  2

#ifndef LED_MODE
#define LED_MODE NONE
#endif
#ifndef LED_DDR_IO
#define LED_DDR_IO 0x0a
#endif
#ifndef LED_PORT_IO
#define LED_PORT_IO 0x0b
#endif
#ifndef LED_PIN
#define LED_PIN 0
#endif
#ifndef LED_BLINK_MASK
#define LED_BLINK_MASK 0x4c
#endif

#if LED_MODE != NONE && LED_MODE != ACTIVE_HIGH && LED_MODE != ACTIVE_LOW
#error "LED_MODE must be NONE, ACTIVE_HIGH or ACTIVE_LOW"
#endif
#if LED_MODE != NONE
#if LED_PIN < 0 || LED_PIN > 7
#error "LED_PIN must be a bit number from 0 to 7"
#endif
#if !((LED_DDR_IO == 0x04 && LED_PORT_IO == 0x05) || \
      (LED_DDR_IO == 0x07 && LED_PORT_IO == 0x08) || \
      (LED_DDR_IO == 0x0a && LED_PORT_IO == 0x0b) || \
      (LED_DDR_IO == 0x0d && LED_PORT_IO == 0x0e))
#error "Use a matching ATtiny88 DDR/PORT I/O address pair"
#endif
#if LED_DDR_IO == 0x0d && LED_PIN > 3
#error "ATtiny88 Port A has only PA0 through PA3 (check package availability)"
#endif
#if LED_DDR_IO == 0x0a && (LED_PIN == 1 || LED_PIN == 2)
#error "PD1 and PD2 are reserved for USB"
#endif
#if (LED_DDR_IO == 0x04 && LED_PIN == 6) || (LED_DDR_IO == 0x07 && LED_PIN == 6)
#error "PB6 and PC6 are reserved for the clock and RESET on this USB target"
#endif
#if LED_BLINK_MASK < 1 || LED_BLINK_MASK > 255
#error "LED_BLINK_MASK must be a nonzero 8-bit mask"
#endif
#endif
#endif
