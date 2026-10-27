"""Zero-vendor-command version identification by the standard USB descriptor."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host.compact_programmer import USBTransport,USB_PROFILES,USB_VID,USB_PID
from check_build import build
SRC=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass26.S'

class USBStub:
    idVendor=USB_VID
    idProduct=USB_PID
    def __init__(self,v):self.bcdDevice=v;self.ops=[]
    def ctrl_transfer(self,*a,**kw):self.ops.append((a,kw));raise AssertionError('No proprietary USB command allowed during identification')

def test():
    modes=[('NONE',0x0550,1206),('ACTIVE_HIGH',0x0551,1220),('ACTIVE_LOW',0x0552,1218)]
    for mode,version,size in modes:
        art=build(SRC,mode,0x1b40 if mode=='NONE' else 0x1b00)
        assert art['size']==size
        offset=(art['symbols']['USB_handler']-art['boot'])-18
        assert int.from_bytes(art['body'][offset+12:offset+14],'little')==version
        dev=USBStub(version);transport=USBTransport(dev)
        assert transport.boot_at==(0x1b40 if mode=='NONE' else 0x1b00)
        assert transport.app_bytes==(6972 if mode=='NONE' else 6908)
        assert transport.code_bytes==size
        assert not dev.ops
        print('PASS',mode,hex(version),'identified without proprietary requests')
    for version in (0x0500,0x0501,0x0533,0xffff):
        dev=USBStub(version)
        try:USBTransport(dev)
        except ValueError:pass
        else:raise AssertionError('Unrecognized device accepted')
        assert not dev.ops
    print('PASS descriptor-only version selection and unknown-version rejection')
if __name__=='__main__':test()
