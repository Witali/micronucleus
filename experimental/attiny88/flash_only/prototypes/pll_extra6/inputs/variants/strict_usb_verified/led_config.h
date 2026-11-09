/* Reconstructed from Witali/micronucleus strict_usb_verified/led_config.h */
#ifndef T88_LED_CONFIG_H
#define T88_LED_CONFIG_H
#define NONE 0
#define ACTIVE_HIGH 1
#define ACTIVE_LOW 2
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
#error "Invalid LED_MODE"
#endif
#if LED_MODE != NONE
#if LED_PIN < 0 || LED_PIN > 7
#error "Invalid LED_PIN"
#endif
#if !((LED_DDR_IO == 0x04 && LED_PORT_IO == 0x05) || (LED_DDR_IO == 0x07 && LED_PORT_IO == 0x08) || (LED_DDR_IO == 0x0a && LED_PORT_IO == 0x0b) || (LED_DDR_IO == 0x0d && LED_PORT_IO == 0x0e))
#error "Invalid LED_DDR_IO/PORT_IO"
#endif
#if LED_DDR_IO == 0x0d && LED_PIN > 3
#error "Invalid PA pin"
#endif
#if LED_DDR_IO == 0x0a && (LED_PIN == 1 || LED_PIN == 2)
#error "USB pins are reserved"
#endif
#if (LED_DDR_IO == 0x04 && LED_PIN == 6) || (LED_DDR_IO == 0x07 && LED_PIN == 6)
#error "Clock/RESET pins reserved"
#endif
#if LED_BLINK_MASK < 1 || LED_BLINK_MASK > 255
#error "Invalid LED_BLINK_MASK"
#endif
#endif
#endif
