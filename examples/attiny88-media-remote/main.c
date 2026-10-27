/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/power.h>
#include <avr/wdt.h>
#include <avr/eeprom.h>
#include <util/delay.h>
#include <string.h>
#include "usbdrv.h"
#include "remote.h"
#include "config.h"
#include "storage.h"
#include "control.h"

PROGMEM const char usbHidReportDescriptor[] = {
    0x05, 0x0c, 0x09, 0x01, 0xa1, 0x01, /* Consumer Control */
    0x85, REMOTE_INPUT_ID,
    0x15, 0x00, 0x26, (char)0xff, 0x03,
    0x19, 0x00, 0x2a, (char)0xff, 0x03,
    0x75, 0x10, 0x95, 0x01, 0x81, 0x00, 0xc0,
    0x05, 0x01, 0x09, 0x06, 0xa1, 0x01, /* Keyboard, report protocol */
    0x85, REMOTE_KEYBOARD_ID, 0x05, 0x07,
    0x19, (char)0xe0, 0x29, (char)0xe7, 0x15, 0x00, 0x25, 0x01,
    0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
    0x19, 0x00, 0x29, 0x73, 0x15, 0x00, 0x25, 0x73,
    0x75, 0x08, 0x95, 0x06, 0x81, 0x00, 0xc0, /* Six keys; no reserved byte */
    0x06, 0x00, (char)0xff, 0x09, 0x01, 0xa1, 0x01, /* Vendor control */
    0x85, REMOTE_LED_ID, 0x09, 0x02,
    0x15, 0x00, 0x26, (char)0xff, 0x00,
    0x75, 0x08, 0x95, 0x01, 0x91, 0x02, /* Mute feedback flags */
    0x85, REMOTE_TEST_ID, 0x09, 0x05, 0x95, 0x01, 0x91, 0x02,
    0x85, REMOTE_PRESET_ID, 0x09, 0x06, 0x95, 0x01, 0x91, 0x02,
    0x85, REMOTE_MAPPING_ID, 0x09, 0x03, 0x95, REMOTE_FEATURE_BYTES - 1, 0xb1, 0x02, 0xc0
};
PROGMEM const char usbDescriptorConfiguration[] = {
    9, USBDESCR_CONFIG, 34, 0, 1, 1, 0, (char)0x80, 50,
    9, USBDESCR_INTERFACE, 0, 0, 1, 3, 0, 0, 0,
    9, USBDESCR_HID, 0x11, 1, 0, 1, USBDESCR_HID_REPORT,
    USB_CFG_HID_REPORT_DESCRIPTOR_LENGTH, 0,
    7, USBDESCR_ENDPOINT, (char)0x81, 3, 8, 0, 10
};
_Static_assert(sizeof usbHidReportDescriptor == USB_CFG_HID_REPORT_DESCRIPTOR_LENGTH, "HID length");

void early_watchdog_off(void) __attribute__((naked, used, section(".init3")));
void early_watchdog_off(void)
{
    MCUSR = 0;
    wdt_disable();
}

void remote_usb_reset(unsigned char starts)
{
    if (starts) {
        usbConfiguration = 0;
        remote_control_abort();
        remote_reset();
    }
}

usbMsgLen_t usbFunctionSetup(uchar bytes[8])
{
    usbRequest_t *rq = (void *)bytes;
    uint8_t id = rq->wValue.bytes[0];
    uint8_t type = rq->wValue.bytes[1];
    remote_control_abort();
    if (rq->wIndex.word)
        return 0;
    if (rq->bmRequestType == 0xa1) {
        if (rq->bRequest == USBRQ_HID_GET_IDLE &&
            (id == 0 || id == REMOTE_INPUT_ID || id == REMOTE_KEYBOARD_ID)) {
            usbMsgPtr = &remote_idle_rate[id == REMOTE_KEYBOARD_ID];
            return 1;
        }
        if (rq->bRequest == USBRQ_HID_GET_REPORT) {
            if (id == REMOTE_INPUT_ID && type == 1) {
                usbMsgPtr = remote_consumer_report;
                return sizeof remote_consumer_report;
            }
            if (id == REMOTE_KEYBOARD_ID && type == 1) {
                usbMsgPtr = remote_keyboard_report;
                return sizeof remote_keyboard_report;
            }
            if (id == REMOTE_MAPPING_ID && type == 3) {
                remote_control_read();
                usbMsgPtr = remote_control_report;
                return sizeof remote_control_report;
            }

        }
    } else if (rq->bmRequestType == 0x21) {
        if (rq->bRequest == USBRQ_HID_SET_IDLE && !rq->wLength.word)
            remote_set_idle(id, type);
        if (rq->bRequest == USBRQ_HID_SET_REPORT &&
            (((id == REMOTE_LED_ID || id == REMOTE_TEST_ID || id == REMOTE_PRESET_ID) && type == 2 && rq->wLength.word == 2) ||
             (id == REMOTE_MAPPING_ID && type == 3 && rq->wLength.word == REMOTE_FEATURE_BYTES))) {
            if (remote_control_begin(id, rq->wLength.word))
                return USB_NO_MSG;
        }
    }
    return 0;
}

uchar usbFunctionWrite(uchar *data, uchar length)
{
    return remote_control_write(data, length);
}

uint8_t storage_hw_ready(void)
{
    return eeprom_is_ready();
}

uint8_t storage_hw_read(uint8_t address)
{
    return eeprom_read_byte((const uint8_t *)(uintptr_t)address);
}

void storage_hw_write(uint8_t address, uint8_t value)
{
    /* storage_poll checks ready before calling; this starts at most one byte. */
    eeprom_update_byte((uint8_t *)(uintptr_t)address, value);
}

int main(void)
{
    cli();
    clock_prescale_set(clock_div_1);
    EIMSK = PCICR = TIMSK0 = TIMSK1 = 0;
    EICRA = _BV(ISC00) | _BV(ISC01);
    EIFR = _BV(INTF0);
    PORTD &= (uint8_t)~(USBMASK | _BV(PD0) | _BV(PD3) | _BV(PD4) | _BV(PD5));
    DDRD = (DDRD & (uint8_t)~USBMASK) | _BV(PD0) | _BV(PD3) | _BV(PD4) | _BV(PD5);
    DDRC &= (uint8_t)~REMOTE_PORTC_MASK;
    PORTC |= REMOTE_PORTC_MASK;
    DDRB &= (uint8_t)~REMOTE_PORTB_MASK;
    PORTB |= REMOTE_PORTB_MASK;
    MCUCR &= (uint8_t)~_BV(PUD);
    PORTCR &= (uint8_t)~(_BV(PUDC) | _BV(PUDB));
    DIDR0 &= (uint8_t)~REMOTE_PORTC_MASK;
    TWCR = 0;
    storage_init();
    usbInit();
    usbDeviceDisconnect();
    _delay_ms(250);
    usbDeviceConnect();
    TCCR1A = 0;
    TCCR1B = _BV(CS11) | _BV(CS10);
    TCNT1 = 0;
    uint16_t last_tick = 0;
    uint8_t configured = 0;
    remote_reset();
    sei();
    for (;;) {
        usbPoll();
        storage_poll();
        /* Constant single-bit updates compile to atomic SBI/CBI, preserving USB. */
        if (remote_active_preset == 0) PORTD |= _BV(PD3); else PORTD &= (uint8_t)~_BV(PD3);
        if (remote_active_preset == 1) PORTD |= _BV(PD4); else PORTD &= (uint8_t)~_BV(PD4);
        if (remote_active_preset == 2) PORTD |= _BV(PD5); else PORTD &= (uint8_t)~_BV(PD5);
        if (!usbConfiguration) {
            if (configured)
                remote_reset();
            configured = 0;
            last_tick = TCNT1;
            PORTD &= (uint8_t)~_BV(PD0);
            continue;
        }
        configured = 1;
        if ((uint16_t)(TCNT1 - last_tick) >= 250) {
            last_tick += 250;
            uint8_t pressed = ((uint8_t)~PINC & REMOTE_PORTC_MASK) |
                              (((uint8_t)~PINB & REMOTE_PORTB_MASK) << 6);
            remote_tick_ms(pressed | remote_simulated_buttons() | remote_injected_buttons());
        }
        if (usbInterruptIsReady() && remote_next_report())
            usbSetInterrupt(remote_report, remote_report_length);
        if (remote_mute_led())
            PORTD |= _BV(PD0);
        else
            PORTD &= (uint8_t)~_BV(PD0);
    }
}
