/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TINY88_REMOTE_STORAGE_H
#define TINY88_REMOTE_STORAGE_H
#include "remote.h"
extern uint8_t storage_busy;
extern uint8_t storage_error;
void storage_init(void);
uint8_t storage_save(const uint16_t mapping[REMOTE_BUTTONS]);
void storage_poll(void);
/* Board hooks: never wait for a pending EEPROM write in the polling path. */
uint8_t storage_hw_ready(void);
uint8_t storage_hw_read(uint8_t address);
void storage_hw_write(uint8_t address, uint8_t value);
#endif
