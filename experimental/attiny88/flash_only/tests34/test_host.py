#!/usr/bin/env python3
"""Mock USB controller for exact vendor request and recoverable programming.

No hardware device is accessed; deliberate lost-ACK injection is only a model.
"""
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import flash_only_programmer35 as host
from eeprom_stage.plan_two_stage import KNOWN_BCD_BOOT

class Mock:
    def __init__(self,revision=0x0450):
        self.idVendor,self.idProduct,self.bcdDevice=host.USB_VID,host.USB_PID,revision
        self.flash=bytearray([0xFF])*8192
        self.page=None
        self.buffer={}
        self.calls=[]
        self.inject_commit_once=False
        self.inject_write_once=False
        self.run_called=False
        self.read_count=0
        self.erases=[]
        self.commits=[]
    def ctrl_transfer(self,bm,req,value,index,payload,timeout=5000):
        self.calls.append((bm,req,value,index,payload))
        if bm==0xC0 and req==host.REQ_READ8:
            assert value==0 and payload==8 and index%2==0
            self.read_count+=1
            return bytes(self.flash[index:index+8])
        assert bm==0x40 and payload==[]
        if req in (host.REQ_SELECT,host.REQ_SELECT_ERASE):
            assert index%64==0 and index<0x1C00
            self.page=index
            self.buffer={}
            if req==host.REQ_SELECT_ERASE:
                self.flash[index:index+64]=bytes([0xFF])*64
                self.erases.append(index)
        elif req==host.REQ_WRITE2:
            assert index%2==0 and self.page is not None
            assert self.page<=index<self.page+64
            self.buffer[index]=value.to_bytes(2,'little')
            if self.inject_write_once:
                self.inject_write_once=False
                raise OSError('Simulated lost USB status after WRITE2: stage is uncertain')
        elif req==host.REQ_COMMIT_PAGE:
            assert self.page is not None
            for a,data in self.buffer.items():
                self.flash[a:a+2]=data
            self.commits.append(self.page)
            self.page=None
            self.buffer={}
            if self.inject_commit_once:
                self.inject_commit_once=False
                raise OSError('Simulated lost USB ACK after actual COMMIT')
        elif req==host.REQ_RUN:self.run_called=True
        else:raise AssertionError(('unsupported request',hex(req)))
        return 0

def test_host():
    count=0
    for bcd in (0x0450,0x0451,0x0452):
        dev=Mock(bcd);t=host.USBTransport(dev)
        assert t.boot_at==KNOWN_BCD_BOOT[bcd]
        for bad in (t.boot_at,t.boot_at+64,8192,-64,1):
            try:t.erase_page(bad)
            except ValueError:pass
            else:raise AssertionError(('accepted unsafe page',hex(bad)))
        assert not dev.calls
        assert t.read8_firmware(t.boot_at-8)==b'\xff'*8
        assert dev.calls[-1][:4]==(0xc0,0xb0,0,t.boot_at-8)
        t.erase_page(0x80)
        assert dev.calls[-1][:4]==(0x40,2,0,0x80)
        try:t.commit_page()
        except ValueError:pass
        else:raise AssertionError('committed incomplete page')
        for i in range(0,64,2):t.write2(0x80+i,(i*7&0xffff).to_bytes(2,'little'))
        assert dev.calls[-1][1]==3
        t.commit_page()
        assert dev.commits[-1]==0x80
        assert dev.flash[0x80:0xC0]==b''.join((i*7).to_bytes(2,'little') for i in range(0,64,2))
        count+=1
    for old in (0x0300,0x0410,0x0420,0x9999):
        dev=Mock(old)
        try:host.USBTransport(dev)
        except ValueError:pass
        else:raise AssertionError('Old protocol accepted')
        assert not dev.calls
    # The repeated address never advances. Replaying identical word does not
    # overwrite a different word (a crucial distinction from old WRITE4).
    dev=Mock();t=host.USBTransport(dev);t.erase_page(0)
    t.write2(6,b'AB')
    snapshot=dict(dev.buffer)
    dev.ctrl_transfer(0x40,3,int.from_bytes(b'AB','little'),6,[])
    assert dev.buffer==snapshot and len(dev.buffer)==1
    dev.inject_write_once=True
    try:t.write2(8,b'XY')
    except OSError:pass
    else:raise AssertionError('Lost WRITE2 ACK not propagated')
    assert t._selected_page is None
    try:t.commit_page()
    except ValueError:pass
    else:raise AssertionError('Committed after uncertain write')
    count+=1
    # Full application image with RESET/postscript, verified through actual
    # READ8 request addresses. Every page is erased, filled, committed, checked.
    dev=Mock();t=host.USBTransport(dev)
    src={0:0,1:0xc0,2:0x33,3:0x44,5:0x08,106:0x37,107:0x42}
    patched=host.pack_application(src,boot_at=t.boot_at)
    with patch.object(host.time,'sleep',lambda _:None):
        host.program_application(t,patched)
    assert dev.flash[:t.boot_at]==patched.image
    assert len(dev.commits)==t.boot_at//64
    assert dev.erases[0]==t.boot_at-64
    assert dev.read_count>=t.boot_at//8
    assert all(not 0x1c00<=a<8192 for a in dev.commits)
    count+=1
    # If device has committed but the status ACK is lost, host verifies Flash
    # and accepts only the actual correct result. It never repeats COMMIT.
    dev=Mock();t=host.USBTransport(dev);dev.inject_commit_once=True
    with patch.object(host.time,'sleep',lambda _:None):
        host.program_application(t,patched)
    assert dev.flash[:t.boot_at]==patched.image
    assert len(dev.commits)==t.boot_at//64
    count+=1
    # No write automatically happens when only image preparation is requested.
    print('PASS mock host Flash, idempotent WRITE2, postscript & uncertain COMMIT:',count,'groups')

if __name__=='__main__':test_host()
