/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "storage.h"
#include <string.h>
#define RECORD_BYTES 56
#define CRC_AT 53
#define COMMIT_AT 55
#define COMMITTED 0xa5
uint8_t storage_busy, storage_error, storage_legacy;
static uint8_t position, pending[RECORD_BYTES];

static uint16_t crc(const uint8_t *bytes, uint8_t length)
{
    uint16_t result = 0xffff;
    for (uint8_t i = 0; i < length; ++i) {
        result ^= (uint16_t)bytes[i] << 8;
        for (uint8_t bit = 0; bit < 8; ++bit)
            result = (result & 0x8000) ? (result << 1) ^ 0x1021 : result << 1;
    }
    return result;
}

static void load_legacy(uint8_t *bytes)
{
    uint8_t generation = 0;
    for (uint8_t slot = 0; slot < 2; ++slot) {
        for (uint8_t i = 0; i < 13; ++i) bytes[i] = storage_hw_read(slot * 16 + i);
        if (bytes[0] != 'M' || bytes[1] != 'R' || bytes[2] != 1 || bytes[12] != COMMITTED ||
            crc(bytes, 10) != (bytes[10] | ((uint16_t)bytes[11] << 8))) continue;
        uint16_t bindings[3];
        uint8_t valid = 1;
        for (uint8_t i = 0; i < 3; ++i) {
            uint16_t usage = bytes[4 + i * 2] | ((uint16_t)bytes[5 + i * 2] << 8);
            if (usage && !remote_consumer_valid(usage)) valid = 0;
            bindings[i] = usage ? REMOTE_MEDIA(usage) : 0;
        }
        if (valid && (!storage_legacy || (int8_t)(bytes[3] - generation) > 0)) {
            memcpy(remote_profiles[0], bindings, sizeof bindings);
            remote_preset_count = 1; remote_cycle_button = 7;
            generation = bytes[3]; storage_legacy = 1;
        }
    }
}

void storage_init(void)
{
    uint8_t bytes[RECORD_BYTES];
    remote_default_config();
    storage_busy = storage_error = storage_legacy = 0;
    for (uint8_t i = 0; i < RECORD_BYTES; ++i) bytes[i] = storage_hw_read(i);
    if (bytes[0] == 'P' && bytes[1] == '8' && bytes[2] == 3 && bytes[COMMIT_AT] == COMMITTED &&
        crc(bytes, CRC_AT) == (bytes[CRC_AT] | ((uint16_t)bytes[CRC_AT + 1] << 8)) &&
        remote_configure(bytes + 3)) return;
    load_legacy(bytes);
}

uint8_t storage_save(void)
{
    if (storage_busy) return 0;
    pending[0] = 'P'; pending[1] = '8'; pending[2] = 3;
    remote_export_config(pending + 3);
    uint16_t checksum = crc(pending, CRC_AT);
    pending[CRC_AT] = checksum; pending[CRC_AT + 1] = checksum >> 8;
    pending[COMMIT_AT] = COMMITTED;
    position = storage_error = 0;
    storage_busy = 1;
    return 1;
}

void storage_poll(void)
{
    if (!storage_busy || !storage_hw_ready()) return;
    if (!position) storage_hw_write(COMMIT_AT, 0);
    else if (position <= COMMIT_AT) storage_hw_write(position - 1, pending[position - 1]);
    else if (position == COMMIT_AT + 1) storage_hw_write(COMMIT_AT, COMMITTED);
    else {
        for (uint8_t i = 0; i < RECORD_BYTES; ++i)
            if (storage_hw_read(i) != pending[i]) storage_error = 1;
        if (!storage_error) storage_legacy = 0;
        storage_busy = 0;
        return;
    }
    ++position;
}
