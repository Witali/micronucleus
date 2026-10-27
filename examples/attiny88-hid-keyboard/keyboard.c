/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "keyboard.h"
#include <string.h>

uint8_t keyboard_report[KEYBOARD_REPORT_BYTES];
uint8_t keyboard_idle_rate;
uint8_t keyboard_done;

/* USB HID Keyboard/Keypad usages for the physical H, E, L, L, O keys. */
static const uint8_t demo_keys[] = {0x0b, 0x08, 0x0f, 0x0f, 0x12};
static uint16_t start_delay;
static uint16_t idle_delay;
static uint8_t key_delay;
static uint8_t next_key;
static uint8_t release_pending;
static uint8_t initial_report;
static uint8_t demo_started;

void keyboard_reset(void)
{
    /* A USB reset during/after typing must never replay the demonstration. */
    if (demo_started)
        keyboard_done = 1;
    memset(keyboard_report, 0, sizeof keyboard_report);
    start_delay = KEYBOARD_START_DELAY_MS;
    key_delay = 0;
    release_pending = 0;
    initial_report = 1;
    keyboard_set_idle(0);
}

void keyboard_set_idle(uint8_t rate)
{
    keyboard_idle_rate = rate;
    idle_delay = (uint16_t)rate * 4;
}

void keyboard_tick_ms(void)
{
    if (start_delay)
        --start_delay;
    if (key_delay)
        --key_delay;
    if (idle_delay)
        --idle_delay;
}

uint8_t keyboard_next_report(void)
{
    if (initial_report) {
        initial_report = 0;
    } else if (!start_delay && !key_delay && !keyboard_done) {
        if (release_pending) {
            keyboard_report[2] = 0;
            release_pending = 0;
            key_delay = 80;
            if (next_key == sizeof demo_keys)
                keyboard_done = 1;
        } else {
            keyboard_report[2] = demo_keys[next_key++];
            release_pending = 1;
            demo_started = 1;
            key_delay = 40;
        }
    } else if (!keyboard_idle_rate || idle_delay) {
        return 0;
    }
    idle_delay = (uint16_t)keyboard_idle_rate * 4;
    return 1;
}
