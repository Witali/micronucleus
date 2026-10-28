"""A hardware RESET has no selected Flash page; COMMIT must fail closed."""
from pathlib import Path
import sys
from functools import lru_cache

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_build import build
from tests import avr_exec as model

model.decode=lru_cache(maxsize=32)(model.decode)


def check():
    cases=0
    for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        artifact=build('source/micronucleus_t88_compact.S',mode=mode,boot=0x1BC0)
        sample=model.AVRExec(artifact)
        candidates=[pc for pc,(op,arg,_) in sample.ins.items()
                    if artifact['symbols']['startup']<=pc<artifact['symbols']['led_init']
                    and op=='ldi' and arg=='r24, 0xff']
        assert len(candidates)==1
        start=candidates[0]
        assert sample.ins[start+2][:2]==('std','Y+0, r24')
        assert sample.ins[start+4][:2]==('mov','r5, r24')
        for low in range(256):
            machine=model.AVRExec(artifact)
            machine.sym=machine.sym.copy()
            machine.sym['checked_startup_page_state']=start+6
            machine.r[1],machine.r[29],machine.r[5]=0,1,0xA5
            assert machine.run(start,stop=('checked_startup_page_state',))=='stop'
            assert machine.r[5]==0xFF and machine.ram[0]==0xFF
            for command in (3,5):
                machine.r[3],machine.r[4]=command,low
                machine.ram[15]=0x5A
                machine.spms.clear()
                assert machine.run('bootloader_dispatch_command',stop=('bootloader_clear_command',))=='stop'
                assert not machine.spms and machine.r[5]==0xFF
                cases+=1
    print('PASS',cases,'RESET-unselected erase/commit cases across all low-byte poisons and LED modes')


if __name__=='__main__':check()
