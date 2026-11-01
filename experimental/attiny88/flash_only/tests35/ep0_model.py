"""Execute linked AVR words with the repository's independent GPIO/wire model.

The model is shared with compact v3.0, preserving an oracle outside the new
firmware implementation. It excludes analog effects and is not certification.
MICRONUCLEUS_TEST_MODEL_ROOT overrides the model path for isolated audit copies.
"""
from pathlib import Path
from functools import lru_cache
from types import SimpleNamespace
import hashlib,os,sys
from tests35.avr_cycles import cycles as instruction_cycles, SKIPS
ROOT=Path(__file__).resolve().parents[1]
BACKEND=Path(os.environ.get('MICRONUCLEUS_TEST_MODEL_ROOT',ROOT.parent/'compact'))
saved_argv=sys.argv[:]
sys.path.insert(0,str(BACKEND))
from tests27.waveform_model import Timed,FlashView,SynchronizedPinIO,Wave,token,data_packet,J,K,dec
sys.argv[:]=saved_argv
sys.path.insert(0,str(ROOT))
from check_build import build as linked_build
raw_decode=getattr(dec.decode,'__wrapped__',dec.decode)

@lru_cache(maxsize=16)
def build(source='source',mode='NONE',boot=None):
    # Semantic placement has enough room for audit fixes; release fit/profile
    # assertions remain in the variant's independent build verification.
    if boot is None:
        from host.profiles import BOOT_AT
        boot=BOOT_AT
    art=linked_build(source+'/micronucleus_t88_compact.S',mode=mode,boot=boot)
    directory=ROOT/'build/ep0_model'/source
    directory.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(art['body']).hexdigest()
    binary=directory/(mode+'_'+digest+'.body.bin')
    if not binary.exists():
        temporary=binary.with_suffix('.'+str(os.getpid())+'.tmp')
        temporary.write_bytes(art['body'])
        temporary.replace(binary)
    art.update(obj=art['obj'],bin=binary,size=len(art['body']),sha256=digest)
    return art

class Calls:
    def __init__(self,raw):self.raw=raw
    def append(self,pc):
        pc//=2;self.raw.extend((pc&255,pc>>8))
    def pop(self):
        hi=self.raw.pop();lo=self.raw.pop();return (lo|hi<<8)*2
    def __bool__(self):return bool(self.raw)
class Pushes:
    def __init__(self,raw):self.raw=raw
    def append(self,v):self.raw.append(v)
    def pop(self):return self.raw.pop()
class CPU(Timed):
    def __init__(self,art,wave,entry=8):
        registers=[0]*32;registers[28:32]=[0,1,0,1];registers[21]=0xA0
        registers[8]=registers[10]=0x10  # cold address-zero token CRC byte
        meta=dict(name='EP0 semantic wire regression',start=art['boot'],o=art['obj'],bin=art['bin'],symbols=art['symbols'],step_limit=100000)
        super().__init__(meta,dict(memory=bytearray(0x300),registers=registers))
        self.flash=FlashView(self.flash,self.base)
        self.raw_stack=[];self.calls=Calls(self.raw_stack);self.push_stack=Pushes(self.raw_stack)
        self.calls.append(0xFFFE);self.pc=self.labels['USB_handler'];self.t=entry
        self.io=SynchronizedPinIO(self,wave);self.io.cleared_at=-1;self.peak=2
    def memread(self,address):return self.r[address] if address<32 else super().memread(address)
    def memwrite(self,address,value):
        if address<32:self.r[address]=value&255
        else:super().memwrite(address,value)
    def add8(self,d,k,carry=0,oldz=False):
        # ADC sets Z from this byte's result; unlike SBC/CPC it does not
        # preserve a previous zero. Keep the archived backend unchanged.
        return super().add8(d,k,carry,oldz=False)
    def step(self):
        self.executing_pc=self.pc
        word=self.flash[self.pc]|self.flash[self.pc+1]<<8
        before_flags=self.flags;before_time=self.t
        # A branch to the following instruction has the same final PC for
        # both outcomes. Its taken condition still determines 1/2 cycles;
        # the inherited timing layer cannot infer that condition from PC.
        if word&0xfff8 in (0xf000,0xf400):
            bit=word&7;branch_if_set=word&0xfff8==0xf000
            taken=bool(self.flag(bit))==branch_if_set
            self.visited.add(self.pc);self.pc+=2
            self.t+=2 if taken else 1;self.steps+=1
            return SimpleNamespace(op='brbs' if branch_if_set else 'brbc',
                                   operands=str(bit)+',',target=self.pc,size=2)
        # ASR is used by the table-free EOF mask classifier. It preserves
        # the sign bit and SREG.H/T/I; V=N xor C and S=N xor V.
        if word&0xfe0f==0x9405:
            index=(word>>4)&31;old=self.r[index]
            value=(old>>1)|(old&0x80)
            self.r[index]=value
            self.setflag(0,old&1);self.setflag(1,value==0)
            self.setflag(2,value&0x80)
            self.setflag(3,self.flag(2)^self.flag(0))
            self.setflag(4,self.flag(2)^self.flag(3))
            self.visited.add(self.pc);self.pc+=2;self.t+=1;self.steps+=1
            return SimpleNamespace(op='asr',operands='r'+str(index),target=None,size=2)
        # SEC is one classic-AVR cycle and changes only SREG.C. The older
        # shared model omitted it because its original paths never use it.
        if word==0x9408:
            self.visited.add(self.pc);self.setflag(0,1)
            self.pc+=2;self.t+=1;self.steps+=1
            return SimpleNamespace(op='sec',operands='',target=None,size=2)
        old_neg=self.r[(word>>4)&31] if word&0xfe0f==0x9401 else None
        ins=super().step()
        if old_neg is not None:
            # NEG's half borrow is result bit3 OR original operand bit3.
            self.setflag(5,(self.r[(word>>4)&31]|old_neg)&8)
        next_size=dec.decode(ins.address+ins.size).size if ins.op in SKIPS else None
        expected=instruction_cycles(ins,before_flags,self.pc,next_size)
        # Compare the final clock against the same addition, rather than
        # subtracting two fractional timestamps and losing a low-order bit.
        if self.t!=before_time+expected:
            raise AssertionError(('AVR instruction cycles',ins.op,self.t-before_time,expected))
        self.peak=max(self.peak,len(self.raw_stack));return ins
