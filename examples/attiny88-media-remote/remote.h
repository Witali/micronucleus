/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TINY88_REMOTE_H
#define TINY88_REMOTE_H
#include <stdint.h>
#define REMOTE_BUTTONS 8
#define REMOTE_PRESETS 3
#define REMOTE_CONFIG_BYTES 50
#define REMOTE_FEATURE_BYTES 53
#define REMOTE_INPUT_ID 1
#define REMOTE_LED_ID 2
#define REMOTE_MAPPING_ID 3
#define REMOTE_KEYBOARD_ID 4
#define REMOTE_TEST_ID 5
#define REMOTE_PRESET_ID 6
#define REMOTE_DISABLED 0
#define REMOTE_KEYBOARD 1
#define REMOTE_CONSUMER 2
#define REMOTE_MUTE 0x00e2
#define REMOTE_VOLUME_UP 0x00e9
#define REMOTE_VOLUME_DOWN 0x00ea
#define REMOTE_PLAY_PAUSE 0x00cd
#define REMOTE_NEXT 0x00b5
#define REMOTE_PREVIOUS 0x00b6
#define REMOTE_STOP 0x00b7
#define REMOTE_BROWSER 0x0196
#define REMOTE_MAIL 0x018a
#define REMOTE_CALCULATOR 0x0192
/* 0=disabled; 0x1MKK=keyboard with four modifier bits; 0x2UUU=consumer. */
#define REMOTE_MEDIA(usage) (0x2000 | (usage))
#define REMOTE_KEY(code, modifiers) (0x1000 | ((uint16_t)(modifiers) << 8) | (code))
extern uint8_t remote_report[8], remote_report_length;
extern uint8_t remote_consumer_report[3], remote_keyboard_report[8];
extern uint8_t remote_idle_rate[2];
extern uint16_t remote_profiles[REMOTE_PRESETS][REMOTE_BUTTONS];
extern uint8_t remote_preset_count, remote_active_preset, remote_cycle_button;
void remote_reset(void);
void remote_tick_ms(uint8_t pressed);
uint8_t remote_next_report(void);
void remote_set_idle(uint8_t id, uint8_t rate);
uint8_t remote_binding_valid(uint16_t binding);
uint8_t remote_consumer_valid(uint16_t usage);
uint8_t remote_configure(const uint8_t bytes[REMOTE_CONFIG_BYTES]);
void remote_export_config(uint8_t bytes[REMOTE_CONFIG_BYTES]);
uint8_t remote_select_preset(uint8_t preset);
void remote_default_config(void);
void remote_set_mute_state(uint8_t state);
uint8_t remote_mute_led(void);
void remote_inject_buttons(uint8_t pressed);
uint8_t remote_injected_buttons(void);
uint8_t remote_simulated_buttons(void);
#endif
