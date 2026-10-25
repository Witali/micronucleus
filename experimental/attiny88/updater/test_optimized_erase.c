/* Execute the candidate erase loop with simavr's independent CPU/native SPM.
 * The ATmega88 substrate is restricted to tiny88 RAM and 64-byte NORWW pages.
 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sim_avr.h"
#include "sim_core.h"
#include "sim_io.h"
#include "avr_flash.h"

static unsigned run_command(avr_t *avr,uint32_t entry,uint32_t stop,uint32_t boot,uint8_t command)
{
    avr->pc=entry;avr->data[3]=command;
    unsigned erased=0;
    for(unsigned step=0;step<100000;step++) {
        if(avr->pc==stop)return erased;
        uint16_t opcode=avr->flash[avr->pc]|avr->flash[avr->pc+1]<<8;
        uint8_t flags[8];memcpy(flags,avr->sreg,sizeof(flags));
        if(opcode==0x95e8) {
            assert(command==2&&avr->data[0x57]==3);
            uint16_t z=avr->data[30]|avr->data[31]<<8;
            assert((uint32_t)z==boot-64*(++erased));assert((z&63)==0);
        }
        avr->pc=avr_run_one(avr);
        if(opcode==0x95e8)assert(memcmp(flags,avr->sreg,sizeof(flags))==0);
        assert(avr->state!=cpu_Crashed&&avr->state!=cpu_Done);
    }
    assert(!"Command did not reach the setup checkpoint");return 0;
}

int main(int argc,char **argv)
{
    assert(argc==5);
    uint32_t boot=strtoul(argv[2],NULL,0),entry=strtoul(argv[3],NULL,0),stop=strtoul(argv[4],NULL,0);
    avr_t *avr=avr_make_mcu_by_name("atmega88");assert(avr);
    avr->ramend=0x2ff;avr->e2end=63;avr->frequency=16000000;avr_init(avr);
    avr->fuse[2]=0xfe;avr->log=0;avr->state=cpu_Running;
    avr_flash_t *flash=NULL;
    for(avr_io_t *io=avr->io_port;io;io=io->next)
        if(!strcmp(io->kind,"flash"))flash=(avr_flash_t *)io;
    assert(flash);flash->spm_pagesize=64;flash->flags=0;
    memset(avr->flash,255,8192);memset(avr->flash,0xa5,boot);
    FILE *file=fopen(argv[1],"rb");assert(file);
    size_t length=fread(avr->flash+boot,1,8192-boot,file);assert(length>0);fclose(file);
    uint8_t before[8192];memcpy(before,avr->flash,8192);
    avr->data[1]=0;avr->data[0x5d]=255;avr->data[0x5e]=2;
    unsigned pages=run_command(avr,entry,stop,boot,2);assert(pages==boot/64);
    for(uint32_t address=0;address<boot;address++)assert(avr->flash[address]==255);
    assert(!avr->data[3]&&!avr->data[4]&&!avr->data[5]);
    assert(memcmp(avr->flash+boot,before+boot,8192-boot)==0);
    const uint16_t invalid[]={0,(uint16_t)(boot+2),65535};
    for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++) {
        avr->data[4]=invalid[i]&255;avr->data[5]=invalid[i]>>8;
        assert(run_command(avr,entry,stop,boot,64)==0);
    }
    printf("PASS: simavr native SPM: %u descending pages erased, SREG preserved, loader intact, invalid page writes rejected\n",pages);
    avr_terminate(avr);return 0;
}
