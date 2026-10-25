/* Independent opcode/SPM execution using simavr. GPL-3.0-or-later test harness.
 * The atmega88 CPU is restricted to tiny88 RAM/EEPROM and 64-byte NORWW Flash.
 * No complete native ATtiny88 peripheral/electrical model is claimed.
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

int main(int argc, char **argv)
{
    assert(argc==6||argc==7);
    const char *mode=argc==7?argv[6]:"normal";
    uint32_t boot=strtoul(argv[5],NULL,0),postscript=boot-64;
    assert(boot>=0x1800&&boot<=0x1b00&&(boot&63)==0);
    uint32_t complete=strtoul(argv[2],NULL,0), abort_pc=strtoul(argv[3],NULL,0);
    avr_t *avr=avr_make_mcu_by_name("atmega88");assert(avr);
    avr->ramend=0x2ff;avr->e2end=63;avr->frequency=16000000;avr->fuse[2]=0xfe;
    avr_init(avr);
    avr->fuse[2]=!strcmp(mode,"disabled")?0xff:0xfe;avr->log=0;
    avr_flash_t *flash=NULL;
    for(avr_io_t *io=avr->io_port;io;io=io->next)
        if(!strcmp(io->kind,"flash"))flash=(avr_flash_t *)io;
    assert(flash);flash->spm_pagesize=64;flash->flags=0;
    for(int i=0;i<32;i++){flash->tmppage[i]=0xffff;flash->tmppage_used[i]=0;}
    FILE *file=fopen(argv[1],"rb");assert(file);assert(fread(avr->flash,1,8192,file)==8192);fclose(file);
    uint8_t before[8192];memcpy(before,avr->flash,8192);
    avr->pc=0x80;avr->state=cpu_Running;
    unsigned erased=0,written=0,clear_count=0;
    for(unsigned steps=0;steps<2000000;steps++) {
        if(avr->pc==complete)break;
        if(avr->pc==abort_pc){fprintf(stderr,"Updater aborted: %u erased:%u written:%u reset:%04x\n",avr->data[24],erased,written,avr->flash[0]|avr->flash[1]<<8);return 2;}
        uint16_t opcode=avr->flash[avr->pc]|avr->flash[avr->pc+1]<<8;
        uint8_t previous_command=0;
        uint16_t previous_z=0;
        if(opcode==0x95e8) {
            uint16_t z=avr->data[30]|avr->data[31]<<8;
            uint8_t command=avr->data[0x57];
            if(command==17) {
                /* simavr lacks the tiny88 CTPB command; model only this gap. */
                for(int i=0;i<32;i++){flash->tmppage[i]=0xffff;flash->tmppage_used[i]=0;}
                avr->data[0x57]=0;avr->pc+=2;avr->cycle+=4;clear_count++;continue;
            }
            assert(command==1||command==3||command==5);
            previous_command=command;previous_z=z;
            if(command==3||command==5) {
                assert(z==0||z==postscript||(z>=boot&&z<8192));
                assert((z&63)==0);
                if(command==3)erased++;else written++;
            }
        }
        avr->pc=avr_run_one(avr);
        if(previous_command==5&&previous_z==boot&&!strcmp(mode,"readback"))avr->flash[boot]^=1;
        if(avr->state==cpu_Crashed||avr->state==cpu_Done){fprintf(stderr,"simavr stopped\n");return 3;}
    }
    assert(avr->pc==complete);
    assert((avr->flash[0]|avr->flash[1]<<8)==(uint16_t)(0xc000|((boot/2-1)&0xfff)));
    assert(erased==(8192-boot)/64+3&&written==erased&&clear_count==erased);
    for(uint32_t i=0x80;i<strtoul(argv[4],NULL,0);i++)assert(avr->flash[i]==before[i]);
    for(uint32_t i=postscript;i<boot;i++)assert(avr->flash[i]==255);
    file=fopen("simavr-result.bin","wb");assert(file);assert(fwrite(avr->flash,1,8192,file)==8192);fclose(file);
    printf("PASS: simavr independent CPU and native SPM: %u erased/written pages, final RESET, intact updater, cleared postscript\n",erased);
    avr_terminate(avr);
    return 0;
}
