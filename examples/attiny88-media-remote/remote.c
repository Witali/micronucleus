/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "remote.h"
#include "config.h"
#include <string.h>

uint8_t remote_report[8], remote_report_length;
uint8_t remote_consumer_report[3] = {REMOTE_INPUT_ID, 0, 0};
uint8_t remote_keyboard_report[8] = {REMOTE_KEYBOARD_ID, 0, 0, 0, 0, 0, 0, 0};
uint8_t remote_idle_rate[2];
uint16_t remote_profiles[REMOTE_PRESETS][REMOTE_BUTTONS] = {
    REMOTE_DEFAULT_MAPPING, REMOTE_DEFAULT_MAPPING, REMOTE_DEFAULT_MAPPING
};
uint8_t remote_preset_count = 1, remote_active_preset, remote_cycle_button = 7;
static uint8_t stable, blocked, debounce[REMOTE_BUTTONS];
static uint16_t repeat[REMOTE_BUTTONS];
static uint8_t consumer_queue[8], consumer_head, consumer_count;
static uint8_t keyboard_queue[8], keyboard_head, keyboard_count;
static uint8_t hold, initial_reports;
static uint16_t idle[2], mute_lease;
static uint8_t mute_state, injected;
static uint16_t injection_lease, simulation_ms;
static uint8_t simulation_finished;

uint8_t remote_consumer_valid(uint16_t usage)
{
    switch (usage) {
    case REMOTE_MUTE: case REMOTE_VOLUME_UP: case REMOTE_VOLUME_DOWN:
    case REMOTE_PLAY_PAUSE: case REMOTE_NEXT: case REMOTE_PREVIOUS: case REMOTE_STOP:
    case REMOTE_BROWSER: case REMOTE_MAIL: case REMOTE_CALCULATOR:
        return 1;
    default: return 0;
    }
}

uint8_t remote_binding_valid(uint16_t binding)
{
    if (!binding) return 1;
    uint8_t kind = binding >> 12, code = binding;
    if (kind == REMOTE_KEYBOARD)
        return (code >= 4 && code <= 0x73) || (!code && (binding & 0x0f00));
    if (kind == REMOTE_CONSUMER)
        return remote_consumer_valid(binding & 0x0fff);
    return 0;
}

static void clear_reports(void)
{
    consumer_head = consumer_count = keyboard_head = keyboard_count = hold = 0;
    memset(remote_consumer_report + 1, 0, 2);
    memset(remote_keyboard_report + 1, 0, 7);
    initial_reports = 3;
}

void remote_reset(void)
{
    if (simulation_ms >= 5000) simulation_finished = 1;
    simulation_ms = 0;
    stable = blocked = injected = 0;
    injection_lease = mute_lease = mute_state = 0;
    memset(debounce, 0, sizeof debounce);
    memset(repeat, 0, sizeof repeat);
    clear_reports();
    remote_set_idle(0, 0);
}

uint8_t remote_select_preset(uint8_t preset)
{
    if (preset >= remote_preset_count) return 0;
    remote_active_preset = preset;
    blocked = stable;
    clear_reports();
    return 1;
}

void remote_default_config(void)
{
    memset(remote_profiles, 0, sizeof remote_profiles);
    for (uint8_t layer = 0; layer < REMOTE_PRESETS; ++layer) {
        remote_profiles[layer][0] = REMOTE_MEDIA(REMOTE_MUTE);
        remote_profiles[layer][1] = REMOTE_MEDIA(REMOTE_VOLUME_UP);
        remote_profiles[layer][2] = REMOTE_MEDIA(REMOTE_VOLUME_DOWN);
    }
    remote_preset_count = 1; remote_cycle_button = 7;
    remote_select_preset(0);
}

uint8_t remote_configure(const uint8_t bytes[REMOTE_CONFIG_BYTES])
{
    if (!bytes[0] || bytes[0] > REMOTE_PRESETS || (bytes[1] >= REMOTE_BUTTONS && bytes[1] != 0xff))
        return 0;
    for (uint8_t i = 2; i < REMOTE_CONFIG_BYTES; i += 2)
        if (!remote_binding_valid(bytes[i] | ((uint16_t)bytes[i + 1] << 8))) return 0;
    remote_preset_count = bytes[0];
    remote_cycle_button = bytes[1];
    for (uint8_t profile = 0; profile < REMOTE_PRESETS; ++profile)
        for (uint8_t button = 0; button < REMOTE_BUTTONS; ++button) {
            uint8_t at = 2 + (profile * REMOTE_BUTTONS + button) * 2;
            remote_profiles[profile][button] = bytes[at] | ((uint16_t)bytes[at + 1] << 8);
        }
    return remote_select_preset(remote_active_preset < remote_preset_count ? remote_active_preset : 0);
}

void remote_export_config(uint8_t bytes[REMOTE_CONFIG_BYTES])
{
    bytes[0] = remote_preset_count; bytes[1] = remote_cycle_button;
    for (uint8_t profile = 0; profile < REMOTE_PRESETS; ++profile)
        for (uint8_t button = 0; button < REMOTE_BUTTONS; ++button) {
            uint8_t at = 2 + (profile * REMOTE_BUTTONS + button) * 2;
            uint16_t value = remote_profiles[profile][button];
            bytes[at] = value; bytes[at + 1] = value >> 8;
        }
}

void remote_set_idle(uint8_t id, uint8_t rate)
{
    for (uint8_t i = 0; i < 2; ++i)
        if (!id || id == (i ? REMOTE_KEYBOARD_ID : REMOTE_INPUT_ID)) {
            remote_idle_rate[i] = rate;
            idle[i] = (uint16_t)rate * 4;
        }
}

void remote_set_mute_state(uint8_t state) { mute_state = state & 3; mute_lease = 3000; }
uint8_t remote_mute_led(void) { return mute_lease && mute_state == 3; }
void remote_inject_buttons(uint8_t pressed) { injected = pressed; injection_lease = 250; }
uint8_t remote_injected_buttons(void) { return injection_lease ? injected : 0; }

uint8_t remote_simulated_buttons(void)
{
#if REMOTE_SIMULATE
    if (!simulation_finished) {
        if (simulation_ms >= 5000 && simulation_ms < 5080) return 1;
        if (simulation_ms >= 7000 && simulation_ms < 7080) return 2;
        if (simulation_ms >= 9000 && simulation_ms < 9080) return 4;
    }
#endif
    return 0;
}

static void queue_consumer(uint8_t button)
{
    if (consumer_count < sizeof consumer_queue) {
        consumer_queue[(consumer_head + consumer_count) % sizeof consumer_queue] = button;
        ++consumer_count;
    }
}

static void queue_keyboard(void)
{
    if (keyboard_count == sizeof keyboard_queue) {
        /* Overflow must still release every old key before the latest state. */
        keyboard_head = 0; keyboard_count = 1; keyboard_queue[0] = 0;
    }
    keyboard_queue[(keyboard_head + keyboard_count) % sizeof keyboard_queue] = stable & (uint8_t)~blocked;
    ++keyboard_count;
}

void remote_tick_ms(uint8_t pressed)
{
#if REMOTE_SIMULATE
    if (!simulation_finished) {
        if (simulation_ms < 10000) ++simulation_ms;
        else simulation_finished = 1;
    }
#endif
    if (hold) --hold;
    if (mute_lease) --mute_lease;
    if (injection_lease) --injection_lease;
    for (uint8_t i = 0; i < 2; ++i) if (idle[i]) --idle[i];
    uint8_t keyboard_changed = 0;
    for (uint8_t i = 0; i < REMOTE_BUTTONS; ++i) {
        uint8_t mask = (uint8_t)1 << i, down = pressed & mask;
        uint16_t binding = remote_profiles[remote_active_preset][i];
        uint8_t kind = binding >> 12;
        if (!!down == !!(stable & mask)) debounce[i] = 0;
        else if (++debounce[i] >= REMOTE_DEBOUNCE_MS) {
            debounce[i] = 0; stable ^= mask;
            if (i == remote_cycle_button) {
                if (down && !(blocked & mask)) {
                    remote_select_preset((remote_active_preset + 1) % remote_preset_count);
                    blocked = stable | pressed;
                } else if (!down) blocked &= (uint8_t)~mask;
                continue;
            }
            if (kind == REMOTE_KEYBOARD) keyboard_changed = 1;
            if (down && !(blocked & mask)) {
                if (kind == REMOTE_CONSUMER) queue_consumer(i);
                repeat[i] = REMOTE_REPEAT_DELAY_MS;
            } else { repeat[i] = 0; blocked &= (uint8_t)~mask; }
            continue;
        }
        if ((stable & mask) && !(blocked & mask) && repeat[i] && --repeat[i] == 0 &&
            i != remote_cycle_button && kind == REMOTE_CONSUMER &&
            (binding == REMOTE_MEDIA(REMOTE_VOLUME_UP) || binding == REMOTE_MEDIA(REMOTE_VOLUME_DOWN))) {
            queue_consumer(i); repeat[i] = REMOTE_REPEAT_MS;
        }
    }
    if (keyboard_changed) queue_keyboard();
}

static void keyboard_state(uint8_t buttons)
{
    memset(remote_keyboard_report + 1, 0, 7);
    uint8_t count = 0;
    for (uint8_t i = 0; i < REMOTE_BUTTONS; ++i) {
        uint16_t binding = remote_profiles[remote_active_preset][i];
        uint8_t kind = binding >> 12;
        if (i == remote_cycle_button || !(buttons & ((uint8_t)1 << i)) || kind != REMOTE_KEYBOARD) continue;
        remote_keyboard_report[1] |= (binding >> 8) & 15;
        uint8_t code = binding;
        if (!code) continue;
        uint8_t duplicate = 0;
        for (uint8_t j = 0; j < count && j < 6; ++j)
            if (remote_keyboard_report[j + 2] == code) duplicate = 1;
        if (!duplicate && count < 6) remote_keyboard_report[2 + count++] = code;
        else if (!duplicate) count = 7;
    }
    if (count > 6) memset(remote_keyboard_report + 2, 1, 6);
}

static uint8_t emit(uint8_t keyboard)
{
    remote_report_length = keyboard ? 8 : 3;
    memcpy(remote_report, keyboard ? remote_keyboard_report : remote_consumer_report, remote_report_length);
    idle[keyboard] = (uint16_t)remote_idle_rate[keyboard] * 4;
    return 1;
}

uint8_t remote_next_report(void)
{
    if (initial_reports & 1) { initial_reports &= (uint8_t)~1; return emit(0); }
    if (initial_reports & 2) { initial_reports &= (uint8_t)~2; return emit(1); }
    if ((remote_consumer_report[1] || remote_consumer_report[2]) && !hold) {
        remote_consumer_report[1] = remote_consumer_report[2] = 0;
        return emit(0);
    }
    if (keyboard_count) {
        keyboard_state(keyboard_queue[keyboard_head]);
        keyboard_head = (keyboard_head + 1) % sizeof keyboard_queue; --keyboard_count;
        return emit(1);
    }
    if (!remote_consumer_report[1] && !remote_consumer_report[2] && consumer_count) {
        uint16_t binding = remote_profiles[remote_active_preset][consumer_queue[consumer_head]];
        consumer_head = (consumer_head + 1) % sizeof consumer_queue; --consumer_count;
        remote_consumer_report[1] = binding; remote_consumer_report[2] = (binding >> 8) & 15;
        hold = REMOTE_HOLD_MS; return emit(0);
    }
    if (remote_idle_rate[0] && !idle[0]) return emit(0);
    if (remote_idle_rate[1] && !idle[1]) return emit(1);
    return 0;
}
