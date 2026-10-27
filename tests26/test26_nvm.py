"""Execute modified address/write/erase/EEPROM code from the assembled ELF."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_build import build
from tests.avr_exec import AVRExec
SRC=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass26.S'


def test_setaddr(art):
    for block in range(0,(art['boot']//4),17):
        x=AVRExec(art);x.r[25]=1;x.ram.update({27:block&255,28:block>>8});assert x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'])=='stop'
        pointer=x.r[4]|x.r[5]<<8
        assert pointer==block*4,(block,pointer)
        assert x.spms==[(0x11,0,0)] or (len(x.spms)==1 and x.spms[0][0]==0x11),x.spms
    for block in range(16):
        field=0x8000|block;x=AVRExec(art);x.r[25]=1;x.ram.update({27:field&255,28:field>>8});x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'])
        assert (x.r[4],x.r[5])==(block*4,0x80),(block,x.r[4:6]);assert x.spms==[]
    for field in (0x8010,0x8fff,0xffff):
        x=AVRExec(art);x.r[25]=1;x.ram.update({27:field&255,28:field>>8});x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'])
        assert x.r[4:6]==[0,0] and not x.spms
    for pending,eepe in ((1,False),(0,True)):
        x=AVRExec(art);x.r[25]=1;x.r[8]=pending;x.io[0x1f]=2 if eepe else 0
        x.ram.update({27:0x00,28:0x80});x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'])
        assert x.r[4:6]==[0,0] and not x.spms


def test_erase_and_commit(art):
    for page in list(range(0,art['boot'],64))+[art['boot'],art['boot']+64,0xffc0]:
        for op,entry in ((3,'flash_erase_selected_page'),(5,'flash_commit_buffered_page')):
            x=AVRExec(art);ptr=page if op==3 else (page+64)&0xffff
            x.r[4]=ptr&255;x.r[5]=ptr>>8
            x.r[3]=op  # The pending command now carries the actual SPM opcode.
            x.run('bootloader_dispatch_command',stop=['bootloader_clear_command'])
            if page<art['boot']:
                assert x.spms and x.spms[0][:2]==(op,page),(hex(page),op,x.spms)
            else:
                assert not x.spms,(hex(page),op,x.spms)


def test_flash_write_data(art):
    for page in (0,0x40,art['boot']-64):
        x=AVRExec(art);x.r[4]=page&255;x.r[5]=page>>8;x.r[25]=3;x.r[29]=1
        data=[0x73,0xab,0x42,0x19]
        x.ram.update(dict(zip((25,26,27,28),data)))
        x.run('bootloader_check_write4',stop=['usb_reply_empty'])
        assert x.spms==[(1,page,0xab73),(1,page+2,0x1942)],(hex(page),x.spms)
        assert x.r[4]|(x.r[5]<<8)==page+4
        # Most importantly, the device no longer replaces user-provided RESET.
        if page==0:assert x.spms[0][2]==0xab73


def test_eeprom_queue(art):
    total=0
    for block in range(16):
        for data in ((0,1,2,3),(0xff,0x81,0x44,0x55)):
            x=AVRExec(art);x.r[4]=block*4;x.r[5]=0x80
            x.ram.update(dict(zip((25,26,27,28),data)))
            x.run('ee_write',stop=['usb_reply_empty'])
            assert x.r[8]==4 and x.r[4]==block*4 and x.r[10:14]==list(data),(block,data,x.r[8:14])
            assert x.r[4]==block*4
            for j in range(4):
                x.io[0x1f]=2
                copy=(x.r[:],len(x.io_events))
                x.run('ee_write_step')
                assert x.r==copy[0] and len(x.io_events)==copy[1]
                x.io[0x1f]=0
                x.run('ee_write_step')
                assert x.r[8]==3-j and x.r[4]==block*4+j+1
                assert x.io_events[-4:]==[('out',0x21,block*4+j),('out',0x20,data[j]),('sbi',0x1f,2),('sbi',0x1f,1)]
            total+=1
    x=AVRExec(art);x.r[4]=64;x.r[5]=0x80
    x.ram.update({25:1,26:2,27:3,28:4});x.run('ee_write',stop=['usb_reply_empty'])
    assert x.r[8]==0 and x.r[10:14]==[0]*4
    print('  EEPROM blocks validated:',total)


def test():
    for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        boot=0x1b40 if mode=='NONE' else 0x1b00
        art=build(SRC,mode=mode,boot=boot)
        test_setaddr(art)
        test_erase_and_commit(art)
        test_flash_write_data(art)
        test_eeprom_queue(art)
        print('PASS',mode,'NVM opcode simulation')

if __name__=='__main__': test()
