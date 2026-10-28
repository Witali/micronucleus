"""Cursor ambiguities must stop the v4.2 plan, without hardware traffic."""
from pathlib import Path
import io
import sys
import types
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import flash_only_programmer35 as host
from tests34.test_host import Mock,prepared_page


class Failure(Mock):
    def __init__(self,mode):
        super().__init__()
        self.mode=mode

    def ctrl_transfer(self,bm,req,value,index,payload,timeout=5000):
        if req==host.REQ_READ8 and self.mode=='read_error':
            # The client cannot know whether the device accepted OUT status
            # and advanced its cursor before this transport error surfaced.
            self.calls.append((bm,req,value,index,payload))
            self.cursor+=payload
            raise OSError('Injected lost READ8 completion')
        result=super().ctrl_transfer(bm,req,value,index,payload,timeout)
        if req==host.REQ_READ8 and self.mode=='short_read':return result[:-1]
        if req==host.REQ_RUN and self.mode=='lost_run_status':
            raise OSError('Injected lost RUN completion after app execution')
        if req==host.REQ_SELECT and self.mode=='nonzero_status':return 1
        return result


def rejected(action):
    try:action()
    except ValueError:return
    raise AssertionError('Unsafe cursor/page operation accepted')


def dead_plan(t,device):
    assert t.cursor is None and not t._valid
    assert t._staged_page is None and t._staged_bytes==0
    assert not t._verified_erased_pages and not t._write_stream
    before=len(device.calls)
    for action in (lambda:t.select(0),lambda:t.erase_page(0),
                   lambda:t.write4(b'ABCD'),lambda:t.read8(),
                   lambda:t.read_memory(0,8),t.run,t.wait_ready):
        rejected(action)
    assert len(device.calls)==before,'Invalid plan emitted more USB traffic'


def check():
    groups=0
    with patch.object(host.time,'sleep',lambda _:None):
        # A lost completion can follow real cursor/buffer effects. Repeating
        # the same WRITE4 would target the next words rather than recover it.
        for final in (False,True):
            device=Mock();t=host.USBTransport(device);prepared_page(t,0x80)
            if final:
                for _ in range(15):t.write4(b'ABCD')
                device.inject_auto_once=True
            else:device.inject_write_once=True
            before=sum(c[1]==host.REQ_WRITE4 for c in device.calls)
            try:t.write4(b'WXYZ')
            except OSError:pass
            else:raise AssertionError('Lost WRITE4 completion was hidden')
            assert sum(c[1]==host.REQ_WRITE4 for c in device.calls)==before+1
            assert device.cursor==(0xc0 if final else 0x84)
            assert device.commits==([0x80] if final else [])
            if final:assert device.flash[0xbc:0xc0]==b'WXYZ'
            dead_plan(t,device);groups+=1

        for mode in ('read_error','short_read','lost_run_status','run_ok','nonzero_status'):
            device=Failure(mode);t=host.USBTransport(device)
            if mode!='nonzero_status':t.select(0x80)
            try:
                if mode in ('read_error','short_read'):t.read8()
                elif mode=='nonzero_status':t.select(0x80)
                else:t.run()
            except (OSError,IOError):assert mode!='run_ok'
            else:assert mode=='run_ok'
            dead_plan(t,device);groups+=1

        # Nothing may inspect, abandon or reselect a partly filled page.
        # These local validation failures emit no command and leave the
        # unfinished page available for the remaining sequential writes.
        device=Mock();t=host.USBTransport(device);prepared_page(t,0x80)
        t.write4(b'ABCD');before=len(device.calls)
        for action in (lambda:t.read8(),lambda:t.read_memory(0x80,8),t.run):rejected(action)
        assert len(device.calls)==before and t.cursor==0x84
        for _ in range(15):t.write4(b'EFGH')
        assert device.commits==[0x80]
        groups+=1

        # Read success advances by the actual count, including odd tails.
        # It invalidates the write stream, so starting WRITE4 needs SELECT.
        device=Mock();t=host.USBTransport(device)
        t.erase_page(0x80);t.wait_ready();host.verify_erased(t,0x80)
        before=len(device.calls);rejected(lambda:t.write4(b'ABCD'))
        assert len(device.calls)==before
        t.select_page(0x80);assert t.read8(3)==b'\xff'*3
        assert t.cursor==device.cursor==0x83
        assert t.read8(1)==b'\xff' and t.cursor==device.cursor==0x84
        before=len(device.calls);rejected(lambda:t.write4(b'ABCD'))
        assert len(device.calls)==before
        t.select_page(0x80);t.write4(b'ABCD');groups+=1

        # A failed selection must not fall back to the previous live plan.
        device=Mock();t=host.USBTransport(device);prepared_page(t,0x80)
        t.write4(b'ABCD');before=len(device.calls)
        rejected(lambda:t.select_page(t.boot_at))
        assert len(device.calls)==before
        dead_plan(t,device);groups+=1

        # Erase verification is required even when a fresh mock starts FF.
        device=Mock();t=host.USBTransport(device);t.select_page(0x80)
        before=len(device.calls);rejected(lambda:t.write4(b'ABCD'))
        assert len(device.calls)==before
        t.erase_page(0x80);before=len(device.calls)
        rejected(lambda:t.write4(b'ABCD'))
        assert len(device.calls)==before;groups+=1

    folder=ROOT/'build/host_cli_defaults'
    folder.mkdir(parents=True,exist_ok=True)
    app=folder/'app.bin';app.write_bytes(bytes((0,0xc0,0x33,0x44)))
    default=host.DEFAULT_FLASH_DELAY_MS/1000
    assert host.program_application.__kwdefaults__['delay']==default
    for extra,expected in (([],default),(['--flash-delay-ms','11.5'],0.0115)):
        fake_usb=types.ModuleType('usb');fake_core=types.ModuleType('usb.core')
        fake_core.find=lambda **kwargs:Mock();fake_usb.core=fake_core
        with patch.dict(sys.modules,{'usb':fake_usb,'usb.core':fake_core}), \
             patch.object(host,'program_application') as program,redirect_stdout(io.StringIO()):
            host.main([str(app),'--execute','--i-have-isp-recovery','--accept-untested-usb',*extra])
        assert program.call_count==1 and program.call_args.kwargs['delay']==expected
    print('PASS v4.2 lost-completion invalidation, no replay/interleaved read, cursor and configurable delay:',groups,'groups')


if __name__=='__main__':check()
