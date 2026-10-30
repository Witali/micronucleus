#!/usr/bin/env python3
"""Pass34 AVR-emitted-opcode checks. Does NOT constitute physical USB testing."""
import sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from check_build import build
from tests.avr_exec import AVRExec
import tests.avr_exec as _avr_exec
from functools import lru_cache
from host.profiles import BOOT_AT,BCD_DEVICE,NO_LED_CODE_BYTES
_avr_exec.decode=lru_cache(maxsize=48)(_avr_exec.decode)

MODES=[('NONE',BOOT_AT,BCD_DEVICE,NO_LED_CODE_BYTES),
       ('ACTIVE_HIGH',BOOT_AT,0xFFFF,None),('ACTIVE_LOW',BOOT_AT,0xFFFF,None)]

def art(led='NONE',boot=0x1c00,source='source'):
    return build(f'{source}/micronucleus_t88_compact.S',mode=led,boot=boot)

def test_profiles():
    for led,boot,bcd,size in MODES:
        a=art(led,boot)
        if size is not None:
            assert len(a['body'])==size and boot+size<=8192,(led,len(a['body']))
        assert int.from_bytes(a['body'][32:34],'little')==bcd
        assert 'R_AVR_' not in subprocess.check_output(['llvm-objdump','-r',str(a['obj'])],text=True)
        assert '*UND*' not in subprocess.check_output(['llvm-objdump','-t',str(a['obj'])],text=True)
        at=a['symbols']['app_jump'];w=int.from_bytes(a['body'][at-boot:at-boot+2],'little')
        off=w&0xfff
        if off&0x800:off-=4096
        assert ((at//2+1+off)&0xfff)*2==boot-4
        if size is not None:
            print('PROFILE',led,'code',size,'boot',hex(boot),'postscript',hex(boot-4))


def test_flash():
    checks=0
    for led,boot,_,_ in MODES:
        a=art(led,boot)
        for page in range(0,8192,64):
            for command in (1,2):
                x=AVRExec(a);x.r[25]=command;x.r[29]=1
                x.r[14:16]=[page&255,page>>8]
                assert x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'],limit=120)=='stop'
                assert x.r[4:6]==[page&255,page>>8] and x.r[3]==command+1
                assert x.spms[-1][0]==17
                x.spms.clear();x.ram[15]=0x5a
                assert x.run('bootloader_dispatch_command',stop=['bootloader_clear_command'],limit=120)=='stop'
                actual=[row for row in x.spms if row[0]==3]
                assert len(actual)==(command==2 and page<boot),(led,page,command,actual)
                checks+=1
            for offset in range(0,64,4):
                x=AVRExec(a);x.r[29]=1;x.r[3]=64
                address=page+offset
                x.r[4:6]=[address&255,address>>8]
                x.r[12:16]=[0x37,0x91,0x25,0xa6];x.r[30:32]=[0,1]
                assert x.run('flash_buffer_ack_write4',stop=['usb_handler_packet_done'],limit=120)=='stop'
                assert x.spms==[(1,address,0x9137),(1,address+2,0xa625)]
                assert x.r[4]|x.r[5]<<8==address+4
                assert x.r[1]==0 and x.r[30:32]==[0,1]
                assert x.r[3]==(5 if offset==60 else 0)
                if offset==60:
                    x.ram[15]=0x5a
                    assert x.run('bootloader_dispatch_command',stop=['bootloader_clear_command'],limit=120)=='stop'
                    writes=[row for row in x.spms if row[0]==5]
                    assert len(writes)==(page<boot),(led,page,writes)
                    if writes:assert writes[0][1]==page
                checks+=1
            for command in (0,5,6,255):
                x=AVRExec(a);x.r[29]=1;x.r[25]=command
                assert x.run('bootloader_check_set_flash_address',stop=['usb_reply_stall'],limit=120)=='stop'
                assert not x.spms
                checks+=1
        for address in (0,2,14,254,256,boot-8,boot-2,boot,8184):
            x=AVRExec(a);x.r[25]=0xb0;x.r[29]=1
            x.r[4:6]=[address&255,address>>8]
            x.r[14:16]=[0x55,0x19]  # Raw wIndex must not replace SELECT's cursor.
            assert x.run('bootloader_handle_vendor_request',stop=['usb_reply_limit_length'],limit=60)=='stop'
            assert x.r[14:16]==[address&255,address>>8] and x.r[24]==8
            assert x.r[4:6]==[address&255,address>>8]
            checks+=1
    print('PASS emitted SELECT/WRITE4/cursor/auto-page and boot protection:',checks)


def test_ack():
    # CPU executor reproduces actual compiled instruction paths for ACK control.
    from tests34.test_pass33_ack import CPU
    cases=0
    for led,boot,_,_ in MODES:
        a=art(led,boot)
        for marker in (0,1,4,8,12,0xff):
            for plen in (0,1,2,3,11,12):
                for new in (0,0x14,0x30):
                    m=CPU(a);m.r[23]=plen;m.r[2]=marker
                    # This direct entry follows framing's recovery-J capture.
                    m.r[21]=2
                    m.mem.update({0x100+15:12,0x100+12:0x08,0x100+19:new})
                    end=m.run('usb_rx_check_ack',('usb_handler_packet_done','usb_rx_ignore_packet'))
                    good=bool(marker) and plen==1
                    assert end==('usb_handler_packet_done' if good else 'usb_rx_ignore_packet')
                    assert m.r[2]==(0 if good else marker)
                    assert m.mem[0x100+15]==(0x5a if good else 12)
                    assert m.mem[0x100+12]==(new if good else 0x08)
                    cases+=1
        for n in (4,8,12):
            m=CPU(a);m.r[19]=n
            m.mem[0x100+15]=n
            m.mem[0x100+12]=8
            m.mem[0x100+19]=0x14
            for i in range(1,14):
                if i!=12:m.mem[0x100+i]=(i*13)&255
            original=dict(m.mem)
            for _ in range(6):
                m.r[19]=m.mem[0x100+15]  # RX already sampled TX_LENGTH.
                assert m.run('usb_rx_handle_in',('usb_tx_acquire_bus',))=='usb_tx_acquire_bus'
                assert m.mem==original and m.r[2]==n
                cases+=1
            m.r[23]=1
            m.r[21]=2  # Captured recovery J at the post-framing direct entry.
            m.run('usb_rx_check_ack',('usb_handler_packet_done','usb_rx_ignore_packet'))
            assert m.r[2]==0 and m.mem[0x100+15]==0x5a
        for old in (0,1,3,19,62):
            m=CPU(a);m.r[24]=1;m.r[2]=12
            m.mem.update({0x100+15:12,0x100+0:9,0x100+12:old,0x100+19:99,0x100+21:1})
            assert m.run('usb_poll_check_reset_duration',('usb_poll_check_packet_pending',))=='usb_poll_check_packet_pending'
            assert m.r[2]==0 and m.mem[0x100+15]==0x5a and m.mem[0x100+0]==0xff
            assert m.mem[0x100+12]==0 and m.mem[0x100+21]==0
            assert m.mem[0x100+19]==0
            assert m.mem[0x100+20]==0
            assert m.r[3]==0 and m.r[5]==0xff
            cases+=1
    print('PASS ACK packet/retry/bus-reset opcode cases:',cases)

if __name__=='__main__':
    test_profiles()
    test_flash()
    test_ack()
