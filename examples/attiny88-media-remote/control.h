/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TINY88_REMOTE_CONTROL_H
#define TINY88_REMOTE_CONTROL_H
#include "remote.h"
extern uint8_t remote_control_report[REMOTE_FEATURE_BYTES];
void remote_control_abort(void);
void remote_control_read(void);
uint8_t remote_control_begin(uint8_t id, uint16_t length);
uint8_t remote_control_write(const uint8_t *data, uint8_t length);
#endif
