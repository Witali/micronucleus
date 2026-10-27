/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "remote.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void tick(unsigned ms, uint8_t pins)
{
    while (ms--)
        remote_tick_ms(pins | remote_simulated_buttons());
}
static unsigned usage(void)
{
    assert(remote_report[0] == REMOTE_INPUT_ID);
    return remote_report[1] | ((unsigned)remote_report[2] << 8);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    remote_reset();
    assert(remote_next_report() && usage() == 0);
    assert(!remote_next_report());
    if (!strcmp(argv[1], "simulation")) {
        unsigned expected[] = {REMOTE_MUTE, 0, REMOTE_VOLUME_UP, 0, REMOTE_VOLUME_DOWN, 0};
        unsigned count = 0;
        for (unsigned ms = 0; ms < 20000; ++ms) {
            tick(1, 0);
            if (remote_next_report()) {
                assert(count < sizeof expected / sizeof expected[0]);
                assert(usage() == expected[count++]);
            }
        }
        assert(count == sizeof expected / sizeof expected[0]);
    } else if (!strcmp(argv[1], "debounce")) {
        for (unsigned i = 0; i < 10; ++i) {
            tick(1, 1); tick(1, 0);
            assert(!remote_next_report());
        }
        tick(19, 1);
        assert(!remote_next_report());
        tick(1, 1);
        assert(remote_next_report() && usage() == REMOTE_MUTE);
        tick(39, 1);
        assert(!remote_next_report());
        tick(1, 1);
        assert(remote_next_report() && usage() == 0);
        tick(2500, 1);
        assert(!remote_next_report()); /* Mute does not repeat while held. */
        tick(20, 0); tick(20, 1);
        assert(remote_next_report() && usage() == REMOTE_MUTE);
    } else if (!strcmp(argv[1], "repeat")) {
        unsigned presses = 0, releases = 0;
        for (unsigned ms = 0; ms < 1100; ++ms) {
            tick(1, 2);
            if (remote_next_report()) {
                if (usage()) { assert(usage() == REMOTE_VOLUME_UP); ++presses; }
                else ++releases;
            }
        }
        tick(20, 0);
        for (unsigned ms = 0; ms < 100; ++ms) {
            tick(1, 0);
            if (remote_next_report()) { assert(!usage()); ++releases; }
        }
        assert(presses >= 4 && presses == releases);
    } else if (!strcmp(argv[1], "backpressure")) {
        tick(20, 2);
        assert(remote_next_report() && usage() == REMOTE_VOLUME_UP);
        tick(1000, 2); /* Endpoint busy; do not consume any next reports. */
        assert(usage() == REMOTE_VOLUME_UP);
        assert(remote_next_report() && usage() == 0);
        assert(remote_next_report() && usage() == REMOTE_VOLUME_UP);
        tick(40, 0);
        assert(remote_next_report() && usage() == 0);
        remote_reset();
        assert(remote_next_report() && usage() == 0);
        assert(!remote_next_report());
    } else if (!strcmp(argv[1], "mapping")) {
        uint16_t map[] = {REMOTE_PLAY_PAUSE, REMOTE_NEXT, 0};
        assert(remote_set_mapping(map));
        assert(remote_next_report() && usage() == 0);
        tick(20, 1);
        assert(remote_next_report() && usage() == REMOTE_PLAY_PAUSE);
        map[1] = 0xffff;
        assert(!remote_set_mapping(map));
        assert(remote_mapping[1] == REMOTE_NEXT);
    } else if (!strcmp(argv[1], "led-idle")) {
        assert(!remote_mute_led());
        remote_set_mute_state(3);
        assert(remote_mute_led());
        tick(2999, 0);
        assert(remote_mute_led());
        tick(1, 0);
        assert(!remote_mute_led());
        remote_set_mute_state(2);
        assert(!remote_mute_led());
        remote_set_idle(255);
        tick(1019, 0); assert(!remote_next_report());
        tick(1, 0); assert(remote_next_report() && !usage());
        remote_set_idle(0);
        tick(1500, 0); assert(!remote_next_report());
    } else {
        assert(!"Unknown test scenario");
    }
    puts(argv[1]);
    return 0;
}
