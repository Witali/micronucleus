/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "keyboard.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void tick(unsigned milliseconds)
{
    while (milliseconds--)
        keyboard_tick_ms();
}

static void check_report(unsigned key)
{
    for (unsigned index = 0; index < KEYBOARD_REPORT_BYTES; ++index)
        assert(keyboard_report[index] == (index == 2 ? key : 0));
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    keyboard_reset();
    assert(keyboard_next_report());
    check_report(0);
    assert(!keyboard_next_report());

    if (!strcmp(argv[1], "sequence")) {
        const unsigned expected[] = {0x0b, 0, 0x08, 0, 0x0f, 0, 0x0f, 0, 0x12, 0};
        unsigned count = 0;
        for (unsigned ms = 0; ms < 10000; ++ms) {
            keyboard_tick_ms();
            if (keyboard_next_report()) {
                assert(count < sizeof expected / sizeof expected[0]);
                check_report(expected[count++]);
            }
        }
        assert(count == sizeof expected / sizeof expected[0]);
        assert(keyboard_done);
        check_report(0);
    } else if (!strcmp(argv[1], "backpressure")) {
        tick(KEYBOARD_START_DELAY_MS - 1);
        assert(!keyboard_next_report());
        tick(1);
        assert(keyboard_next_report());
        check_report(0x0b);
        tick(39);
        assert(!keyboard_next_report());
        /* Simulate a busy endpoint: do not call next_report for 1 second. */
        tick(1000);
        check_report(0x0b);
        assert(keyboard_next_report());
        check_report(0);
        tick(79);
        assert(!keyboard_next_report());
        tick(1);
        assert(keyboard_next_report());
        check_report(0x08);
    } else if (!strcmp(argv[1], "idle")) {
        keyboard_set_idle(255);
        tick(1019);
        assert(!keyboard_next_report());
        tick(1);
        assert(keyboard_next_report());
        check_report(0);
        keyboard_set_idle(1);
        tick(3);
        assert(!keyboard_next_report());
        tick(1);
        assert(keyboard_next_report());
        keyboard_set_idle(0);
        tick(1000);
        assert(!keyboard_next_report());
    } else if (!strcmp(argv[1], "reset")) {
        tick(KEYBOARD_START_DELAY_MS);
        assert(keyboard_next_report());
        check_report(0x0b);
        keyboard_reset();
        assert(keyboard_done);
        assert(keyboard_next_report());
        check_report(0);
        tick(10000);
        assert(!keyboard_next_report());
        /* Further USB resets also must not restart typing. */
        keyboard_reset();
        assert(keyboard_next_report());
        check_report(0);
        tick(10000);
        assert(!keyboard_next_report());
    } else {
        assert(!"Unknown test scenario");
    }
    puts(argv[1]);
    return 0;
}
