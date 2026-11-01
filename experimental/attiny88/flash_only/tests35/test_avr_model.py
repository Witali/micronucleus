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

    # ADC does not chain the old Z flag. Mathematical signed/range and
    # nibble arithmetic provide independent flag oracles for every operand.
    install(cpu,pc,0x1f01)  # ADC R16,R17
    adc_cases=0
    for left in range(256):
        for right in range(256):
            for carry in (0,1):
                total=left+right+carry;result=total%256
                signed=(left if left<128 else left-256)+(right if right<128 else right-256)+carry
                overflow=int(not -128<=signed<=127);negative=int(result>=128)
                expected=(int(total>=256)|(int(result==0)<<1)|(negative<<2)|
                          (overflow<<3)|((negative^overflow)<<4)|
                          (int((left%16)+(right%16)+carry>=16)<<5))
                for old_zero in (0,1):
                    for upper in (0,64,128,192):
                        begin(cpu,pc,upper|0x3c|(old_zero<<1)|carry)
                        cpu.r[16:18]=[left,right]
                        instruction=cpu.step()
                        assert instruction.op=='adc' and cpu.r[16]==result
                        assert cpu.r[17]==right and cpu.flags==upper|expected
                        assert cpu.t==101 and cpu.pc==pc+2 and cpu.steps==1
                        adc_cases+=1
    print('PASS ADC all operand pairs, carry, prior Z and preserved T/I:',adc_cases,'cases',flush=True)

    install(cpu,pc,0x9501)  # NEG R16, including its half-carry flag.
    neg_cases=0
    for value in range(256):
        result=(-value)%256;negative=int(result>=128);overflow=int(value==128)
        affected=(int(value!=0)|(int(result==0)<<1)|(negative<<2)|
                  (overflow<<3)|((negative^overflow)<<4)|
                  (int(bool((value|result)&8))<<5))
        for flags in range(256):
            begin(cpu,pc,flags);cpu.r[16]=value
            instruction=cpu.step()
            assert instruction.op=='neg' and cpu.r[16]==result
            assert cpu.flags==(flags&0xc0)|affected
            assert cpu.t==101 and cpu.pc==pc+2 and cpu.steps==1
            neg_cases+=1
    print('PASS NEG all operands and initial SREG states:',neg_cases,'cases',flush=True)


if __name__=='__main__':test()
