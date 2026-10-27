/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "storage.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t memory[64];
uint8_t storage_hw_ready(void) { return 1; }
uint8_t storage_hw_read(uint8_t at) { assert(at < 32); return memory[at]; }
void storage_hw_write(uint8_t at, uint8_t value) { assert(at < 32); memory[at] = value; }
static void finish(void)
{
    unsigned polls = 0;
    while (storage_busy) { storage_poll(); assert(++polls <= 16); }
    assert(!storage_error);
}
int main(void)
{
    const uint16_t first[] = {REMOTE_MUTE, REMOTE_VOLUME_UP, REMOTE_VOLUME_DOWN};
    const uint16_t second[] = {REMOTE_PLAY_PAUSE, REMOTE_NEXT, REMOTE_PREVIOUS};
    memset(memory, 0xff, sizeof memory);
    storage_init();
    assert(!storage_busy);
    assert(storage_save(first)); finish();
    uint8_t saved[64]; memcpy(saved, memory, sizeof saved);
    for (unsigned cut = 0; cut <= 15; ++cut) {
        memcpy(memory, saved, sizeof memory);
        storage_init();
        assert(storage_save(second));
        for (unsigned i = 0; i < cut; ++i) storage_poll();
        remote_set_mapping(first);
        storage_init(); /* Power loss: all pending state disappears. */
        assert(!memcmp(remote_mapping, cut >= 14 ? second : first, sizeof remote_mapping));
        for (unsigned at = 32; at < sizeof memory; ++at) assert(memory[at] == 0xff);
    }
    memcpy(memory, saved, sizeof memory);
    storage_init();
    assert(storage_save(second)); finish();
    memory[16 + 4] ^= 1; /* Corrupt newest slot. Earlier committed slot survives. */
    storage_init();
    assert(!memcmp(remote_mapping, first, sizeof remote_mapping));
    for (unsigned generation = 0; generation < 300; ++generation) {
        const uint16_t *map = generation & 1 ? first : second;
        assert(storage_save(map)); finish();
        storage_init();
        assert(!memcmp(remote_mapping, map, sizeof remote_mapping));
    }
    puts("EEPROM: every write boundary, CRC fallback, generation wrap, preserved upper 32 bytes");
    return 0;
}
