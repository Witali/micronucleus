#!/usr/bin/env python3
"""Protocol4.2 mock: cursor I/O, auto-write and once-per-word page buffering."""
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import flash_only_programmer35 as host
from eeprom_stage.plan_two_stage import KNOWN_BCD_BOOT


class Mock:
    def __init__(self,revision=next(iter(host.USB_PROFILES))):
        self.idVendor,self.idProduct,self.bcdDevice=host.USB_VID,host.USB_PID,revision
        self.flash=bytearray([0xff])*host.FLASH_BYTES
        self.cursor=None
        self.page=None
        self.buffer={}
        self.loaded_words=set()
        self.calls=[];self.events=[]
        self.run_called=False;self.read_count=0
        self.erases=[];self.commits=[];self.loads=[]
        self.inject_write_once=False;self.inject_auto_once=False

    def load_word(self,address,data):
        # ATtiny88 datasheet19.0.2 forbids loading the same temporary-buffer
        # word twice, even if identical bytes would appear idempotent.
        assert address not in self.loaded_words,('temporary word loaded twice',address)
        self.loaded_words.add(address);self.buffer[address]=bytes(data)
        self.loads.append(address)

    def ctrl_transfer(self,bm,req,value,index,payload,timeout=5000):
        self.calls.append((bm,req,value,index,payload));self.events.append(('usb',req))
        if bm==0xc0 and req==host.REQ_READ8:
            assert value==index==0 and isinstance(payload,int) and 1<=payload<=8
            assert self.cursor is not None and self.cursor+payload<=host.FLASH_BYTES
            assert not self.loaded_words,'READ interleaved a staged page'
            self.read_count+=1
            result=bytes(self.flash[self.cursor:self.cursor+payload]);self.cursor+=len(result)
            return result
        assert bm==0x40 and payload==[]
        if req in (host.REQ_SELECT,host.REQ_SELECT_ERASE):
            assert value==0 and index%2==0 and 0<=index<host.FLASH_BYTES
            self.cursor=index;self.page=index-index%64
            self.buffer={};self.loaded_words.clear()
            if req==host.REQ_SELECT_ERASE:
                assert index%64==0 and index<host.BOOT_AT
                self.flash[index:index+64]=b'\xff'*64
                self.erases.append(index);self.events.append(('erase',index))
        elif req==host.REQ_WRITE4:
            assert self.cursor is not None and self.cursor%4==0
            assert 0<=self.cursor and self.cursor+4<=host.BOOT_AT
            page=self.cursor-self.cursor%64
            assert self.page==page
            data=value.to_bytes(2,'little')+index.to_bytes(2,'little')
            self.load_word(self.cursor,data[:2]);self.load_word(self.cursor+2,data[2:])
            self.cursor+=4
            if self.cursor%64==0:
                assert self.loaded_words==set(range(page,page+64,2))
                for address,word in self.buffer.items():
                    for i,byte in enumerate(word):self.flash[address+i]&=byte
                self.commits.append(page);self.events.append(('auto',page))
                self.buffer={};self.loaded_words.clear();self.page=self.cursor
                if self.inject_auto_once:
                    self.inject_auto_once=False
                    raise OSError('Lost status after actual automatic page write')
            if self.inject_write_once:
                self.inject_write_once=False
                raise OSError('Lost WRITE4 status after buffer/cursor effect')
        elif req==host.REQ_RUN:self.run_called=True
        else:raise AssertionError(('unsupported request',req))
        return 0


def prepared_page(t,page):
    t.erase_page(page);t.wait_ready();host.verify_erased(t,page);t.select_page(page)


def test_host():
    groups=0
    for bcd in host.USB_PROFILES:
        dev=Mock(bcd);t=host.USBTransport(dev)
        assert t.boot_at==KNOWN_BCD_BOOT[bcd]
        t.select(0x80)
        assert t.read8()==b'\xff'*8 and t.cursor==dev.cursor==0x88
        assert t.read8(3)==b'\xff'*3 and t.cursor==dev.cursor==0x8b
        assert dev.calls[-2][:4]==(0xc0,0xb0,0,0)
        assert dev.calls[-1][4]==3
        with patch.object(host.time,'sleep',lambda _:None):
            prepared_page(t,0x80)
            for offset in range(0,64,4):
                data=bytes((offset,offset+1,offset+2,offset+3))
                t.write4(data)
                assert t.cursor==dev.cursor==0x80+offset+4
            t.wait_ready()
        assert dev.commits==[0x80]
        assert dev.flash[0x80:0xc0]==bytes(range(64))
        assert not any(call[1]==5 for call in dev.calls)
        groups+=1
    for old in (0x0300,0x0410,0x0420,0x0450,0x0451,0x0452,0x0460,0xffff,0x9999):
        dev=Mock(old)
        try:host.USBTransport(dev)
        except ValueError:pass
        else:raise AssertionError('Incompatible protocol accepted')
        assert not dev.calls
    for address in (-64,1,host.BOOT_AT,host.BOOT_AT+64,8192):
        dev=Mock();t=host.USBTransport(dev)
        try:t.erase_page(address)
        except ValueError:pass
        else:raise AssertionError(('unsafe erase accepted',address))
        assert not dev.calls
    # A complete image preserves RESET/postscript packing and all boot bytes.
    dev=Mock();t=host.USBTransport(dev)
    boot_before=bytes(dev.flash[t.boot_at:])
    image=host.pack_application({0:0,1:0xc0,2:0x33,3:0x44,106:0x37,107:0x42},boot_at=t.boot_at)
    waits=[]
    def wait(delay):waits.append(delay);dev.events.append(('wait',delay))
    with patch.object(host.time,'sleep',wait):host.program_application(t,image)
    assert dev.flash[:t.boot_at]==image.image
    assert bytes(dev.flash[t.boot_at:])==boot_before
    assert len(dev.commits)==t.boot_at//64 and dev.erases[0]==t.boot_at-64
    configured=host.DEFAULT_FLASH_DELAY_MS/1000
    assert len(waits)==2*(t.boot_at//64) and all(n==configured for n in waits)
    for i,event in enumerate(dev.events):
        if event[0] in ('erase','auto'):assert dev.events[i+1]==('wait',configured)
    assert all(call[2:4]==(0,0) for call in dev.calls if call[1]==host.REQ_READ8)
    assert sum(call[1]==host.REQ_WRITE4 for call in dev.calls)==16*(t.boot_at//64)
    assert not any(call[1]==5 for call in dev.calls)
    groups+=1
    # A repeated buffer load is prohibited, not an idempotence guarantee.
    dev=Mock();dev.ctrl_transfer(0x40,host.REQ_SELECT,0,0,[])
    dev.load_word(0,b'AB')
    try:dev.load_word(0,b'AB')
    except AssertionError:pass
    else:raise AssertionError('Repeated temporary-buffer word was accepted')
    groups+=1
    print('PASS v4.2 cursor READ8/WRITE4, automatic pages, RESET/postscript and once-per-word buffer:',groups,'groups')


if __name__=='__main__':test_host()
