"""USB protocol v5.5 host cache and automatic cursor tests using a target mock.
Not real USB tests; USB ACK/retransmission remains an unverified dependency.
"""
import sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import compact_programmer as h
from tests25.test25_host_planner import USBMock

def test():
    for ver,(name,boot,code) in h.USB_PROFILES.items():
        dev=USBMock(boot_at=boot);dev.bcdDevice=ver
        dev.flash[:]=bytes(i*71&255 for i in range(len(dev.flash)))
        dev.eep[:]=bytes(i*17&255 for i in range(64))
        tr=h.USBTransport(dev)
        raw=tr.read8(0)
        assert raw==bytes(dev.flash[:8])
        for start in range(8,256,8):
            assert tr.read8(start)==bytes(dev.flash[start:start+8])
        reads=[c for c in dev.calls if c[1]==h.REQ_READ8]
        selects=[c for c in dev.calls if c[1]==h.REQ_SET_ADDRESS]
        assert len(reads)==32 and len(selects)==1,(name,len(reads),len(selects))
        assert all(v==0 and ind==0 for _,_,v,ind in reads),name
        # Disjoint positions and switching memory force exactly one new SELECT.
        assert tr.read8(0,eeprom=True)==bytes(dev.eep[:8])
        assert tr.read8(8,eeprom=True)==bytes(dev.eep[8:16])
        assert len([c for c in dev.calls if c[1]==h.REQ_SET_ADDRESS])==2
        assert tr.read8(0)==bytes(dev.flash[:8])
        assert len([c for c in dev.calls if c[1]==h.REQ_SET_ADDRESS])==3
        # On USB failure, forget host cursor and issue fresh SELECT.
        first=dev.ctrl_transfer
        def fail_once(bm,cmd,*args,**kwargs):
            if bm==0xC0 and cmd==h.REQ_READ8:
                dev.ctrl_transfer=first
                raise IOError('injected USB data loss')
            return first(bm,cmd,*args,**kwargs)
        dev.ctrl_transfer=fail_once
        try:tr.read8(8)
        except IOError:pass
        else:raise AssertionError('Simulated USB failure was not propagated')
        assert tr._cursor is None
        assert tr.read8(8)==bytes(dev.flash[8:16])
        assert len([c for c in dev.calls if c[1]==h.REQ_SET_ADDRESS])==4
        # WRITE4 also increments cursor, no SET needed for consecutive writes.
        dev.flash[:64]=b'\xff'*64
        tr.set_address(0,erase=True)
        selects_before=len([c for c in dev.calls if c[1] in (h.REQ_SET_ADDRESS,h.REQ_SELECT_ERASE)])
        for a in range(0,64,4):tr.write4(bytes((a+i)&255 for i in range(4)))
        assert len([c for c in dev.calls if c[1] in (h.REQ_SET_ADDRESS,h.REQ_SELECT_ERASE)])==selects_before
        assert dev.flash[:64]==bytes(range(64))
        assert tr._cursor==('flash',64)
        # First readback needs a SELECT; subsequent READ8 packets do not.
        assert tr.read8(0)==bytes(range(8))
        assert tr.read8(8)==bytes(range(8,16))
        assert tr._cursor==('flash',16)
        expected=bytes((i*13)&255 for i in range(64))
        before=len(dev.calls)
        with patch.object(h.time,'sleep'):
            h.program_eeprom_stream(tr,expected)
        commands=[v[1] for v in dev.calls[before:]]
        assert commands.count(h.REQ_WRITE4)==16
        assert commands.count(h.REQ_READ8)==8
        # Once to select for write, once to rewind for readback.
        assert commands.count(h.REQ_SET_ADDRESS)==2,commands
        assert bytes(dev.eep)==expected
        print('PASS',name,'READ8/WRITE4 automatic cursor and resync')
    print('PASS v5.5 sequential transport and error recovery mock')

if __name__=='__main__':test()
