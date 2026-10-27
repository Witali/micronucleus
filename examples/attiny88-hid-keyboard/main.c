/* SPDX-License-Identifier: GPL-2.0-or-later */
/* MH-Tiny88, external 16 MHz clock, USB D-=PD1 / D+=PD2, LED=PD0. */
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/power.h>
#include <avr/wdt.h>
#include <util/delay.h>
#include "usbdrv.h"
#include "keyboard.h"

PROGMEM const char usbHidReportDescriptor[] = {
    0x05, 0x01,       /* Usage Page (Generic Desktop) */
    0x09, 0x06,       /* Usage (Keyboard) */
    0xa1, 0x01,       /* Collection (Application) */
    0x05, 0x07,       /* Usage Page (Keyboard/Keypad) */
    0x19, 0xe0, 0x29, 0xe7, /* Left Control through Right GUI */
    0x15, 0x00, 0x25, 0x01,
    0x75, 0x01, 0x95, 0x08, 0x81, 0x02, /* Eight modifier bits */
    0x95, 0x01, 0x75, 0x08, 0x81, 0x01, /* Reserved byte */
    0x95, 0x05, 0x75, 0x01,
    0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x91, 0x02, /* Five LEDs */
    0x95, 0x01, 0x75, 0x03, 0x91, 0x01, /* LED padding */
    0x95, 0x06, 0x75, 0x08,
    0x15, 0x00, 0x25, 0x65,
    0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x81, 0x00, /* Six key slots */
    0xc0
};

PROGMEM const char usbDescriptorConfiguration[] = {
    9, USBDESCR_CONFIG, 34, 0, 1, 1, 0, (char)0x80, 50,
    9, USBDESCR_INTERFACE, 0, 0, 1, 3, 1, 1, 0,
    9, USBDESCR_HID, 0x11, 0x01, 0, 1, USBDESCR_HID_REPORT,
    USB_CFG_HID_REPORT_DESCRIPTOR_LENGTH, 0,
    7, USBDESCR_ENDPOINT, (char)0x81, 3, KEYBOARD_REPORT_BYTES, 0, 10
};

_Static_assert(sizeof usbHidReportDescriptor == USB_CFG_HID_REPORT_DESCRIPTOR_LENGTH,
               "HID descriptor size differs from usbconfig.h");
_Static_assert(sizeof usbDescriptorConfiguration == USB_CFG_DESCR_PROPS_CONFIGURATION,
               "USB configuration size differs from usbconfig.h");

static uint8_t protocol = 1;
static uint8_t host_leds;
static uint8_t led_write_pending;

/* Disable an inherited watchdog before C startup, including after WDT reset. */
void early_watchdog_off(void) __attribute__((naked, used, section(".init3")));
void early_watchdog_off(void)
{
    MCUSR = 0;
    wdt_disable();
}

void keyboard_usb_reset(unsigned char reset_starts)
{
    if (reset_starts) {
        usbConfiguration = 0; /* Upstream V-USB does not clear this on reset. */
        protocol = 1;
        host_leds = 0;
        led_write_pending = 0;
        keyboard_reset();
        PORTD &= (uint8_t)~_BV(PD0);
    }
}

usbMsgLen_t usbFunctionSetup(uchar data[8])
{
    usbRequest_t *request = (void *)data;
    led_write_pending = 0;
    if (request->wIndex.word != 0)
        return 0;

    if (request->bmRequestType == 0xa1) { /* Class, interface, device to host */
        switch (request->bRequest) {
        case USBRQ_HID_GET_REPORT:
            if (request->wValue.bytes[0] != 0)
                return 0; /* No report IDs. */
            if (request->wValue.bytes[1] == 1) {
                usbMsgPtr = keyboard_report;
                return sizeof keyboard_report;
            }
            if (request->wValue.bytes[1] == 2) {
                usbMsgPtr = &host_leds;
                return 1;
            }
            break;
        case USBRQ_HID_GET_IDLE:
            usbMsgPtr = &keyboard_idle_rate;
            return 1;
        case USBRQ_HID_GET_PROTOCOL:
            usbMsgPtr = &protocol;
            return 1;
        }
    } else if (request->bmRequestType == 0x21) { /* Host to device */
        switch (request->bRequest) {
        case USBRQ_HID_SET_IDLE:
            if (request->wValue.bytes[0] == 0 && request->wLength.word == 0)
                keyboard_set_idle(request->wValue.bytes[1]); /* Units: 4 ms */
            break;
        case USBRQ_HID_SET_PROTOCOL:
            if (request->wValue.word <= 1 && request->wLength.word == 0)
                protocol = request->wValue.bytes[0]; /* Both use 8-byte reports. */
            break;
        case USBRQ_HID_SET_REPORT:
            if (request->wValue.word == 0x0200 && request->wLength.word == 1) {
                led_write_pending = 1;
                return USB_NO_MSG;
            }
            break;
        }
    }
    return 0;
}

uchar usbFunctionWrite(uchar *data, uchar length)
{
    if (!led_write_pending || length != 1)
        return 0xff;
    host_leds = data[0] & 0x1f;
    led_write_pending = 0;
    return 1;
}

int main(void)
{
    cli();
    clock_prescale_set(clock_div_1);
    /* The bootloader can leave interrupt flags and timer settings behind. */
    EIMSK = 0;
    PCICR = 0;
    TIMSK0 = 0;
    TIMSK1 = 0;
    EICRA = _BV(ISC00) | _BV(ISC01);
    EIFR = _BV(INTF0);
    PORTD &= (uint8_t)~(USBMASK | _BV(PD0));
    DDRD = (DDRD & (uint8_t)~USBMASK) | _BV(PD0);

    usbInit();
    /* Force fresh enumeration when changing from bootloader to HID identity. */
    usbDeviceDisconnect();
    _delay_ms(250);
    usbDeviceConnect();

    /* Timer1: 16 MHz / 64 = 250 ticks/ms. Poll it; no timer ISR delays USB. */
    TCCR1A = 0;
    TCCR1B = _BV(CS11) | _BV(CS10);
    TCNT1 = 0;
    uint16_t last_tick = 0;
    uint8_t was_configured = 0;
    keyboard_reset();
    sei();

    for (;;) {
        usbPoll();
        if (!usbConfiguration) {
            if (was_configured)
                keyboard_reset();
            was_configured = 0;
            last_tick = TCNT1;
            PORTD &= (uint8_t)~_BV(PD0);
            continue;
        }
        was_configured = 1;
        if ((uint16_t)(TCNT1 - last_tick) >= 250) {
            last_tick += 250;
            keyboard_tick_ms();
        }
        if (usbInterruptIsReady() && keyboard_next_report())
            usbSetInterrupt(keyboard_report, sizeof keyboard_report);
        if (keyboard_done)
            PORTD |= _BV(PD0);
    }
}
