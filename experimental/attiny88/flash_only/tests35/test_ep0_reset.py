"""Run reset, replacement SETUP and idle-handoff rules through actual opcodes."""
from pathlib import Path
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,reset
from tests35.test_setup_pending_marker import seeded,receive,wave_for

HERE=Path(__file__).resolve().parent

def quiet():return h.Wave(b'',start=1_000_000)

def replacement(art,command):
    bind(art);cpu=seeded(art,command)
    assert receive(cpu,wave_for())==[(2,0xd2)]
    assert cpu.r[3]==11 and cpu.m[0x10f]==0x5a
    cpu.raw_stack.clear();cpu.pc=cpu.labels['usb_control_process_received_packet']
    for _ in range(200):
        if cpu.pc==cpu.labels['usb_standard_dispatch']:
            return dict(command=cpu.r[3],peak=cpu.peak,stack=cpu.raw_stack)
        cpu.step()
    raise AssertionError('Replacement SETUP did not dispatch')

def exit_action(art,tx_length,auto=False):
    bind(art);cpu=h.CPU(art,quiet());cpu.raw_stack.clear()
    cpu.pc=cpu.labels['bootloader_check_idle_timeout' if auto else 'bootloader_start_application'];cpu.t=0
    cpu.r[6:8]=[255,3]
    cpu.m[0x10F]=tx_length
    cpu.flash.memory[art['boot']-3]=0
    for _ in range(200):
        if cpu.pc==cpu.labels['usb_tx_prepare_pending_reply']:return 'wait'
        if cpu.pc==cpu.labels['led_exit']:return 'exit'
        cpu.step()
    raise AssertionError('App exit did not reach its owner')

def test():
    art=h.build();cases=0
    for command in (3,4,5,64,11):
        for rx_length in (0,1,11,255):
            new=reset(art,command,rx_length)
            assert new['action']=='idle' and new['command']==0,new
            regs=new['reset']['registers'];ctx=bytes.fromhex(new['reset']['context'])
            assert regs[2:4]==[0,0] and regs[24:26]==[0,0] and regs[5]==255
            # R3 is the live accepted-SETUP owner; offset18 is dead SRAM.
            assert [ctx[offset] for offset in (12,19,20,21)]==[0]*4
            assert ctx[15]==0x5A and ctx[0]==255 and new['reset']['samples']==100
            cases+=1
        assert replacement(art,command)['command']==0
        cases+=1
    for length in (4,8,12):
        for auto in (False,True):
            assert exit_action(art,length,auto)=='wait';cases+=1
    assert exit_action(art,0x5A)=='exit';cases+=1
    print('PASS reset/replacement SETUP/idle handoff:',cases,'emitted-AVR cases')
if __name__=='__main__':test()
