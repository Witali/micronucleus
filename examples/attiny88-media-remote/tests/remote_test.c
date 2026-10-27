/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "remote.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void tick(unsigned ms, uint8_t pins)
{
    while (ms--) remote_tick_ms(pins | remote_simulated_buttons() | remote_injected_buttons());
}
static unsigned usage(void) { return remote_report[1] | ((unsigned)remote_report[2] << 8); }
static void empty_initial(void)
{
    assert(remote_next_report() && remote_report[0] == 1 && !usage());
    assert(remote_next_report() && remote_report[0] == 4);
    for (unsigned i=1; i<8; ++i) assert(remote_report[i] == 0);
    assert(!remote_next_report());
}
int main(int argc, char **argv)
{
    assert(argc==2);
    remote_default_config(); remote_reset(); empty_initial();
    if (!strcmp(argv[1],"simulation")) {
        unsigned expected[]={REMOTE_MUTE,0,REMOTE_VOLUME_UP,0,REMOTE_VOLUME_DOWN,0}, count=0;
        for(unsigned ms=0;ms<20000;++ms) {
            tick(1,0);
            if(remote_next_report()) { assert(remote_report[0]==1 && count<6 && usage()==expected[count++]); }
        }
        assert(count==6);
    } else if (!strcmp(argv[1],"consumer")) {
        for(unsigned i=0;i<10;++i) { tick(1,1);tick(1,0);assert(!remote_next_report()); }
        tick(19,1);assert(!remote_next_report());tick(1,1);
        assert(remote_next_report() && remote_report[0]==1 && usage()==REMOTE_MUTE);
        tick(40,1);assert(remote_next_report() && !usage());
        tick(2000,1);assert(!remote_next_report());
        tick(20,0);
        unsigned presses=0,releases=0;
        for(unsigned ms=0;ms<1100;++ms) {
            tick(1,2);
            if(remote_next_report()) { assert(remote_report[0]==1);if(usage()){assert(usage()==REMOTE_VOLUME_UP);++presses;}else ++releases; }
        }
        assert(presses>=4);
        tick(100,0);while(remote_next_report()) { assert(!usage());++releases; }
        assert(presses==releases);
    } else if (!strcmp(argv[1],"keyboard")) {
        remote_profiles[0][0]=REMOTE_KEY(6,1); /* Ctrl+C */
        remote_profiles[0][1]=REMOTE_KEY(25,1); /* Ctrl+V */
        tick(20,1);assert(remote_next_report() && remote_report_length==8 && remote_report[1]==1 && remote_report[2]==6);
        tick(1000,1);assert(!remote_next_report()); /* Host handles keyboard repeat. */
        tick(20,3);assert(remote_next_report() && remote_report[1]==1 && remote_report[2]==6 && remote_report[3]==25);
        tick(20,2);assert(remote_next_report() && remote_report[1]==1 && remote_report[2]==25);
        tick(20,0);assert(remote_next_report() && remote_report[1]==0 && remote_report[2]==0);
        remote_profiles[0][0]=REMOTE_KEY(4,0);remote_profiles[0][1]=REMOTE_KEY(4,0);
        tick(20,3);assert(remote_next_report() && remote_report[2]==4 && remote_report[3]==0);
        tick(20,2);assert(remote_next_report() && remote_report[2]==4);
        tick(20,0);assert(remote_next_report() && remote_report[2]==0);
    } else if (!strcmp(argv[1],"layers")) {
        remote_preset_count=3;
        remote_profiles[0][0]=REMOTE_KEY(4,1);remote_profiles[1][0]=REMOTE_KEY(5,2);
        tick(20,1);assert(remote_next_report() && remote_report[2]==4);
        tick(20,129);assert(remote_active_preset==1);empty_initial();
        tick(1000,129);assert(remote_active_preset==1 && !remote_next_report());
        tick(20,1);assert(!remote_next_report()); /* Held old key remains blocked. */
        tick(20,0);while(remote_next_report()) {}
        tick(20,1);assert(remote_next_report() && remote_report[2]==5 && remote_report[1]==2);
        tick(20,0);while(remote_next_report()) {}
        tick(20,128);assert(remote_active_preset==2);empty_initial();
        tick(20,0);tick(20,128);assert(remote_active_preset==0);empty_initial();
        assert(!remote_select_preset(3));
    } else if (!strcmp(argv[1],"backpressure")) {
        remote_cycle_button=255;
        for(unsigned i=0;i<8;++i) remote_profiles[0][i]=REMOTE_KEY(4+i,0);
        tick(20,1);tick(20,0); /* Short tap queued despite endpoint backpressure. */
        assert(remote_next_report() && remote_report[2]==4);
        assert(remote_next_report() && remote_report[2]==0);
        for(unsigned i=0;i<30;++i) {tick(20,1);tick(20,0);}
        unsigned reports=0;while(remote_next_report()) {assert(++reports<=8);}
        for(unsigned i=1;i<8;++i)assert(remote_keyboard_report[i]==0);
        tick(20,255);assert(remote_next_report());for(unsigned i=2;i<8;++i)assert(remote_report[i]==1);
        tick(20,63);assert(remote_next_report());for(unsigned i=2;i<8;++i)assert(remote_report[i]==i+2);
    } else if (!strcmp(argv[1],"validation")) {
        uint8_t config[50],bad[50];remote_export_config(config);
        memcpy(bad,config,50);bad[0]=4;assert(!remote_configure(bad));
        memcpy(bad,config,50);bad[1]=8;assert(!remote_configure(bad));
        memcpy(bad,config,50);bad[49]=0xff;assert(!remote_configure(bad));
        remote_export_config(bad);assert(!memcmp(config,bad,50));
        assert(remote_binding_valid(REMOTE_MEDIA(REMOTE_BROWSER)));
        assert(!remote_binding_valid(0x1000) && !remote_binding_valid(0x3000));
        remote_set_mute_state(3);tick(2999,0);assert(remote_mute_led());tick(1,0);assert(!remote_mute_led());
        remote_set_idle(4,255);tick(1020,0);assert(remote_next_report() && remote_report[0]==4);
        remote_set_idle(0,0);assert(!remote_next_report());
        remote_profiles[0][0]=REMOTE_KEY(4,0);remote_inject_buttons(1);
        tick(20,0);assert(remote_next_report() && remote_report[2]==4);
        tick(300,0);assert(remote_next_report() && remote_report[2]==0);
    } else assert(!"Unknown scenario");
    puts(argv[1]);return 0;
}
