/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/power.h>
#include <avr/wdt.h>
#include <avr/eeprom.h>
#include <util/delay.h>
#include "usbdrv.h"
#include "remote.h"
#include "config.h"
#include "storage.h"

PROGMEM const char usbHidReportDescriptor[] = {
    0x05, 0x0c, 0x09, 0x01, 0xa1, 0x01, /* Consumer Control */
    0x85, REMOTE_INPUT_ID,
    0x15, 0x00, 0x26, (char)0xff, 0x03,
    0x19, 0x00, 0x2a, (char)0xff, 0x03,
    0x75, 0x10, 0x95, 0x01, 0x81, 0x00, 0xc0,
    0x06, 0x00, (char)0xff, 0x09, 0x01, 0xa1, 0x01, /* Vendor control */
    0x85, REMOTE_LED_ID, 0x09, 0x02,
    0x15, 0x00, 0x26, (char)0xff, 0x00,
    0x75, 0x08, 0x95, 0x01, 0x91, 0x02, /* Mute feedback flags */
    0x85, REMOTE_MAPPING_ID, 0x09, 0x03, 0x95, 0x07, 0xb1, 0x02, 0xc0
};
PROGMEM const char usbDescriptorConfiguration[] = {
    9, USBDESCR_CONFIG, 34, 0, 1, 1, 0, (char)0x80, 50,
    9, USBDESCR_INTERFACE, 0, 0, 1, 3, 0, 0, 0,
    9, USBDESCR_HID, 0x11, 1, 0, 1, USBDESCR_HID_REPORT,
    USB_CFG_HID_REPORT_DESCRIPTOR_LENGTH, 0,
    7, USBDESCR_ENDPOINT, (char)0x81, 3, 8, 0, 10
};
_Static_assert(sizeof usbHidReportDescriptor == USB_CFG_HID_REPORT_DESCRIPTOR_LENGTH, "HID length");
static uint8_t control_report[8];
static uint8_t write_id;

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
        write_id = 0;
        remote_reset();
    }
}

usbMsgLen_t usbFunctionSetup(uchar bytes[8])
{
    usbRequest_t *rq = (void *)bytes;
    uint8_t id = rq->wValue.bytes[0];
    uint8_t type = rq->wValue.bytes[1];
    write_id = 0;
    if (rq->wIndex.word)
        return 0;
    if (rq->bmRequestType == 0xa1) {
        if (rq->bRequest == USBRQ_HID_GET_IDLE && (id == 0 || id == REMOTE_INPUT_ID)) {
            usbMsgPtr = &remote_idle_rate;
            return 1;
        }
        if (rq->bRequest == USBRQ_HID_GET_REPORT) {
            if (id == REMOTE_INPUT_ID && type == 1) {
                usbMsgPtr = remote_report;
                return sizeof remote_report;
            }
            if (id == REMOTE_MAPPING_ID && type == 3) {
                control_report[0] = REMOTE_MAPPING_ID;
                control_report[1] = 1 | (storage_busy ? 0x10 : 0) | (storage_error ? 0x20 : 0);
                for (uint8_t i = 0; i < REMOTE_BUTTONS; ++i) {
                    control_report[2 + i * 2] = remote_mapping[i];
                    control_report[3 + i * 2] = remote_mapping[i] >> 8;
                }
                usbMsgPtr = control_report;
                return sizeof control_report;
            }
        }
    } else if (rq->bmRequestType == 0x21) {
        if (rq->bRequest == USBRQ_HID_SET_IDLE && (id == 0 || id == REMOTE_INPUT_ID) && !rq->wLength.word)
            remote_set_idle(type);
        if (rq->bRequest == USBRQ_HID_SET_REPORT &&
            ((id == REMOTE_LED_ID && type == 2 && rq->wLength.word == 2) ||
             (id == REMOTE_MAPPING_ID && type == 3 && rq->wLength.word == 8))) {
            write_id = id;
            return USB_NO_MSG;
        }
    }
    return 0;
}

uchar usbFunctionWrite(uchar *data, uchar length)
{
    uint8_t id = write_id;
    write_id = 0;
    if (id == REMOTE_LED_ID && length == 2 && data[0] == id && data[1] <= 3) {
        remote_set_mute_state(data[1]);
        return 1;
    }
    if (id == REMOTE_MAPPING_ID && length == 8 && data[0] == id &&
        (data[1] == 1 || data[1] == 0x81) && !storage_busy) {
        uint16_t mapping[REMOTE_BUTTONS];
        for (uint8_t i = 0; i < REMOTE_BUTTONS; ++i)
            mapping[i] = data[2 + i * 2] | ((uint16_t)data[3 + i * 2] << 8);
        if (!remote_set_mapping(mapping))
            return 0xff;
        if (data[1] & 0x80)
            return storage_save(mapping) ? 1 : 0xff;
        return 1;
    }
    return 0xff;
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
    PORTD &= (uint8_t)~(USBMASK | _BV(PD0));
    DDRD = (DDRD & (uint8_t)~USBMASK) | _BV(PD0);
    uint8_t buttons = _BV(REMOTE_BUTTON0_BIT) | _BV(REMOTE_BUTTON1_BIT) | _BV(REMOTE_BUTTON2_BIT);
    DDRC &= (uint8_t)~buttons;
    PORTC |= buttons;
    MCUCR &= (uint8_t)~_BV(PUD);
    PORTCR &= (uint8_t)~_BV(PUDC);
    DIDR0 &= (uint8_t)~(_BV(ADC0D) | _BV(ADC1D) | _BV(ADC2D));
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
            uint8_t pins = (uint8_t)~PINC;
            uint8_t pressed = (!!(pins & _BV(REMOTE_BUTTON0_BIT))) |
                              (!!(pins & _BV(REMOTE_BUTTON1_BIT)) << 1) |
                              (!!(pins & _BV(REMOTE_BUTTON2_BIT)) << 2);
            remote_tick_ms(pressed | remote_simulated_buttons());
        }
        if (usbInterruptIsReady() && remote_next_report())
            usbSetInterrupt(remote_report, sizeof remote_report);
        if (remote_mute_led())
            PORTD |= _BV(PD0);
        else
            PORTD &= (uint8_t)~_BV(PD0);
    }
}
