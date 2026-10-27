/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TINY88_REMOTE_CONFIG_H
#define TINY88_REMOTE_CONFIG_H
/* Active-low buttons: connect each pin to GND through a normally-open switch. */
#define REMOTE_BUTTON0_BIT PC0
#define REMOTE_BUTTON1_BIT PC1
#define REMOTE_BUTTON2_BIT PC2
#define REMOTE_DEFAULT_MAPPING {REMOTE_MUTE, REMOTE_VOLUME_UP, REMOTE_VOLUME_DOWN}
#define REMOTE_DEBOUNCE_MS 20
#define REMOTE_HOLD_MS 40
#define REMOTE_REPEAT_DELAY_MS 500
#define REMOTE_REPEAT_MS 120
#ifndef REMOTE_SIMULATE
#define REMOTE_SIMULATE 0
#endif
#endif
