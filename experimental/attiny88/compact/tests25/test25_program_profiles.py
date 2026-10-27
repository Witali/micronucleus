"""Full offline 20-page Flash/EEPROM host transaction mock for all USB BCD variants."""
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
import test25_host_planner as mock
from host import compact_programmer as h

def test():
    for version,(name,boot,_) in h.USB_PROFILES.items():
        dev=mock.USBMock(boot_at=boot)
        dev.bcdDevice=version
        tr=h.USBTransport(dev)
        app=h.pack_application({0:0x02,1:0xc0,0x101:0xb5,boot-5:0x96},boot_at=boot)
        with patch.object(h.time,'sleep'):
            h.program_application(tr,app)
            for adr in range(0,64,4):
                h.program_eeprom_block(tr,adr,bytes(((adr+i)*7)&255 for i in range(4)))
        assert bytes(dev.flash[:boot])==app.image
        assert bytes(dev.eep)==bytes(((a)*7)&255 for a in range(64))
        assert h.read_flash(tr)==app.image[:boot-4]
        assert h.read_eeprom(tr)==bytes(((a)*7)&255 for a in range(64))
        assert not any(v[1] in (h.REQ_WRITE4,h.REQ_SELECT_ERASE) for v in dev.calls if v[0]==0xc0)
        print('PASS full host mock',name,'v',hex(version),'app',boot-4)

if __name__=='__main__':test()
