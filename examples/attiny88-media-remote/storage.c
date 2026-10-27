/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "storage.h"
#include <string.h>

/* Two 16-byte slots occupy EEPROM 0x00..0x1f. 0x20..0x3f is untouched. */
#define SLOT_BYTES 16
#define RECORD_BYTES 13
#define COMMIT_AT 12
#define COMMITTED 0xa5
uint8_t storage_busy;
uint8_t storage_error;
static uint8_t active_slot, generation, target_slot, position;
static uint8_t pending[RECORD_BYTES];

static uint16_t crc(const uint8_t *bytes)
{
    uint16_t result = 0xffff;
    for (uint8_t i = 0; i < 10; ++i) {
        result ^= (uint16_t)bytes[i] << 8;
        for (uint8_t bit = 0; bit < 8; ++bit)
            result = (result & 0x8000) ? (result << 1) ^ 0x1021 : result << 1;
    }
    return result;
}

static uint8_t read_slot(uint8_t slot, uint8_t bytes[RECORD_BYTES], uint16_t mapping[REMOTE_BUTTONS])
{
    for (uint8_t i = 0; i < RECORD_BYTES; ++i)
        bytes[i] = storage_hw_read(slot * SLOT_BYTES + i);
    if (bytes[0] != 'M' || bytes[1] != 'R' || bytes[2] != 1 || bytes[COMMIT_AT] != COMMITTED)
        return 0;
    if (crc(bytes) != (bytes[10] | ((uint16_t)bytes[11] << 8)))
        return 0;
    for (uint8_t i = 0; i < REMOTE_BUTTONS; ++i)
        mapping[i] = bytes[4 + i * 2] | ((uint16_t)bytes[5 + i * 2] << 8);
    return remote_mapping_valid(mapping);
}

void storage_init(void)
{
    uint8_t bytes[RECORD_BYTES];
    uint16_t mapping[REMOTE_BUTTONS];
    active_slot = 0xff;
    generation = 0;
    storage_busy = storage_error = 0;
    for (uint8_t slot = 0; slot < 2; ++slot) {
        if (read_slot(slot, bytes, mapping) &&
            (active_slot == 0xff || (int8_t)(bytes[3] - generation) > 0)) {
            active_slot = slot;
            generation = bytes[3];
            remote_set_mapping(mapping);
        }
    }
}

uint8_t storage_save(const uint16_t mapping[REMOTE_BUTTONS])
{
    if (storage_busy || !remote_mapping_valid(mapping))
        return 0;
    target_slot = active_slot == 0 ? 1 : 0;
    pending[0] = 'M'; pending[1] = 'R'; pending[2] = 1;
    pending[3] = generation + 1;
    for (uint8_t i = 0; i < REMOTE_BUTTONS; ++i) {
        pending[4 + i * 2] = mapping[i];
        pending[5 + i * 2] = mapping[i] >> 8;
    }
    uint16_t checksum = crc(pending);
    pending[10] = checksum; pending[11] = checksum >> 8;
    pending[COMMIT_AT] = COMMITTED;
    position = 0;
    storage_error = 0;
    storage_busy = 1;
    return 1;
}

void storage_poll(void)
{
    if (!storage_busy || !storage_hw_ready())
        return;
    uint8_t base = target_slot * SLOT_BYTES;
    if (position == 0) {
        storage_hw_write(base + COMMIT_AT, 0); /* Invalidate target first. */
    } else if (position <= COMMIT_AT) {
        storage_hw_write(base + position - 1, pending[position - 1]);
    } else if (position == COMMIT_AT + 1) {
        storage_hw_write(base + COMMIT_AT, COMMITTED); /* Commit last. */
    } else {
        /* Hardware is idle again: independently read back every record byte. */
        for (uint8_t i = 0; i < RECORD_BYTES; ++i)
            if (storage_hw_read(base + i) != pending[i])
                storage_error = 1;
        if (!storage_error) {
            active_slot = target_slot;
            generation = pending[3];
        }
        storage_busy = 0;
        return;
    }
    ++position;
}
