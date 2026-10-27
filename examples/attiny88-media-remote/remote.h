/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TINY88_REMOTE_H
#define TINY88_REMOTE_H
#include <stdint.h>

#define REMOTE_BUTTONS 3
#define REMOTE_INPUT_ID 1
#define REMOTE_LED_ID 2
#define REMOTE_MAPPING_ID 3
#define REMOTE_MUTE 0x00e2
#define REMOTE_VOLUME_UP 0x00e9
#define REMOTE_VOLUME_DOWN 0x00ea
#define REMOTE_PLAY_PAUSE 0x00cd
#define REMOTE_NEXT 0x00b5
#define REMOTE_PREVIOUS 0x00b6
#define REMOTE_STOP 0x00b7

extern uint8_t remote_report[3];
extern uint8_t remote_idle_rate;
extern uint16_t remote_mapping[REMOTE_BUTTONS];
void remote_reset(void);
void remote_tick_ms(uint8_t pressed);
uint8_t remote_next_report(void);
void remote_set_idle(uint8_t rate);
uint8_t remote_set_mapping(const uint16_t mapping[REMOTE_BUTTONS]);
uint8_t remote_mapping_valid(const uint16_t mapping[REMOTE_BUTTONS]);
void remote_set_mute_state(uint8_t state);
uint8_t remote_mute_led(void);
uint8_t remote_simulated_buttons(void);
#endif
