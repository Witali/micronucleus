"""Startup and bus-reset initialization must invalidate every selected-page poison."""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_standard import Quiet


def initialized(art,low):
    bind(art)
    cpu=h.CPU(art,Quiet())
    cpu.raw_stack.clear()
    # The disconnect counter has reached zero and the last SRAM byte has
    # been cleared. Deliberately poison context/registers here so the shared
    # initializer, rather than the model's zero defaults, proves its contract.
    cpu.pc=cpu.labels['startup_check_sram_end']
    cpu.r[1]=0;cpu.r[24:26]=[0,0];cpu.r[28:32]=[0,1,0x60,0]
    cpu.r[2:6]=[12,5,low,0xa5];cpu.r[6:8]=[0xa5,0x5a];cpu.r[11]=0xe0
    cpu.r[8]=0xa5
    cpu.m[0x100:0x12c]=bytes((i*37+low)&255 for i in range(44))
    visited=set()
    for _ in range(100):
        visited.add(cpu.pc)
        if cpu.pc==cpu.labels['led_init']:break
        cpu.step()
    else:raise AssertionError('startup initializer did not return')
    assert cpu.labels['bootloader_reset_control_state'] in visited
    assert not cpu.raw_stack
    assert cpu.r[2:4]==[0,0] and cpu.r[5]==255
    assert cpu.r[6:8]==[0,0] and cpu.r[8]==0x10 and cpu.r[11]==0
    # Historical receive fields remain poisoned: only R3 owns new SETUP.
    # The Flash guard sweep below must still reject every page-low poison.
    assert [cpu.m[0x100+i] for i in (12,19,20,21)]==[0]*4
    assert cpu.m[0x10f]==0x5a and cpu.m[0x100]==255
    assert cpu.word(28)==0x100 and cpu.word(30)==0x60
    return cpu


def check():
    cases=0
    for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        art=h.build(mode=mode)
        for low in range(256):
            cpu=initialized(art,low)
            for command in (3,5):
                cpu.pc=cpu.labels['bootloader_dispatch_command']
                cpu.r[3]=command
                for _ in range(100):
                    if cpu.pc==cpu.labels['bootloader_clear_command']:break
                    at=cpu.pc-art['boot']
                    assert art['body'][at:at+2]!=b'\xe8\x95',('unselected SPM',low,command)
                    cpu.step()
                else:raise AssertionError('unselected erase/commit did not abort')
                assert cpu.r[5]==255
                cases+=1
    print('PASS',cases,'poisoned-startup unselected erase/commit cases across all low bytes and LED modes')


if __name__=='__main__':check()
