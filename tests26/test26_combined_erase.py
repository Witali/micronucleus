"""Pass24 machine-opcode tests for select-only / select-and-erase control requests."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_build import build
from tests.avr_exec import AVRExec
from host import compact_programmer as h
SRC=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass26.S'


def test():
    count=0
    for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        art=build(SRC,mode,0x1b00)
        for page in list(range(0,art['boot'],64))+[0x1b00,0x1b40,0x1fc0]:
            for request in (h.REQ_SET_ADDRESS, h.REQ_SELECT_ERASE):
                block=page//4
                x=AVRExec(art)
                x.r[25]=request;x.r[3]=0
                x.ram.update({27:block&255,28:(block>>8)&255,25:0,26:0})
                assert x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'])=='stop'
                assert x.r[4] | (x.r[5]<<8)==page
                assert len(x.spms)==1 and x.spms[0][:2]==(0x11,0)
                assert x.r[3]==request+1,(request,page,x.r[3])
                x.spms.clear()
                assert x.run('bootloader_dispatch_command',stop=['bootloader_clear_command'])=='stop'
                if request==h.REQ_SELECT_ERASE and page<art['boot']:
                    assert x.spms and x.spms[0][:2]==(0x03,page),(request,page,x.spms)
                else:
                    assert not x.spms,(request,page,x.spms)
                count+=1
        # Crucial: invalid EEPROM + select-and-erase must never erase the previously chosen Flash page.
        for block in list(range(16))+[0x10,0x1ff,0x7fff]:
            for request in (h.REQ_SET_ADDRESS,h.REQ_SELECT_ERASE):
                x=AVRExec(art)
                x.r[25]=request;x.r[3]=0
                x.r[4]=0x40;x.r[5]=0    # previously selected Flash page
                field=0x8000|block
                x.ram.update({27:field&255,28:field>>8})
                assert x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'])=='stop'
                assert not x.spms
                assert x.r[3]==0,(hex(field),request,x.r[3])
                if block<16:assert x.r[4:6]==[block*4,0x80]
                else:assert x.r[4:6]==[0x40,0]
                count+=1
        print('PASS',mode,'select-and-erase/deferred/boot protection opcode paths')
    # New v5.4: SELECT_ADDRESS retains low four block bits. ERASE_ALIGN remains in SPM.
    a=build(SRC,'NONE',0x1b40)
    for block in range(1,16):
        x=AVRExec(a);x.r[25]=h.REQ_SET_ADDRESS
        x.ram.update({27:block,28:0})
        assert x.run('bootloader_check_set_flash_address',stop=['usb_reply_empty'])=='stop'
        assert x.r[4] | (x.r[5]<<8)==block*4
    # Host never issues the combined Flash erasure command for EEPROM.
    d=type('Device',(),{'idVendor':h.USB_VID,'idProduct':h.USB_PID,'bcdDevice':0x0550})()
    t=h.USBTransport(d)
    try:t.set_address(0,eeprom=True,erase=True)
    except ValueError:pass
    else:raise AssertionError('EEPROM erase must be rejected by host')
    print('PASS',count,'combined address+erase machine-opcode cases')
if __name__=='__main__':test()
