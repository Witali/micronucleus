"""Execute hand-encoded instructions and check ATtiny88 datasheet cycles.

The expected costs below are independent fixture data, not imported from the
timing implementation. Skip tests cover both widths of the following opcode.
"""
from tests35 import ep0_model as h
from tests35.test_ep0_standard import Quiet
from tests35.avr_cycles import ONE,TWO,THREE,FOUR,SKIPS


def install(cpu, pc, words):
    raw=b''.join(word.to_bytes(2,'little') for word in words)
    cpu.flash.memory[pc:pc+len(raw)]=raw
    cpu.flash=h.FlashView(cpu.flash.memory,cpu.base)
    h.dec.decode=h.raw_decode


def reset(cpu, pc):
    cpu.pc=pc;cpu.t=100;cpu.steps=0;cpu.flags=0xa5
    cpu.r[:]=[0]*32;cpu.r[16:18]=[0x35,0x21]
    cpu.r[26:32]=[0x40,1,0x40,1,0x40,1]
    cpu.raw_stack[:]=[0xff,0x7f,0x80,0x01]
    cpu.io={9:2,10:0,11:0,0x1b:0}
    cpu.bus_events=[]


def test():
    art=h.build()
    h.dec.START=art['boot'];h.dec.raw=art['body']
    known=ONE|TWO|THREE|FOUR|SKIPS|{'brbs','brbc'}
    inventory=set();instructions=0
    # Only the two descriptor blocks between RESET and USB_handler are data.
    for start,end in ((art['boot'],art['boot']+2),
                      (art['symbols']['USB_handler'],art['boot']+len(art['body']))):
        at=start
        while at<end:
            ins=h.raw_decode(at)
            assert not ins.unknown and ins.op in known,('unclassified instruction cycles',at,ins.op)
            assert at+ins.size<=end
            inventory.add(ins.op);instructions+=1;at+=ins.size
    cpu=h.CPU(art,Quiet());pc=cpu.base+128
    # Opcodes are written from the instruction formats in DS40002198A.
    cases=(
        ('nop',(0x0000,),1),('wdr',(0x95a8,),1),
        ('ldi',(0xe001,),1),('mov',(0x2f01,),1),('movw',(0x0101,),1),
        ('add',(0x0f01,),1),('adc',(0x1f01,),1),
        ('sub',(0x1b01,),1),('sbc',(0x0b01,),1),
        ('cp',(0x1701,),1),('cpc',(0x0701,),1),('cpi',(0x3000,),1),
        ('subi',(0x5000,),1),('sbci',(0x4000,),1),
        ('and',(0x2301,),1),('eor',(0x2701,),1),('or',(0x2b01,),1),
        ('andi',(0x7000,),1),('ori',(0x6000,),1),
        ('com',(0x9500,),1),('neg',(0x9501,),1),('inc',(0x9503,),1),
        ('dec',(0x950a,),1),('lsr',(0x9506,),1),('ror',(0x9507,),1),
        ('asr',(0x9505,),1),('swap',(0x9502,),1),
        ('in',(0xb109,),1),('out',(0xb90b,),1),
        ('bst',(0xfb00,),1),('bld',(0xf900,),1),('sec',(0x9408,),1),
        ('adiw',(0x9601,),2),('sbiw',(0x9701,),2),
        ('ld',(0x910c,),2),('ld',(0x910d,),2),('ld',(0x910e,),2),
        ('ld',(0x9109,),2),('ld',(0x910a,),2),
        ('ld',(0x9101,),2),('ld',(0x9102,),2),
        ('st',(0x930c,),2),('st',(0x930d,),2),('st',(0x930e,),2),
        ('st',(0x9309,),2),('st',(0x930a,),2),
        ('st',(0x9301,),2),('st',(0x9302,),2),
        ('ldd',(0x810b,),2),('std',(0x8303,),2),
        ('lds',(0x9100,0x0140),2),('sts',(0x9300,0x0140),2),
        ('sbi',(0x9a59,),2),('cbi',(0x9859,),2),
        ('push',(0x930f,),2),('pop',(0x910f,),2),
        ('rjmp',(0xc000,),2),('rcall',(0xd000,),3),
        ('lpm',(0x9104,),3),('lpm',(0x9105,),3),
        ('ret',(0x9508,),4),('spm',(0x95e8,),4),
    )
    count=0
    for name,words,expected in cases:
        install(cpu,pc,words+(0,0))
        for start in (100,100+1/3,100.677328003,24000+16_000_000/1_499_250):
            reset(cpu,pc);cpu.t=start
            ins=cpu.step()
            assert ins.op==name,(name,ins.op,words)
            assert cpu.t==start+expected,(name,cpu.t,expected)
            assert cpu.steps==1
            count+=1
    # Five skip instructions, both decisions, both next-instruction widths.
    # The LDS second word is deliberately also a plausible opcode: it must
    # never be treated as the beginning of another skipped instruction.
    for op,word in (('cpse',0x1301),('sbrc',0xfd00),('sbrs',0xff00),
                    ('sbic',0x9948),('sbis',0x9b48)):
        for following in ((0,), (0x9100,0x9508)):
            for skip in (False,True):
                install(cpu,pc,(word,)+following+(0,))
                reset(cpu,pc)
                if op=='cpse':cpu.r[17]=cpu.r[16] if skip else cpu.r[16]^1
                elif op in ('sbrc','sbrs'):
                    cpu.r[16]=int(skip==(op=='sbrs'))
                else:cpu.io[9]=int(skip==(op=='sbis'))
                ins=cpu.step()
                assert ins.op==op
                assert cpu.pc==pc+2+(2*len(following) if skip else 0)
                assert cpu.t==100+(1+len(following) if skip else 1)
                assert cpu.steps==1
                count+=1
    print('PASS ATtiny88 fixed instruction and 16/32-bit skip cycles:',count,'cases')
    print('PASS every linked code instruction has an explicit cycle class:',instructions,'instructions;',len(inventory),'mnemonics')


if __name__=='__main__':test()
