"""Execute linked AVR words with the repository's independent GPIO/wire model.

The model is shared with compact v3.0, preserving an oracle outside the new
firmware implementation. It excludes analog effects and is not certification.
MICRONUCLEUS_TEST_MODEL_ROOT overrides the model path for isolated audit copies.
"""
from pathlib import Path
from functools import lru_cache
from types import SimpleNamespace
import hashlib,os,sys
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
    def step(self):
        self.executing_pc=self.pc
        # SEC is one classic-AVR cycle and changes only SREG.C. The older
        # shared model omitted it because its original paths never use it.
        if self.flash[self.pc]==0x08 and self.flash[self.pc+1]==0x94:
            self.visited.add(self.pc);self.setflag(0,1)
            self.pc+=2;self.t+=1;self.steps+=1
            return SimpleNamespace(op='sec',operands='',target=None,size=2)
        ins=super().step();self.peak=max(self.peak,len(self.raw_stack));return ins
