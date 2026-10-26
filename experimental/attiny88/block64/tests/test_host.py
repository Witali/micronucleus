from __future__ import annotations
import pathlib,sys,random,pytest
ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'host'))
from micronucleus_block64 import *

BOOT=0x1980
APP=BOOT-4
class MockUSB:
    bcdDevice=0x0300
    def __init__(self):
        self.flash=bytearray(b'\xff'*8192)
        self.eeprom=bytearray(b'\xff'*64)
        self.log=[]
        self.status=0
        self.running=False
    def ctrl_transfer(self,request_type,request,value,index,data_or_wlength,timeout=6000):
        self.log.append((request_type,request,value,index,data_or_wlength))
        if request_type==IN_VENDOR:
            if request==REQ_INFO:
                assert data_or_wlength==8
                return [(APP>>8)&255,APP&255,64,5,0x93,0x11,0xe1,0]
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
        assert request==REQ_WRITE
        data=bytes(data_or_wlength)
        assert 1<=len(data)<=64
        mem=self.flash if index==FLASH else self.eeprom
        assert value+len(data)<=(BOOT if index==FLASH else 64)
        if index==FLASH:assert (value&~63)==((value+len(data)-1)&~63)
        if index==FLASH:
            page=value&~63
            local=bytearray(mem[page:page+64])
            local[value-page:value-page+len(data)]=data
            if page==0:
                patched=(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
                local[:2]=patched
            mem[page:page+64]=local
        else:mem[value:value+len(data)]=data
        return len(data)

def test_connection_and_geometry():
    d=MockUSB();h=Programmer(d)
    i=h.connect()
    assert i.app_size==APP and i.boot_start==BOOT and i.page_size==64 and i.eeprom_size==64

def test_flash_read_256_one_transfer_per_64():
    d=MockUSB();h=Programmer(d);h.connect()
    d.flash[:256]=bytes(range(256))
    assert h.read(FLASH,0,256)==bytes(range(256))
    assert len([a for a in d.log if a[1]==REQ_READ])==4

def test_eeprom_full_read_write_one_transfer_each():
    d=MockUSB();h=Programmer(d);h.connect()
    block=bytes((i*9)&255 for i in range(64))
    h.write(EEPROM,0,block,verify=True)
    assert h.read(EEPROM,0,64)==block
    assert len([a for a in d.log if a[1]==REQ_WRITE])==1
    assert len([a for a in d.log if a[1]==REQ_READ])==2


def test_flash_page_partial_split():
    d=MockUSB();h=Programmer(d);h.connect()
    d.flash[0x100:0x180]=b'Z'*128
    data=bytes(range(75))
    h.write(FLASH,0x100+60,data)
    assert d.flash[0x100+60:0x100+60+75]==data
    assert d.flash[0x100:0x100+60]==b'Z'*60
    assert [value for typ,req,value,idx,blob in d.log if req==REQ_WRITE]==[0x13C,0x140,0x180]


def test_upload_reset_vector_and_final_postscript():
    d=MockUSB();h=Programmer(d);h.connect()
    # RESET RJMP to address 0x0010 => word target=0x0008,
    # encoded offset=0x0007 from PC=0.
    image={0:0x07,1:0xC0,16:0x22,17:0x33}
    h.upload(image,full_erase=False,verify=True,run=True)
    assert d.running
    assert d.flash[:2]==(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
    ps_word=int.from_bytes(d.flash[APP:APP+2],'little')
    target=((APP//2)+1+(ps_word&0xfff))&0xfff
    assert target==8
    assert d.flash[16:18]==b'\x22\x33'
    writes=[value for typ,req,value,idx,blob in d.log if req==REQ_WRITE]
    assert writes[0]==APP and writes[-1]==BOOT-64


def test_upload_rejects_no_reset_rjmp():
    d=MockUSB();h=Programmer(d);h.connect()
    with pytest.raises(Block64Error,match='RJMP'):h.upload({0:0,1:0})


def test_no_write_into_loader():
    d=MockUSB();h=Programmer(d);h.connect()
    with pytest.raises(Block64Error):h.write(FLASH,BOOT,b'X')
    with pytest.raises(Block64Error):h.write(EEPROM,63,b'AB')


def test_read_all_64_lengths():
    d=MockUSB();h=Programmer(d);h.connect()
    d.eeprom[:]=bytes(range(64))
    for n in range(1,65):
        assert h.read(EEPROM,0,n)==bytes(range(n))


def test_intel_hex_roundtrip(tmp_path):
    b=bytes((i*13+7)&255 for i in range(128))
    p=tmp_path/'f.hex';p.write_text(dump_hex(b,0x100))
    parsed=parse_hex(p)
    assert bytes(parsed[x] for x in range(0x100,0x180))==b
    invalid=tmp_path/'invalid.hex';invalid.write_text(p.read_text().replace(':10',':11',1))
    with pytest.raises(Block64Error):parse_hex(invalid)


def test_wrong_legacy_version_rejected():
    d=MockUSB();d.bcdDevice=0x0208
    with pytest.raises(Block64Error,match='version|bcdDevice'):Programmer(d).connect()
