"""Later programming must not silently damage an earlier verified page."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import flash_only_programmer35 as host
from tests34.test_host import Mock


class CrossPageFault(Mock):
    def ctrl_transfer(self,bm,request,value,index,payload,timeout=5000):
        selected=self.page
        result=super().ctrl_transfer(bm,request,value,index,payload,timeout)
        if request==host.REQ_COMMIT_PAGE and selected==0x100:
            # Model an address/data fault whose side effect is outside the
            # current page. Its local readback is still exactly correct.
            self.flash[0x20]^=1
        return result


def check():
    original={0:0,1:0xC0,0x20:0x57}
    device=CrossPageFault()
    transport=host.USBTransport(device)
    image=host.pack_application(original,boot_at=transport.boot_at)
    with patch.object(host.time,'sleep',lambda _:None):
        try:
            host.program_application(transport,image)
        except IOError as error:
            assert '0x0000' in str(error),str(error)
        else:
            raise AssertionError('Earlier page corruption escaped final readback')
    assert not device.run_called
    assert len(device.commits)==transport.boot_at//host.PAGE_BYTES
    print('PASS final whole-image readback catches later cross-page corruption')


if __name__=='__main__':check()
