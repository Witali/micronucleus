#!/usr/bin/env python3
"""Pass34 AVR-emitted-opcode checks. Does NOT constitute physical USB testing."""
import sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from check_build import build
from tests.avr_exec import AVRExec
import tests.avr_exec as _avr_exec
from functools import lru_cache
_avr_exec.decode=lru_cache(maxsize=48)(_avr_exec.decode)

MODES=[('NONE',0x1BC0,0x0450,1036),('ACTIVE_HIGH',0x1BC0,0x0451,1056),('ACTIVE_LOW',0x1BC0,0x0452,1054)]

def art(led='NONE',boot=0x1c00,source='source'):
    return build(f'{source}/micronucleus_t88_compact.S',mode=led,boot=boot)

def test_profiles():
    for led,boot,bcd,size in MODES:
        a=art(led,boot)
        assert len(a['body'])==size and boot+size<=8192,(led,len(a['body']))
        assert int.from_bytes(a['body'][32:34],'little')==bcd
        assert 'R_AVR_' not in subprocess.check_output(['llvm-objdump','-r',str(a['obj'])],text=True)
        assert '*UND*' not in subprocess.check_output(['llvm-objdump','-t',str(a['obj'])],text=True)
        at=a['symbols']['app_jump'];w=int.from_bytes(a['body'][at-boot:at-boot+2],'little')
        off=w&0xfff
        if off&0x800:off-=4096
        assert ((at//2+1+off)&0xfff)*2==boot-4
        print('PROFILE',led,'code',size,'boot',hex(boot),'postscript',hex(boot-4))


def test_flash():
    checks=0
    for led,boot,_,_ in MODES:
        a=art(led,boot)
        for page in range(0,8192,64):
            for cmd in (1,2):
                x=AVRExec(a);x.r[25]=cmd;x.r[29]=1
                x.ram.update({27:page&255,28:page>>8})
                assert x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'],limit=120)=='stop'
                assert x.r[4:6]==[page&255,page>>8]
                assert x.r[3]==cmd+1
                assert x.spms and x.spms[-1][0]==0x11
                x.spms.clear()
                x.ram[15]=0x5a  # No unacknowledged outgoing DATA during standalone SPM test.
                assert x.run('bootloader_dispatch_command',stop=['bootloader_clear_command'],limit=100)=='stop'
                erases=[k for k in x.spms if k[0]==3]
                assert len(erases)==(1 if cmd==2 and page<boot else 0),(led,page,cmd,erases)
                checks+=1
        for page in range(0,8192,64):
            for idx in (0,2,16,30,62):
                address=page+idx
                x=AVRExec(a);x.r[29]=1;x.r[25]=3
                x.r[4:6]=[page&255,page>>8]
                x.ram.update({25:0x37,26:0x91,27:address&255,28:address>>8})
                assert x.run('bootloader_check_write4',stop=['usb_reply_empty'],limit=120)=='stop'
                assert x.r[1]==0 and x.r[4:6]==[page&255,page>>8]
                loads=[k for k in x.spms if k[0]==1]
                assert len(loads)==1 and loads[0][1:]==(address,0x9137),(led,page,idx,x.spms)
                assert x.r[3]==0  # WRITE2 does not auto-commit.
                checks+=1
            for cmd in (4,5,6,0):
                x=AVRExec(a);x.r[29]=1;x.r[25]=cmd
                assert x.run('bootloader_check_write4' if cmd else 'bootloader_check_set_flash_address',stop=['usb_reply_empty'],limit=100)=='stop'
                assert x.r[3]==(cmd if cmd in (4,5) else 0),(led,page,cmd,x.r[3])
                checks+=1
            for cmd in (3,5):
                x=AVRExec(a);x.r[3]=cmd;x.r[4:6]=[page&255,page>>8];x.r[29]=1
                x.ram[15]=0x5a  # No pending IN DATA; ACK-state gate permits SPM.
                assert x.run('bootloader_dispatch_command',stop=['bootloader_clear_command'],limit=120)=='stop'
                real=[k for k in x.spms if k[0] in (3,5)]
                assert len(real)==(1 if page<boot else 0),(led,page,cmd,real)
                if real:assert real[0][0]==cmd and real[0][1]==page
                checks+=1
        for adr in (0,2,14,254,256,boot-8,boot-2,boot,8184):
            x=AVRExec(a);x.r[25]=0xb0;x.r[29]=1;x.r[4:6]=[0x55,0x19]
            x.ram.update({27:adr&255,28:adr>>8})
            assert x.run('bootloader_handle_vendor_request',stop=['usb_reply_set_pointer'],limit=60)=='stop'
            assert x.r[18:20]==[adr&255,adr>>8] and x.r[24]==8
            assert x.r[4:6]==[0x55,0x19], 'READ8 must not move the write page selector'
            checks+=1
    print('PASS emitted AVR NVM opcode and boot-region protection checks:',checks)


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
                    m.mem.update({0x100+15:12,0x100+12:0x08,0x100+19:new})
                    end=m.run('usb_rx_check_ack',('usb_handler_packet_done','usb_rx_ignore_packet'))
                    good=bool(marker) and plen==1
                    assert end==('usb_handler_packet_done' if good else 'usb_rx_ignore_packet')
                    assert m.r[2]==(0 if good else marker)
                    assert m.mem[0x100+15]==(0x5a if good else 12)
                    assert m.mem[0x100+12]==(new if good else 0x08)
                    cases+=1
        for n in (4,8,12):
            m=CPU(a);m.r[19]=0
            m.mem[0x100+15]=n
            m.mem[0x100+12]=8
            m.mem[0x100+19]=0x14
            for i in range(1,14):
                if i!=12:m.mem[0x100+i]=(i*13)&255
            original=dict(m.mem)
            for _ in range(6):
                m.r[19]=0
                assert m.run('usb_rx_handle_in',('usb_tx_acquire_bus',))=='usb_tx_acquire_bus'
                assert m.mem==original and m.r[2]==n
                cases+=1
            m.r[23]=1
            m.run('usb_rx_check_ack',('usb_handler_packet_done','usb_rx_ignore_packet'))
            assert m.r[2]==0 and m.mem[0x100+15]==0x5a
        for old in (0,1,3,19,62):
            m=CPU(a);m.r[24]=1;m.r[2]=12
            m.mem.update({0x100+15:12,0x100+0:9,0x100+12:old,0x100+19:99,0x100+21:1})
            assert m.run('usb_poll_check_reset_duration',('usb_poll_check_packet_pending',))=='usb_poll_check_packet_pending'
            assert m.r[2]==0 and m.mem[0x100+15]==0x5a and m.mem[0x100+0]==0xff
            assert m.mem[0x100+12]==0 and m.mem[0x100+21]==0
            # NEW_DEVICE_ADDRESS is overwritten by the next valid SETUP;
            # it need not be cleared separately by bus reset.
            assert m.mem[0x100+19]==99
            cases+=1
    print('PASS ACK packet/retry/bus-reset opcode cases:',cases)

if __name__=='__main__':
    test_profiles()
    test_flash()
    test_ack()
