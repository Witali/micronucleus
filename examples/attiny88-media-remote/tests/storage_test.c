/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "storage.h"
#include "control.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t memory[64];
uint8_t storage_hw_ready(void){return 1;}
uint8_t storage_hw_read(uint8_t at){assert(at<56);return memory[at];}
void storage_hw_write(uint8_t at,uint8_t value){assert(at<56);memory[at]=value;}
static void finish(void){unsigned n=0;while(storage_busy){storage_poll();assert(++n<=58);}assert(!storage_error);}
int main(void)
{
    memset(memory,0xff,sizeof memory);storage_init();remote_reset();
    uint8_t first[50],second[50];remote_export_config(first);
    remote_preset_count=3;remote_profiles[1][4]=REMOTE_KEY(6,1);remote_profiles[2][6]=REMOTE_MEDIA(REMOTE_BROWSER);
    remote_export_config(second);assert(storage_save());finish();
    uint8_t saved[64],replacement[50];memcpy(saved,memory,64);
    memcpy(replacement,first,50);replacement[0]=2;replacement[2]=0x19;replacement[3]=0x11;
    for(unsigned cut=0;cut<=58;++cut){
        memcpy(memory,saved,64);storage_init();assert(remote_configure(replacement));assert(storage_save());
        for(unsigned n=0;n<cut;++n)storage_poll();
        storage_init();uint8_t loaded[50];remote_export_config(loaded);
        /* An interrupted single-record save falls back to valid defaults. */
        assert(!memcmp(loaded,cut>=57?replacement:(cut==0?second:first),50));
        for(unsigned at=56;at<64;++at)assert(memory[at]==0xff);
    }
    memcpy(memory,saved,64);memory[12]^=1;storage_init();uint8_t loaded[50];remote_export_config(loaded);assert(!memcmp(first,loaded,50));
    memset(memory,0xff,64);
    const uint8_t legacy[13]={0x4d, 0x52, 0x01, 0x09, 0xcd, 0x00, 0x00, 0x00, 0xe2, 0x00, 0xe4, 0x3b, 0xa5};
    memcpy(memory,legacy,13);storage_init();
    assert(storage_legacy && remote_preset_count==1);
    assert(remote_profiles[0][0]==REMOTE_MEDIA(REMOTE_PLAY_PAUSE) && remote_profiles[0][1]==0);
    assert(!memcmp(memory,legacy,13)); /* Import must not write the EEPROM. */
    assert(storage_save());finish();storage_init();
    assert(!storage_legacy && remote_profiles[0][0]==REMOTE_MEDIA(REMOTE_PLAY_PAUSE));
    memset(memory,0xff,64);storage_init();remote_control_abort();
    uint8_t report[53]={3,0x83,0};memcpy(report+3,second,50);
    assert(remote_control_begin(3,53));
    for(unsigned at=0;at<48;at+=8){assert(remote_control_write(report+at,8)==0);assert(!storage_busy && remote_preset_count==1);}
    assert(remote_control_write(report+48,5)==1 && storage_busy);finish();
    remote_control_read();assert(remote_control_report[1]==3 && !memcmp(remote_control_report+3,second,50));
    assert(remote_control_begin(3,53));assert(remote_control_write(report,8)==0);remote_control_abort();
    assert(remote_control_write(report+8,8)==0xff);
    assert(remote_control_begin(3,53));assert(remote_control_write(report,54)==0xff);
    uint8_t led[]={2,3};assert(remote_control_begin(2,2));assert(remote_control_write(led,1)==0);assert(remote_control_write(led+1,1)==1 && remote_mute_led());
    uint8_t layer[]={6,2};assert(remote_control_begin(6,2));assert(remote_control_write(layer,2)==1 && remote_active_preset==2);
    puts("EEPROM: interruption/CRC/defaults; control: seven-packet save, abort, bounds, outputs");
    return 0;
}
