"""Independent instruction semantics needed by receiver qualification.

Microchip AVR Instruction Set Manual DS40002198A, ASR/BRBC/BRBS:
https://ww1.microchip.com/downloads/en/DeviceDoc/AVR-Instruction-Set-Manual-DS40002198A.pdf
The branch outcome matters even when its target is the following instruction.
"""
from tests35 import ep0_model as h
from tests35.test_ep0_standard import Quiet


def install(cpu,pc,word):
    cpu.flash.memory[pc:pc+2]=word.to_bytes(2,'little')
    cpu.flash=h.FlashView(cpu.flash.memory,cpu.base)


def begin(cpu,pc,flags):
    cpu.pc=pc;cpu.flags=flags;cpu.t=100;cpu.steps=0


def test():
    art=h.build();cpu=h.CPU(art,Quiet());pc=cpu.base+128
    pattern=[(index*37+11)&255 for index in range(32)]
    asr_cases=0
    for register in range(32):
        install(cpu,pc,0x9405|(register<<4));cpu.r=pattern.copy()
        for value in range(256):
            # Signed division supplies the result oracle independently of
            # the interpreter's bit-shift implementation.
            signed=value-256 if value>=128 else value
            result=(signed//2)&255
            carry=value%2;negative=int(result>=128)
            overflow=negative^carry;sign=negative^overflow
            affected=carry|(int(result==0)<<1)|(negative<<2)|(overflow<<3)|(sign<<4)
            for flags in range(256):
                begin(cpu,pc,flags);cpu.r[register]=value
                instruction=cpu.step()
                assert instruction.op=='asr' and cpu.r[register]==result
                assert cpu.flags==(flags&0xe0)|affected,(register,value,flags,cpu.flags)
                assert cpu.pc==pc+2 and cpu.t==101 and cpu.steps==1
                asr_cases+=1
            assert cpu.r[:register]+cpu.r[register+1:]==pattern[:register]+pattern[register+1:]
    print('PASS ASR all registers, operands and initial SREG states:',asr_cases,'cases',flush=True)

    # Include nonzero offsets to check delegation to the unchanged backend.
    # The zero-offset case would be timed incorrectly by comparing final PC
    # with target PC: both outcomes reach the following instruction.
    h.dec.decode=h.raw_decode
    branch_cases=0
    for branch_if_set in (False,True):
        for bit in range(8):
            for offset in (-64,-1,0,1,63):
                word=(0xf000 if branch_if_set else 0xf400)|((offset&127)<<3)|bit
                install(cpu,pc,word);cpu.r=pattern.copy()
                for flags in range(256):
                    begin(cpu,pc,flags)
                    taken=bool((flags>>bit)&1)==branch_if_set
                    instruction=cpu.step()
                    assert instruction.op==('brbs' if branch_if_set else 'brbc')
                    assert cpu.pc==pc+2+(2*offset if taken else 0)
                    assert cpu.t==100+(2 if taken else 1)
                    assert cpu.flags==flags and cpu.r==pattern and cpu.steps==1
                    branch_cases+=1
    assert not cpu.bus_events
    print('PASS BRBS/BRBC zero and signed offsets, all flags and SREG states:',branch_cases,'cases',flush=True)


if __name__=='__main__':test()
