/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "control.h"
#include "storage.h"
#include <string.h>
uint8_t remote_control_report[REMOTE_FEATURE_BYTES];
static uint8_t write_id, received, expected;

void remote_control_abort(void) { write_id = 0; }

void remote_control_read(void)
{
    remote_control_report[0] = REMOTE_MAPPING_ID;
    remote_control_report[1] = 3 | (storage_busy ? 0x10 : 0) |
                              (storage_error ? 0x20 : 0) | (storage_legacy ? 0x40 : 0);
    remote_control_report[2] = remote_active_preset;
    remote_export_config(remote_control_report + 3);
}

uint8_t remote_control_begin(uint8_t id, uint16_t length)
{
    write_id = 0;
    if (!(((id == REMOTE_LED_ID || id == REMOTE_TEST_ID || id == REMOTE_PRESET_ID) && length == 2) ||
          (id == REMOTE_MAPPING_ID && length == REMOTE_FEATURE_BYTES && !storage_busy))) return 0;
    write_id = id; received = 0; expected = length;
    return 1;
}

uint8_t remote_control_write(const uint8_t *data, uint8_t length)
{
    if (!write_id || !length || received + length > expected) { write_id = 0; return 0xff; }
    memcpy(remote_control_report + received, data, length);
    received += length;
    if (received < expected) return 0;
    uint8_t id = write_id;
    write_id = 0;
    if (remote_control_report[0] != id) return 0xff;
    uint8_t value = remote_control_report[1];
    if (id == REMOTE_LED_ID && value <= 3) { remote_set_mute_state(value); return 1; }
    if (id == REMOTE_TEST_ID) { remote_inject_buttons(value); return 1; }
    if (id == REMOTE_PRESET_ID) return remote_select_preset(value) ? 1 : 0xff;
    if (id == REMOTE_MAPPING_ID && (value == 3 || value == 0x83) && !storage_busy) {
        if (!remote_configure(remote_control_report + 3)) return 0xff;
        return (value & 0x80) ? (storage_save() ? 1 : 0xff) : 1;
    }
    return 0xff;
}
