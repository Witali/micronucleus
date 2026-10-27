/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TINY88_KEYBOARD_H
#define TINY88_KEYBOARD_H

#include <stdint.h>

#define KEYBOARD_REPORT_BYTES 8
#define KEYBOARD_START_DELAY_MS 5000

extern uint8_t keyboard_report[KEYBOARD_REPORT_BYTES];
extern uint8_t keyboard_idle_rate;
extern uint8_t keyboard_done;

void keyboard_reset(void);
void keyboard_tick_ms(void);
void keyboard_set_idle(uint8_t rate);
/* Call only when the USB interrupt endpoint can accept a new report. */
uint8_t keyboard_next_report(void);

#endif
