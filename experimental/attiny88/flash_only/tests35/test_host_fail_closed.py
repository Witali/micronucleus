"""Page-plan invalidation after uncertain USB completion; no hardware traffic."""
from pathlib import Path
import sys,io,types
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import flash_only_programmer35 as host
from tests34.test_host import Mock


class Failure(Mock):
    def __init__(self,mode):
        super().__init__()
        self.mode=mode

    def ctrl_transfer(self,bm,req,value,index,payload,timeout=5000):
        if req==host.REQ_READ8 and self.mode=='read_error':
            self.page=None
            self.buffer={}
            raise OSError('Injected USB read failure with lost device state')
        result=super().ctrl_transfer(bm,req,value,index,payload,timeout)
        if req==host.REQ_READ8 and self.mode=='short_read':
            return result[:7]
        if req==host.REQ_RUN and self.mode=='lost_run_status':
            raise OSError('Injected lost RUN status after app execution')
        return result


def check():
    assert host.DEFAULT_FLASH_DELAY_MS==7.0
    assert host.program_application.__kwdefaults__['delay']==0.007
    for mode in ('read_error','short_read','lost_run_status','run_ok'):
        device=Failure(mode)
        transport=host.USBTransport(device)
        transport.erase_page(0x80)
        transport.write2(0x80,b'AB')
        try:
            if mode.startswith('read') or mode=='short_read':
                transport.read8_firmware(0x80)
            else:
                transport.run()
        except (OSError,IOError):
            assert mode!='run_ok'
        else:
            assert mode=='run_ok'
        assert transport._selected_page is None and transport._erased_page is None
        assert not transport._pending_words
        before=len(device.calls)
        for action in (lambda:transport.write2(0x82,b'CD'),transport.commit_page):
            try:action()
            except ValueError:pass
            else:raise AssertionError('Stale page plan survived an uncertain transfer')
        assert len(device.calls)==before
    device=Failure('read_ok')
    transport=host.USBTransport(device)
    transport.erase_page(0x80)
    transport.write2(0x80,b'AB')
    transport.read8_firmware(0x80)
    assert transport._selected_page==0x80 and transport._pending_words=={0x80}
    for offset in range(2,64,2):transport.write2(0x80+offset,b'CD')
    assert len(transport._pending_words)==32
    before=len(device.calls)
    try:transport.select_page(transport.boot_at)
    except ValueError:pass
    else:raise AssertionError('Protected page selection accepted')
    try:transport.commit_page()
    except ValueError:pass
    else:raise AssertionError('Invalid SELECT fell back to the prior staged page')
    assert len(device.calls)==before and transport._selected_page is None
    assert transport._erased_page is None and not transport._pending_words
    folder=ROOT/'build/host_cli_defaults'
    folder.mkdir(parents=True,exist_ok=True)
    app=folder/'app.bin'
    app.write_bytes(bytes((0,0xC0,0x33,0x44)))
    for extra,expected in (([],0.007),(['--flash-delay-ms','11.5'],0.0115)):
        fake_usb=types.ModuleType('usb');fake_core=types.ModuleType('usb.core')
        fake_core.find=lambda **kwargs:Mock()
        fake_usb.core=fake_core
        with patch.dict(sys.modules,{'usb':fake_usb,'usb.core':fake_core}), \
             patch.object(host,'program_application') as program,redirect_stdout(io.StringIO()):
            host.main([str(app),'--execute','--i-have-isp-recovery','--accept-untested-usb',*extra])
        assert program.call_count==1 and program.call_args.kwargs['delay']==expected
    print('PASS host RUN/read error and short-read invalidation, successful read preservation, default7ms')


if __name__=='__main__':check()
