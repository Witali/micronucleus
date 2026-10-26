from __future__ import annotations
import pathlib,sys,random,pytest
ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'host'))
from micronucleus_block64 import *

BOOT=0x1940
APP=BOOT-4

class MockUSB:
    bcdDevice=0x0301
    def __init__(self):
        self.flash=bytearray(b'\xff'*8192)
        self.eeprom=bytearray(b'\xff'*64)
        self.log=[]
        self.status=0
        self.running=False
        self.erased=set()
    def ctrl_transfer(self,request_type,request,value,index,data_or_wlength,timeout=6000):
        self.log.append((request_type,request,value,index,data_or_wlength))
        if request_type==IN_VENDOR:
            if request==REQ_INFO:
                assert data_or_wlength==8
                return [(APP>>8)&255,APP&255,64,5,0x93,0x11,0xe3,0]
            if request==REQ_STATUS:return [self.status]
            assert request==REQ_READ
            size=data_or_wlength
            assert 1<=size<=64
            assert index in (FLASH,EEPROM)
            memory=self.flash if index==FLASH else self.eeprom
            assert 0<=value<=len(memory) and value+size<=(BOOT if index==FLASH else 64)
            return list(memory[value:value+size])
        assert request_type==OUT_VENDOR
        if request==REQ_RUN:
            assert len(data_or_wlength)==0
            self.running=True
            return 0
        if request==REQ_ERASE_PAGE:
            assert index==FLASH and value%64==0 and value<BOOT
            assert len(data_or_wlength)==0
            self.flash[value:value+64]=b'\xff'*64
            self.erased.add(value)
            return 0
        assert request==REQ_WRITE
        data=bytes(data_or_wlength)
        assert 1<=len(data)<=64
        mem=self.flash if index==FLASH else self.eeprom
        assert value+len(data)<=(BOOT if index==FLASH else 64)
        if index==FLASH:
            assert value%64==0 and len(data)==64
            assert value in self.erased, 'Firmware WRITE must not erase implicitly'
            new=bytearray(data)
            if value==0:
                reset=(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
                new[:2]=reset
            mem[value:value+64]=new
            self.erased.remove(value)
        else:mem[value:value+len(data)]=data
        return len(data)

def make():
    d=MockUSB();h=Programmer(d,sleep=lambda _:None);h.connect()
    return d,h

def test_connection_and_geometry():
    d,h=make();i=h.info
    assert i.app_size==APP and i.boot_start==BOOT and i.page_size==64 and i.eeprom_size==64
    assert i.version==0x0301 and i.features&BOOT_FEATURE_SPLIT_ERASE

def test_flash_read_256_one_transfer_per_64():
    d,h=make();d.flash[:256]=bytes(range(256))
    assert h.read(FLASH,0,256)==bytes(range(256))
    assert len([a for a in d.log if a[1]==REQ_READ])==4

def test_eeprom_full_read_write_one_transfer_each():
    d,h=make();block=bytes((i*9)&255 for i in range(64))
    h.write(EEPROM,0,block,verify=True)
    assert h.read(EEPROM,0,64)==block
    assert len([a for a in d.log if a[1]==REQ_WRITE])==1
    assert len([a for a in d.log if a[1]==REQ_READ])==2
    assert not [a for a in d.log if a[1]==REQ_ERASE_PAGE]

def test_flash_full_page_write_does_not_read():
    d,h=make();start=0x100;data=bytes((i*3+5)&255 for i in range(64))
    h.write(FLASH,start,data,verify=False)
    assert d.flash[start:start+64]==data
    assert [a[1] for a in d.log if a[1] in (REQ_READ,REQ_ERASE_PAGE,REQ_WRITE)]==[REQ_ERASE_PAGE,REQ_WRITE]

def test_flash_page_partial_split_is_host_side_rmw():
    d,h=make();d.flash[0x100:0x180]=b'Z'*128
    data=bytes(range(75))
    h.write(FLASH,0x100+60,data)
    assert d.flash[0x100+60:0x100+60+75]==data
    assert d.flash[0x100:0x100+60]==b'Z'*60
    assert [value for typ,req,value,idx,blob in d.log if req==REQ_WRITE]==[0x100,0x140,0x180]
    assert [value for typ,req,value,idx,blob in d.log if req==REQ_ERASE_PAGE]==[0x100,0x140,0x180]
    assert sum(req==REQ_READ for typ,req,_,_,_ in d.log)>=2
    assert all(len(blob)==64 for typ,req,_,_,blob in d.log if req==REQ_WRITE)

def test_flash_erase_and_write_are_explicit_independent_operations():
    d,h=make();start=0x280
    d.flash[start:start+64]=b'A'*64
    h.erase_page(start,verify=True)
    assert d.flash[start:start+64]==b'\xff'*64
    assert not [a for a in d.log if a[1]==REQ_WRITE]
    data=bytes(range(64))
    h.write_page(start,data)
    assert d.flash[start:start+64]==data
    assert [a[1] for a in d.log if a[1] in (REQ_ERASE_PAGE,REQ_WRITE)]==[REQ_ERASE_PAGE,REQ_WRITE]

def test_flash_write_page_rejects_non_page_or_bad_addresses():
    d,h=make()
    with pytest.raises(Block64Error):h.write_page(0x100,b'X')
    with pytest.raises(Block64Error):h.write_page(0x101,b'X'*64)
    with pytest.raises(Block64Error):h.erase_page(BOOT)
    with pytest.raises(Block64Error):h.erase_page(BOOT-1)
    assert not d.log or all(x[1]==REQ_INFO for x in d.log)

def test_upload_reset_vector_and_final_postscript():
    d,h=make()
    image={0:0x07,1:0xC0,16:0x22,17:0x33}
    h.upload(image,full_erase=True,verify=True,run=True)
    assert d.running
    assert d.flash[:2]==(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
    ps_word=int.from_bytes(d.flash[APP:APP+2],'little')
    target=((APP//2)+1+(ps_word&0xfff))&0xfff
    assert target==8
    assert d.flash[16:18]==b'\x22\x33'
    calls=[(req,value) for typ,req,value,idx,blob in d.log if req in (REQ_ERASE_PAGE,REQ_WRITE)]
    assert calls[0]==(REQ_ERASE_PAGE,BOOT-64) # postscript invalidated first
    assert calls[-1]==(REQ_WRITE,BOOT-64) # and restored last
    assert (REQ_WRITE,0) in calls[-4:] # reset page programmed near the end

def test_incremental_upload_preserves_unspecified_bytes():
    d,h=make();d.flash[0x100:0x140]=bytes([0x77]*64)
    image={0:0x07,1:0xc0,0x102:0xA1,0x103:0xB2}
    h.upload(image,full_erase=False,verify=True)
    assert d.flash[0x100:0x102]==b'\x77\x77'
    assert d.flash[0x102:0x104]==b'\xA1\xB2'
    assert d.flash[0x104:0x140]==b'\x77'*(64-4)
    assert (REQ_ERASE_PAGE,0x100) in [(req,addr) for typ,req,addr,_,_ in d.log]

def test_upload_rejects_no_reset_rjmp():
    d,h=make()
    with pytest.raises(Block64Error,match='RJMP'):h.upload({0:0,1:0})

def test_no_write_into_loader():
    d,h=make()
    with pytest.raises(Block64Error):h.write(FLASH,BOOT,b'X')
    with pytest.raises(Block64Error):h.write(EEPROM,63,b'AB')

def test_read_all_64_lengths():
    d,h=make();d.eeprom[:]=bytes(range(64))
    for n in range(1,65):assert h.read(EEPROM,0,n)==bytes(range(n))

def test_intel_hex_roundtrip(tmp_path):
    b=bytes((i*13+7)&255 for i in range(128))
    p=tmp_path/'f.hex';p.write_text(dump_hex(b,0x100))
    parsed=parse_hex(p)
    assert bytes(parsed[x] for x in range(0x100,0x180))==b
    invalid=tmp_path/'invalid.hex';invalid.write_text(p.read_text().replace(':10',':11',1))
    with pytest.raises(Block64Error):parse_hex(invalid)

def test_wrong_legacy_version_rejected():
    d=MockUSB();d.bcdDevice=0x0300
    with pytest.raises(Block64Error,match='version|bcdDevice'):Programmer(d).connect()


def test_host_pauses_between_usb_spm_request_and_status():
    events=[]
    class Observed(MockUSB):
        def ctrl_transfer(self,request_type,request,value,index,data_or_wlength,timeout=6000):
            events.append(('usb',request))
            return super().ctrl_transfer(request_type,request,value,index,data_or_wlength,timeout)
    dev=Observed()
    host=Programmer(dev,sleep=lambda t:events.append(('sleep',t)))
    host.connect()
    events.clear()
    host.erase_page(0x100)
    host.write_page(0x100,bytes(range(64)),verify=False)
    assert events==[
        ('usb',REQ_ERASE_PAGE),('sleep',host.spm_settle_s),('usb',REQ_STATUS),
        ('usb',REQ_WRITE),('sleep',host.spm_settle_s),('usb',REQ_STATUS)]


def test_full_upload_never_reads_old_flash_when_verify_disabled():
    dev,host=make()
    host.upload({0:7,1:0xc0,0x100:0x44,0x101:0x55},full_erase=True,verify=False)
    assert all(req!=REQ_READ for _,req,_,_,_ in dev.log)
    assert dev.flash[0x100:0x102]==b'\x44\x55'


def test_host_preserves_application_selected_isr_vectors():
    d,h=make()
    image={0:0x07,1:0xc0}
    for n in range(1,20):
        word=0xc000|((n*13+5)&0xfff)
        image[2*n]=word&0xff
        image[2*n+1]=word>>8
    h.upload(image,full_erase=True,verify=True)
    for n in range(1,20):
        word=0xc000|((n*13+5)&0xfff)
        assert d.flash[2*n:2*n+2]==word.to_bytes(2,'little')
    assert d.flash[:2]==(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
