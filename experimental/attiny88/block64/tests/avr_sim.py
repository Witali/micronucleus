"""Instruction-level AVR test interpreter for Block64 code outside the V-USB bit engine.
Not a physical-level USB emulator; SPM/EEPROM modeled at functional level.
"""
from __future__ import annotations
from pathlib import Path
import importlib.util, re, subprocess, sys
from dataclasses import dataclass
ROOT=Path(__file__).resolve().parent.parent
BOOT=0x19c0
spec=importlib.util.spec_from_file_location('block_decoder',Path(__file__).with_name('avr_decoder.py'))
D=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=D
spec.loader.exec_module(D)
MEM_STATE=0x0139;MEM_TYPE=0x0130;MEM_ADDR_LO=0x0131;MEM_ADDR_HI=0x0132
MEM_REMAIN=0x0133;MEM_INDEX=0x0134;MEM_TOTAL=0x0135;MEM_STATUS=0x0138
MEM_PROGRESS=0x0136;MEM_EXPECT_PID=0x0137;MEM_BUFFER=0x0140
ST_IDLE=0;ST_DONE=1;ST_ERROR=2;ST_RUN=3;ST_RECEIVE=4;ST_WRITE_EEPROM=5;ST_FLASH_WAIT_PREP=6;ST_SPM_WAIT_SENT=7
# Deterministic strict-mode assumptions at 16 MHz, not measured device times.
# Microchip Table 5-4 gives 3.4 ms typical atomic EEPROM programming;
# Table 19-1 gives 3.7..4.5 ms for Flash erase/write.
MODEL_EEPROM_PROGRAM_CYCLES = 54_400
MODEL_FLASH_PROGRAM_CYCLES = 72_000
EEPROM_READ_STALL_CYCLES = 4
EEPROM_WRITE_START_STALL_CYCLES = 2
NVM_ENABLE_WINDOW_CYCLES = 4

def syms(obj=ROOT/'build/block64.o'):
    out={}
    for line in subprocess.check_output(['llvm-objdump','-t',str(obj)],text=True).splitlines():
        m=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',line)
        if m: out[m.group(2)]=int(m.group(1),16)
    return out

class CPU:
    def __init__(self, image:bytes|None=None, EEPROM:bytes|None=None, *,
                 strict_nvm=False, selfprgen_fuse_programmed=None,
                 eeprom_program_cycles=MODEL_EEPROM_PROGRAM_CYCLES,
                 flash_program_cycles=MODEL_FLASH_PROGRAM_CYCLES):
        if strict_nvm and selfprgen_fuse_programmed is None:
            raise ValueError('Strict NVM mode requires an explicit SELFPRGEN fuse assumption')
        if eeprom_program_cycles <= 0 or flash_program_cycles <= 0:
            raise ValueError('Modeled NVM durations must be positive')
        self.labels=syms()
        self.flash=bytearray([0xff]*8192 if image is None else image)
        self.io={0x1f:0,0x20:0,0x21:0,0x37:0}
        self.r=[0]*32
        self.r[28]=0;self.r[29]=1
        self.pc=0
        self.sreg=0
        self.mem=bytearray(0x300)
        self.mem[0x010f]=0x5a
        self.mem[0x0100]=0xff
        self.eeprom=bytearray([0xff]*64 if EEPROM is None else EEPROM)
        self.ep_busy_cycles=0
        self.spm_buffer=bytearray([0xff]*64)
        self.spm_oplog=[]
        self.lpm_oplog=[]
        self.eeprom_oplog=[]
        self.usb_timing_trace=[]
        self.stack=[]
        self.cycles=0
        self.ops=0
        self.done_at=None
        self.started = False
        self.strict_nvm = strict_nvm
        self.selfprgen_fuse_programmed = selfprgen_fuse_programmed
        self.eeprom_program_cycles = eeprom_program_cycles
        self.flash_program_cycles = flash_program_cycles
        self.nvm_events = []
        self._spm_armed_at = None
        self._eempe_armed_at = None
        self._eeprom_pending = None
        self._eeprom_ready_at = None
        self._spm_loaded_words = set()
    def decode(self, addr):
        D.START=BOOT
        D.raw=self.codebody
        return D.decode(addr)
    @property
    def codebody(self):return self.flash[BOOT:]
    def flag(self,b):return bool(self.sreg&(1<<b))
    def flagset(self,b,on):self.sreg=(self.sreg|(1<<b)) if on else (self.sreg&~(1<<b))
    def znvs(self,result,overflow=False,oldzero=None):
        self.flagset(1, result==0 if oldzero is None else oldzero and result==0)
        self.flagset(2,bool(result&128))
        self.flagset(3,overflow)
        self.flagset(4,bool(result&128)^overflow)
    def logic(self,v):self.znvs(v,False)
    def subtract(self,d,r,borrow=0,zerochain=False):
        # Keep the borrow as a ninth bit: Rr=0xFF with carry-in 1
        # must not wrap to zero before computing C/H/V for SBC/CPC.
        result=(d-r-borrow)&255
        overflow=bool(((d^r)&(d^result))&128)
        carry=(d < r+borrow)
        self.flagset(0,carry)
        zprev=self.flag(1) if zerochain else None
        self.znvs(result,overflow,zprev)
        self.flagset(5, (d&15) < ((r&15)+borrow))
        return result
    def add(self,d,r,carry=0,zerochain=False):
        v=d+r+carry;result=v&255
        overflow=bool((~(d^r)&(d^result))&128)
        self.flagset(0,v>255)
        zprev=self.flag(1) if zerochain else None
        self.znvs(result,overflow,zprev)
        self.flagset(5,bool(((d& r)|(r&~result)|(~result&d))&8))
        return result
    @staticmethod
    def reg(r):return int(r[1:])
    @staticmethod
    def imm(s):return int(s,0)
    def read_io(self, addr):
        if self.strict_nvm:
            self._nvm_tick()
        if addr == 0x1f and self.ep_busy_cycles>0:return self.io.get(addr,0)|2
        return self.io.get(addr,0)
    def write_io(self, addr,val):
        val &= 255
        if self.strict_nvm and addr in (0x1f,0x20,0x21,0x37):
            self._strict_write_io(addr,val)
            return
        # EECR.EERE is a write-one strobe. ATtiny88 permits OUT as well as
        # SBI to trigger the read; hardware clears EERE automatically.
        if addr == 0x1f and (val & 1):
            assert not (self.read_io(addr) & 2), 'EERE during EEPROM write'
            self.io[0x20] = self.eeprom[self.io[0x21]]
            val &= 0xfe
        self.io[addr] = val
    def _nvm_tick(self):
        if self._eeprom_pending is not None and self.cycles >= self._eeprom_ready_at:
            address,value = self._eeprom_pending
            self.eeprom[address] = value
            self.eeprom_oplog.append((address,value))
            self.nvm_events.append(('eeprom_complete',self.cycles,address,value))
            self._eeprom_pending = None
            self._eeprom_ready_at = None
            self.io[0x1f] &= ~2
        if self._eempe_armed_at is not None and self.cycles-self._eempe_armed_at > NVM_ENABLE_WINDOW_CYCLES:
            self.io[0x1f] &= ~4
            self._eempe_armed_at = None
        if self._spm_armed_at is not None and self.cycles-self._spm_armed_at > NVM_ENABLE_WINDOW_CYCLES:
            self.io[0x37] = 0
            self._spm_armed_at = None
    def advance_nvm_cycles(self, cycles):
        """Advance assumed peripheral time without executing AVR instructions."""
        assert self.strict_nvm and cycles >= 0
        self.cycles += cycles
        self._nvm_tick()
    def _clear_spm_buffer(self):
        self.spm_buffer[:] = b'\xff'*64
        self._spm_loaded_words.clear()
    def _strict_write_io(self, addr,val):
        self._nvm_tick()
        busy = bool(self.io.get(0x1f,0)&2)
        if addr == 0x37:
            # EEPROM programming blocks writes to SPMCSR (datasheet19.1.1).
            if busy:
                self.nvm_events.append(('spmcsr_blocked',self.cycles,val))
                return
            self.io[addr] = val
            self._spm_armed_at = self.cycles if val&1 else None
            return
        if addr in (0x20,0x21):
            assert not busy, 'Changing EEPROM address/data during programming is unsupported'
            self.io[addr] = val
            return
        if busy:
            assert not val&1, 'EERE during EEPROM write'
            # Mode bits cannot be changed while programming. No new write starts.
            return
        if val&1:
            address = self.io[0x21]
            assert address < len(self.eeprom)
            self.io[0x20] = self.eeprom[address]
            self.io[addr] = val&~1
            self.nvm_events.append(('eeprom_read',self.cycles,address))
            self.advance_nvm_cycles(EEPROM_READ_STALL_CYCLES)
            return
        if val&2:
            if self._eempe_armed_at is None or self.cycles-self._eempe_armed_at > NVM_ENABLE_WINDOW_CYCLES:
                self.io[addr] = val&~6
                self.nvm_events.append(('eeprom_enable_expired',self.cycles))
                return
            assert not self.io.get(0x37,0)&1, 'EEPROM start while SELFPRGEN is active'
            assert val&0x30 == 0, 'Strict model implements atomic erase+write mode only'
            address,value = self.io[0x21],self.io[0x20]
            assert address < len(self.eeprom)
            self.io[addr] = (val&~4)|2
            self._eempe_armed_at = None
            self._eeprom_pending = (address,value)
            self._eeprom_ready_at = self.cycles+self.eeprom_program_cycles
            self._clear_spm_buffer()  # EEPROM write destroys staged Flash words.
            self.nvm_events.append(('eeprom_start',self.cycles,address,value))
            self.advance_nvm_cycles(EEPROM_WRITE_START_STALL_CYCLES)
            return
        self.io[addr] = val
        self._eempe_armed_at = self.cycles if val&4 else None
    def _strict_spm(self, address, command):
        self._nvm_tick()
        if not self.selfprgen_fuse_programmed or self.io.get(0x1f,0)&2 or not self.io.get(0x37,0)&1:
            self.nvm_events.append(('spm_ignored',self.cycles,command))
            self.io[0x37] = 0
            self._spm_armed_at = None
            return
        page = address&~63
        assert 0 <= page and page+64 <= len(self.flash)
        if command == 0x11:
            self._clear_spm_buffer()
            self.spm_oplog.append(('buffer_clear',page))
        elif command == 1:
            word = (address&63)&~1  # Hardware ignores Z0 for SPM page loading.
            assert word not in self._spm_loaded_words, 'Duplicate temporary-buffer word load'
            self._spm_loaded_words.add(word)
            self.spm_buffer[word:word+2] = bytes(self.r[0:2])
            self.spm_oplog.append(('load',page+word,self.r[0],self.r[1]))
        elif command == 3:
            self.flash[page:page+64] = b'\xff'*64
            self.spm_oplog.append(('erase',page))
            self.advance_nvm_cycles(self.flash_program_cycles)
        elif command == 5:
            assert address%64 == 0, 'Unaligned SPM Page Write'
            # The documented algorithm requires erase first. Repeated writes
            # without erase are unsupported; do not invent 0->1 or AND results.
            assert self.flash[page:page+64] == b'\xff'*64, 'Flash Page Write requires an erased page'
            self.flash[page:page+64] = self.spm_buffer
            self.spm_oplog.append(('write',page))
            self._clear_spm_buffer()
            self.advance_nvm_cycles(self.flash_program_cycles)
        else:
            assert command not in (0x09,), 'Fuse/lock access is outside this strict model'
            self.nvm_events.append(('spm_ignored',self.cycles,command))
        self.io[0x37] = 0
        self._spm_armed_at = None
    def ram(self,addr):return self.mem[addr]
    def set_setup(self,request,addr=0,length=1,memtype=0,request_type=0xc0):
        self.r[28]=0; self.r[29]=1;self.r[25]=request
        for o,v in [(23,request_type),(24,request),(25,addr&255),(26,addr>>8),(27,memtype&255),(28,memtype>>8),(29,length&255),(30,length>>8)]:self.mem[0x0100+o]=v
    def run_from(self, name, stop_at=(), count=2000, execute_ret=False):
        self.pc=self.labels.get(name,name if isinstance(name,int) else None)
        assert self.pc is not None,name
        return self.run(stop_at,count,execute_ret)
    def run(self,stop_at=(),count=4000,execute_ret=False):
        stop={self.labels[x] for x in stop_at if x in self.labels}
        for _ in range(count):
            if self.pc in stop: return self.pc
            i=self.decode(self.pc)
            if i.unknown:raise AssertionError(('unsupported',hex(self.pc),hex(i.words[0])))
            self.pc+=i.size
            op=i.op; a=i.operands.split(', ') if i.operands else []
            self.ops+=1;self.cycles+=1
            if self.strict_nvm:self._nvm_tick()
            if op=='ret':
                self.cycles+=3
                if not self.stack or not execute_ret:return self.pc
                self.pc=self.stack.pop()
            elif op=='rcall':
                self.stack.append(self.pc); self.pc=i.target;self.cycles+=2
            elif op=='rjmp':self.pc=i.target;self.cycles+=1
            elif op in ('brbs','brbc'):
                bit=int(a[0].rstrip(','));hit=(self.flag(bit)==(op=='brbs'))
                if hit:self.pc=i.target;self.cycles+=1
            elif op=='ldi':self.r[self.reg(a[0])]=self.imm(a[1])
            elif op=='mov':self.r[self.reg(a[0])]=self.r[self.reg(a[1])]
            elif op=='movw':
                d=self.reg(a[0]); s=self.reg(a[1]);self.r[d:d+2]=self.r[s:s+2]
            elif op in ('andi','ori'):
                d=self.reg(a[0]);v=self.imm(a[1]);self.r[d]=(self.r[d]&v if op=='andi' else self.r[d]|v);self.logic(self.r[d])
            elif op in ('and','or','eor'):
                d=self.reg(a[0]);v=self.r[self.reg(a[1])];self.r[d]={'and':self.r[d]&v,'or':self.r[d]|v,'eor':self.r[d]^v}[op];self.logic(self.r[d])
            elif op in ('add','adc'):
                d=self.reg(a[0]);v=self.r[self.reg(a[1])];carry=self.flag(0) if op=='adc' else 0
                self.r[d]=self.add(self.r[d],v,int(carry),op=='adc')
            elif op in ('sub','sbc','cp','cpc'):
                d=self.reg(a[0]);v=self.r[self.reg(a[1])];carry=self.flag(0) if op in ('sbc','cpc') else 0
                result=self.subtract(self.r[d],v,int(carry),op in ('sbc','cpc'))
                if op in ('sub','sbc'):self.r[d]=result
            elif op in ('subi','sbci','cpi'):
                d=self.reg(a[0]);v=self.imm(a[1]);carry=self.flag(0) if op=='sbci' else 0
                result=self.subtract(self.r[d],v,int(carry),op=='sbci')
                if op!='cpi':self.r[d]=result
            elif op in ('inc','dec'):
                d=self.reg(a[0]);v=(self.r[d]+(1 if op=='inc' else -1))&255
                self.r[d]=v;self.znvs(v, v==(0x80 if op=='inc' else 0x7f))
            elif op in ('adiw','sbiw'):
                # Official AVRrc timing: ADIW/SBIW = 2 clocks, not 1.
                self.cycles += 1
                d=self.reg(a[0]);v=self.imm(a[1]);old=self.r[d]|self.r[d+1]<<8
                new=(old+(v if op=='adiw' else -v))&0xffff
                self.r[d]=new&255;self.r[d+1]=new>>8
                self.flagset(1,new==0)
                self.flagset(2,bool(new&0x8000));self.flagset(0,(new<old if op=='adiw' else new>old))
            elif op in ('sbrc','sbrs'):
                r=self.r[self.reg(a[0])];b=self.imm(a[1]);skip=not bool(r&(1<<b)) if op=='sbrc' else bool(r&(1<<b))
                if skip:skipi=self.decode(self.pc);self.pc+=skipi.size;self.cycles+=1+(skipi.size==4)
            elif op=='cpse':
                skip=self.r[self.reg(a[0])]==self.r[self.reg(a[1])]
                if skip:skipi=self.decode(self.pc);self.pc+=skipi.size;self.cycles+=1+(skipi.size==4)
            elif op in ('sbic','sbis'):
                addr=self.imm(a[0]); bit=self.imm(a[1]); val=self.read_io(addr)
                skip=not bool(val&(1<<bit)) if op=='sbic' else bool(val&(1<<bit))
                if skip:skipi=self.decode(self.pc);self.pc+=skipi.size;self.cycles+=1+(skipi.size==4)
            elif op=='sbi':
                addr=self.imm(a[0]);bit=self.imm(a[1]);self.cycles+=1
                if self.strict_nvm:
                    self.write_io(addr, self.read_io(addr)|(1<<bit))
                elif addr==0x1f and bit==0:
                    self.write_io(addr, self.read_io(addr) | (1 << bit))
                elif addr==0x1f and bit==1:
                    assert self.io.get(0x1f,0)&4, 'EEMPE not set'
                    aa=self.io[0x21];bb=self.io[0x20]
                    self.eeprom[aa]=bb;self.eeprom_oplog.append((aa,bb))
                    self.io[0x1f]=0
                else:self.write_io(addr,self.read_io(addr)|(1<<bit))
            elif op=='cbi':
                addr=self.imm(a[0]);bit=self.imm(a[1]);self.cycles+=1;self.write_io(addr,self.read_io(addr)&~(1<<bit))
            elif op=='in':self.r[self.reg(a[0])]=self.read_io(self.imm(a[1]))
            elif op=='out':self.write_io(self.imm(a[0]),self.r[self.reg(a[1])])
            elif op=='lds':
                d=self.reg(a[0]);addr=self.imm(a[1]);self.r[d]=self.mem[addr];self.cycles+=1
            elif op=='sts':
                addr=self.imm(a[0]);d=self.reg(a[1]);self.mem[addr]=self.r[d];self.cycles+=1
            elif op in ('ld','st'):
                r,p=(a[0],a[1]) if op=='ld' else (a[1],a[0]);d=self.reg(r)
                post=p.endswith('+');pre=p.startswith('-');name=p.strip('+-')
                ix={'X':26,'Y':28,'Z':30}[name]
                addr=self.r[ix]|self.r[ix+1]<<8
                if pre:addr-=1
                if op=='ld':self.r[d]=self.mem[addr]
                else:self.mem[addr]=self.r[d]
                if post:addr+=1
                if post or pre:self.r[ix]=addr&255;self.r[ix+1]=(addr>>8)&255
                self.cycles+=1
            elif op in ('ldd','std'):
                r,p=(a[0],a[1]) if op=='ldd' else (a[1],a[0]);d=self.reg(r)
                bank,offset=p.split('+');base=28 if bank=='Y' else 30
                addr=(self.r[base]|self.r[base+1]<<8)+self.imm(offset)
                if op=='ldd':self.r[d]=self.mem[addr]
                else:self.mem[addr]=self.r[d]
                self.cycles+=1
            elif op=='lpm':
                d=self.reg(a[0]);post=a[1]=='Z+';addr=self.r[30]|self.r[31]<<8
                val=self.flash[addr];self.r[d]=val
                self.lpm_oplog.append(addr)
                if post:
                    addr=(addr+1)&0xffff;self.r[30]=addr&255;self.r[31]=addr>>8
                self.cycles+=2
            elif op=='spm':
                addr=self.r[30]|self.r[31]<<8;ctrl=self.io.get(0x37,0)
                if self.strict_nvm:
                    self._strict_spm(addr,ctrl)
                    self.cycles+=3
                    continue
                page=addr&~63
                if ctrl==3:
                    self.flash[page:page+64]=b'\xff'*64
                    self.spm_oplog.append(('erase',page))
                elif ctrl==0x11:
                    self.spm_buffer[:]=b'\xff'*64
                    self.spm_oplog.append(('buffer_clear',page))
                elif ctrl==1:
                    lo=addr&63
                    self.spm_buffer[lo:lo+2]=bytes(self.r[0:2])
                    self.spm_oplog.append(('load',addr,self.r[0],self.r[1]))
                elif ctrl==5:
                    assert addr%64==0,('un-aligned SPM write',hex(addr))
                    self.flash[page:page+64]=self.spm_buffer
                    self.spm_oplog.append(('write',page))
                    self.spm_buffer[:]=b'\xff'*64
                else:raise AssertionError(('unknown SPMCSR',ctrl))
                self.io[0x37]=0; self.cycles+=3
            elif op=='wdr':pass
            elif op=='bset':self.flagset(self.imm(a[0]),True)
            elif op=='bclr':self.flagset(self.imm(a[0]),False)
            elif op=='com':
                d=self.reg(a[0]);v=(~self.r[d])&255;self.r[d]=v;self.flagset(0,True);self.logic(v)
            elif op=='ror':
                d=self.reg(a[0]);v=self.r[d];prior=self.flag(0)
                self.r[d]=((v>>1)|(0x80 if prior else 0))&255
                self.flagset(0,bool(v&1));self.flagset(1,self.r[d]==0)
                self.flagset(2,bool(self.r[d]&0x80));self.flagset(3,self.flag(2)^self.flag(0))
                self.flagset(4,self.flag(2)^self.flag(3))
            elif op=='lsr':
                d=self.reg(a[0]);v=self.r[d];self.r[d]=v>>1
                self.flagset(0,bool(v&1));self.flagset(1,self.r[d]==0)
                self.flagset(2,False);self.flagset(3,self.flag(0))
                self.flagset(4,self.flag(3))
            elif op=='nop':pass
            else:raise AssertionError((hex(self.pc-i.size),op,a))
        raise AssertionError(('CPU overrun',hex(self.pc),self.ops))
