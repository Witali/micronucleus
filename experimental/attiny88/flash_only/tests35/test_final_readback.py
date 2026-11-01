"""An automatic later-page write must not hide earlier-page corruption."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import flash_only_programmer35 as host
from tests34.test_host import Mock


class CrossPageFault(Mock):
    def ctrl_transfer(self,bm,request,value,index,payload,timeout=5000):
        count=len(self.commits)
        result=super().ctrl_transfer(bm,request,value,index,payload,timeout)
        if len(self.commits)!=count and self.commits[-1]==0x100:
            # Model an address/data fault outside the auto-written page.
            # That page's immediate readback remains exactly correct.
            self.flash[0x20]^=1
        return result


def check():
    device=CrossPageFault();transport=host.USBTransport(device)
    image=host.pack_application({0:0,1:0xc0,0x20:0x57},boot_at=transport.boot_at)
    with patch.object(host.time,'sleep',lambda _:None):
        try:host.program_application(transport,image)
        except IOError as error:assert '0x0000' in str(error),str(error)
        else:raise AssertionError('Earlier page corruption escaped final readback')
    assert not device.run_called and not transport._valid
    assert len(device.commits)==transport.boot_at//host.PAGE_BYTES
    print('PASS v4.2 final whole-image readback catches later auto-write cross-page corruption')


if __name__=='__main__':check()
