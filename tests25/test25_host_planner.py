"""Pure offline host-side vector relocation and protocol tests.

The mock is NOT a USB hardware simulator and cannot validate timing/ACK.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
import compact_programmer as h

class USBMock:
    idVendor,idProduct,bcdDevice=h.USB_VID,h.USB_PID,h.USB_BCD
    def __init__(self, boot_at=h.BOOT_AT):
        self.boot_at=boot_at
        self.flash=bytearray(b'\xff'*h.FLASH_SIZE)
        self.eep=bytearray(b'\xff'*h.EEPROM_SIZE)
        self.mode,self.ptr='flash',0
        self.calls=[];self.pending=[]
    def ctrl_transfer(self,bm,cmd,value,index,data,timeout=5000):
        self.calls.append((bm,cmd,value,index))
        if cmd in (h.REQ_SET_ADDRESS, h.REQ_SELECT_ERASE):
            assert bm==0x40 and data==[]
            self.mode,self.ptr=h.decode_addr(index)
            if self.mode=='flash':
                self.pending=[]
            if cmd==h.REQ_SELECT_ERASE:
                assert self.mode=='flash'
                assert 0<=self.ptr<self.boot_at and self.ptr%h.PAGE_BYTES==0
                self.flash[self.ptr:self.ptr+64]=b'\xff'*64
            return []
        if cmd==h.REQ_WRITE4:
            raw=value.to_bytes(2,'little')+index.to_bytes(2,'little')
            if self.mode=='flash':
                self.pending.extend(raw)
                if len(self.pending)==64:
                    addr=self.ptr-60
                    self.flash[addr:addr+64]=self.pending
                    self.pending=[]
            else:self.eep[self.ptr:self.ptr+4]=raw
            self.ptr+=4
            return []
        if cmd==h.REQ_READ8:
            assert bm==0xC0 and data==8
            kind,addr=self.mode,self.ptr
            self.ptr+=8
            if kind=='eeprom': return list(self.eep[addr:addr+8])
            assert 0<=addr<=h.FLASH_SIZE-8
            return list(self.flash[addr:addr+8])
        if cmd==h.REQ_RUN:return []
        raise AssertionError((bm,cmd,value,index,data))


def test_vectors():
    tests=[0, 1, 64, h.APP_BYTES//2-1]
    for entry in tests:
        if entry==0:continue
        rel=(entry-1)&0xfff
        raw={0:(0xc000|rel)&255,1:(0xc000|rel)>>8,2:0x43,3:0x21,entry*2:0xa5}
        patched=h.pack_application(raw)
        assert patched.reset_target_word==entry
        assert int.from_bytes(patched.image[:2],'little')==patched.boot_reset_word
        effective_pc=((h.BOOT_AT-4)//2+1+((patched.postscript_reset_word&0xfff)^0x800)-0x800)&0xfff
        assert effective_pc==entry,(entry,effective_pc)
        assert patched.image[h.POSTSCRIPT_AT+2:h.BOOT_AT]==b'\xff\xff'
        assert patched.image[entry*2]==0xa5
    abs_image=h.pack_application({0:0x0c,1:0x94,2:0x34,3:0x01})
    assert abs_image.reset_target_word==0x134
    for bad in [{0:0xff,1:0xff},{h.APP_BYTES:1},{0:0x0c,1:0x94,2:0xff,3:0x1f}]:
        try:h.pack_application(bad)
        except ValueError:pass
        else:raise AssertionError(('invalid reset should fail',bad))
    print('PASS host RESET relocation (relative, absolute, invalid)')


def test_hex():
    h1=h.image_to_hex(b'\x11\x22\x33\x44\xff\xaa')
    assert h.parse_intel_hex(h1)==dict(enumerate(b'\x11\x22\x33\x44\xff\xaa'))
    try:h.parse_intel_hex(h1.replace('11223344','11223345'))
    except ValueError:pass
    else:raise AssertionError('Checksum not rejected')
    for encoded in (0,0x6ff,0x8000,0x800f,0xffff):
        kind,byte=h.decode_addr(encoded)
        assert byte==(encoded&0x7fff)*4
        assert kind==('eeprom' if encoded&0x8000 else 'flash')
    assert h.encode_addr(60,eeprom=True)==0x800f
    for a in (1,-1,64,8192):
        try:h.encode_addr(a,eeprom=True)
        except ValueError:pass
        else:raise AssertionError(('accepted invalid EEPROM address',a))
    print('PASS block addressing, Intel HEX/CRC record, bounds')


def test_program():
    u=USBMock();x=h.USBTransport(u)
    reset=0xc000|((0x81-1)&0xfff)
    patch=h.pack_application({0:reset&255,1:reset>>8,2:0x34,3:0x56,0x102:0xab,0x103:0xcd,h.APP_BYTES-1:0x91})
    import unittest.mock
    with unittest.mock.patch.object(h.time,'sleep'):
        h.program_application(x,patch)
    assert u.flash[:h.BOOT_AT]==patch.image
    assert u.flash[h.BOOT_AT:]==b'\xff'*(8192-h.BOOT_AT)
    assert u.calls[0][1:2]==(h.REQ_SELECT_ERASE,)
    assert u.calls[0][3]==h.encode_addr(h.BOOT_AT-h.PAGE_BYTES)
    assert sum(cmd==h.REQ_SELECT_ERASE for bm,cmd,value,index in u.calls)==h.BOOT_AT//h.PAGE_BYTES
    assert u.calls[-1][1:2]==(h.REQ_READ8,)
    data=h.read_flash(x)
    assert data==patch.image[:h.APP_BYTES]
    u2=USBMock();x2=h.USBTransport(u2)
    with unittest.mock.patch.object(h.time,'sleep'):
        for pos in range(0,64,4): h.program_eeprom_block(x2,pos,bytes(((pos+i)*3)&255 for i in range(4)))
    assert h.read_eeprom(x2)==bytes(i*3&255 for i in range(64))
    u2.bcdDevice=0x0400
    try:h.USBTransport(u2)
    except ValueError:pass
    else:raise AssertionError('Old firmware not rejected')
    # A fingerprint can identify a different loader boundary (LED profiles).
    # The same PC programmer must then relocate RESET and postscript to 0x1AC0.
    led_boot=0x1ac0
    app=h.pack_application({0:reset&255,1:reset>>8,2:0x34,3:0x56,
                            led_boot-5:0xa1},boot_at=led_boot)
    led_dev=USBMock(boot_at=led_boot)
    led_transport=h.USBTransport(led_dev)
    led_transport.boot_at=led_boot
    led_transport.app_bytes=led_boot-4
    import unittest.mock
    with unittest.mock.patch.object(h.time,'sleep'):
        h.program_application(led_transport,app)
    assert led_dev.flash[:led_boot]==app.image
    assert len(h.read_flash(led_transport))==led_boot-4
    assert led_dev.flash[led_boot:]==bytes([0xff])*(h.FLASH_SIZE-led_boot)
    # Host must reject a patched image prepared for a different loader layout
    # BEFORE any USB commands or Flash writes.
    wrong_app=h.pack_application({0:reset&255,1:reset>>8},boot_at=h.BOOT_AT)
    initial=len(led_dev.calls)
    try:h.program_application(led_transport,wrong_app)
    except ValueError:pass
    else:raise AssertionError('Wrong loader geometry accepted')
    assert len(led_dev.calls)==initial
    print('PASS host dynamic 19/20-page layouts, postscript readback and protection')
    print('PASS mock PC-side complete Flash and EEPROM programming')

if __name__=='__main__':
    test_vectors();test_hex();test_program()
