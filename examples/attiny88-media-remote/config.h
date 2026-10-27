/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TINY88_REMOTE_CONFIG_H
#define TINY88_REMOTE_CONFIG_H
/* Active-low buttons: connect each pin to GND through a normally-open switch. */
#define REMOTE_PORTC_MASK 0x3f /* Buttons 1..6: PC0..PC5. */
#define REMOTE_PORTB_MASK 0x03 /* Buttons 7..8: PB0..PB1. */
#define REMOTE_DEFAULT_MAPPING { REMOTE_MEDIA(REMOTE_MUTE), REMOTE_MEDIA(REMOTE_VOLUME_UP), \
                                 REMOTE_MEDIA(REMOTE_VOLUME_DOWN), 0, 0, 0, 0, 0 }
#define REMOTE_DEBOUNCE_MS 20
#define REMOTE_HOLD_MS 40
#define REMOTE_REPEAT_DELAY_MS 500
#define REMOTE_REPEAT_MS 120
#ifndef REMOTE_SIMULATE
#define REMOTE_SIMULATE 0
#endif
#endif
