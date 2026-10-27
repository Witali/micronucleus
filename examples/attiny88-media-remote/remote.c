/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "remote.h"
#include "config.h"
#include <string.h>

uint8_t remote_report[3] = {REMOTE_INPUT_ID, 0, 0};
uint8_t remote_idle_rate;
uint16_t remote_mapping[REMOTE_BUTTONS] = REMOTE_DEFAULT_MAPPING;
static uint8_t stable;
static uint8_t debounce[REMOTE_BUTTONS];
static uint16_t repeat[REMOTE_BUTTONS];
static uint8_t queue[8];
static uint8_t head, count;
static uint8_t hold, initial_report;
static uint16_t idle, mute_lease;
static uint8_t mute_state;
static uint16_t simulation_ms;
static uint8_t simulation_finished;

static void enqueue(uint8_t button)
{
    if (remote_mapping[button] && count < sizeof queue) {
        queue[(head + count) % sizeof queue] = button;
        ++count;
    }
}

void remote_set_idle(uint8_t rate)
{
    remote_idle_rate = rate;
    idle = (uint16_t)rate * 4;
}

void remote_reset(void)
{
    /* USB reset cancels a test in progress instead of replaying mute toggles. */
    if (simulation_ms >= 5000)
        simulation_finished = 1;
    simulation_ms = 0;
    stable = head = count = hold = 0;
    memset(debounce, 0, sizeof debounce);
    memset(repeat, 0, sizeof repeat);
    remote_report[1] = remote_report[2] = 0;
    initial_report = 1;
    mute_state = 0;
    mute_lease = 0;
    remote_set_idle(0);
}

uint8_t remote_mapping_valid(const uint16_t mapping[REMOTE_BUTTONS])
{
    for (uint8_t i = 0; i < REMOTE_BUTTONS; ++i) {
        switch (mapping[i]) {
        case 0: case REMOTE_MUTE: case REMOTE_VOLUME_UP: case REMOTE_VOLUME_DOWN:
        case REMOTE_PLAY_PAUSE: case REMOTE_NEXT: case REMOTE_PREVIOUS: case REMOTE_STOP:
            break;
        default:
            return 0;
        }
    }
    return 1;
}

uint8_t remote_set_mapping(const uint16_t mapping[REMOTE_BUTTONS])
{
    if (!remote_mapping_valid(mapping))
        return 0;
    memcpy(remote_mapping, mapping, sizeof remote_mapping);
    head = count = hold = 0;
    remote_report[1] = remote_report[2] = 0;
    initial_report = 1;
    return 1;
}

void remote_set_mute_state(uint8_t state)
{
    mute_state = state & 3; /* Bit 1: known, bit 0: muted. */
    mute_lease = 3000;
}

uint8_t remote_mute_led(void)
{
    return mute_lease && mute_state == 3;
}

uint8_t remote_simulated_buttons(void)
{
#if REMOTE_SIMULATE
    if (!simulation_finished) {
        if (simulation_ms >= 5000 && simulation_ms < 5080)
            return 1;
        if (simulation_ms >= 7000 && simulation_ms < 7080)
            return 2;
        if (simulation_ms >= 9000 && simulation_ms < 9080)
            return 4;
    }
#endif
    return 0;
}

void remote_tick_ms(uint8_t pressed)
{
#if REMOTE_SIMULATE
    if (!simulation_finished) {
        if (simulation_ms < 10000)
            ++simulation_ms;
        else
            simulation_finished = 1;
    }
#endif
    if (hold)
        --hold;
    if (idle)
        --idle;
    if (mute_lease)
        --mute_lease;
    for (uint8_t i = 0; i < REMOTE_BUTTONS; ++i) {
        uint8_t mask = (uint8_t)1 << i;
        uint8_t down = pressed & mask;
        if (!!down == !!(stable & mask)) {
            debounce[i] = 0;
        } else if (++debounce[i] >= REMOTE_DEBOUNCE_MS) {
            debounce[i] = 0;
            stable ^= mask;
            if (down) {
                enqueue(i);
                repeat[i] = REMOTE_REPEAT_DELAY_MS;
            } else {
                repeat[i] = 0;
            }
            continue;
        }
        if ((stable & mask) && repeat[i]) {
            if (--repeat[i] == 0 &&
                (remote_mapping[i] == REMOTE_VOLUME_UP || remote_mapping[i] == REMOTE_VOLUME_DOWN)) {
                enqueue(i);
                repeat[i] = REMOTE_REPEAT_MS;
            }
        }
    }
}

uint8_t remote_next_report(void)
{
    if (initial_report) {
        initial_report = 0;
    } else if (remote_report[1] || remote_report[2]) {
        if (hold)
            goto idle_report;
        remote_report[1] = remote_report[2] = 0;
    } else if (count) {
        uint8_t button = queue[head];
        head = (head + 1) % sizeof queue;
        --count;
        uint16_t usage = remote_mapping[button];
        remote_report[1] = (uint8_t)usage;
        remote_report[2] = (uint8_t)(usage >> 8);
        hold = REMOTE_HOLD_MS;
    } else {
idle_report:
        if (!remote_idle_rate || idle)
            return 0;
    }
    idle = (uint16_t)remote_idle_rate * 4;
    return 1;
}
