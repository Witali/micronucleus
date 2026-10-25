#!/usr/bin/env python3
"""Machine-instruction-level AVR model of new EEPROM handlers.

Covers actual compiled opcodes and register side effects. It is not a USB
physical simulator, nor a hardware-accurate EEPROM endurance simulator.
"""
import importlib.util, pathlib, random, re, subprocess, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('avr_decoder',ROOT/'tests/avr_decoder.py')
dec=importlib.util.module_from_spec(spec);sys.modules['avr_decoder']=dec;spec.loader.exec_module(dec)
OBJ=ROOT/'build/plus_crc.o'
BODY=ROOT/'firmware/BOOTLOADER_BODY_CRC_PLUS.bin'
BOOT=0x19C0


def get_symbols():
    out={}
    for line in subprocess.check_output(['llvm-objdump','-t',str(OBJ)],text=True).splitlines():
        m=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',line)
        if m:out[m.group(2)]=int(m.group(1),16)
    return out

class AVR:
    def __init__(self,request=0xA0,address=0,index=0,ep_busy=False,spm_busy=False,request_type=0xC0,contents=None,length=1):
        self.labels=get_symbols()
        self.flash=BODY.read_bytes()
        self.eeprom=bytearray([0xff]*64) if contents is None else bytearray(contents)
        self.r=[0]*32;self.r[28]=0x00;self.r[29]=0x01;self.r[25]=request
        self.mem=bytearray(0x300)
        self.mem[0x0117]=request_type;self.mem[0x0118]=request
        self.mem[0x0119]=address&255;self.mem[0x011a]=(address>>8)&255
        self.mem[0x011b]=index&255;self.mem[0x011c]=(index>>8)&255
        self.mem[0x011d]=length&255;self.mem[0x011e]=(length>>8)&255
        self.io={0x1f:2 if ep_busy else 0,0x20:0,0x21:0,0x37:1 if spm_busy else 0}
        self.pc=self.labels['L1f0c'];self.flags=0;self.stack=[];self.cycle=0
        self.last_eempe_cycle=None;self.spmmemwrites=0;self.eeprom_writes=0
        self.trace=[];self.outcome=None
    def flag(self,n):return bool(self.flags&(1<<n))
    def setflag(self,n,v):self.flags=((self.flags| (1<<n)) if v else (self.flags & ~(1<<n)))
    def logic(self,x):
        self.setflag(1,x==0);self.setflag(2,(x&0x80)!=0);self.setflag(3,0);self.setflag(4,(x&0x80)!=0)
    def ssub(self,a,b):
        x=(a-b)&255
        self.setflag(0,a<b);self.setflag(1,x==0);self.setflag(2,bool(x&128))
        self.setflag(3,bool(((a&~b&~x)|(~a&b&x))&128));self.setflag(4,self.flag(2)^self.flag(3))
    def register(self,s):return int(s[1:])
    def numeric(self,s):return int(s,0)
    def dec(self,addr):
        dec.START=BOOT;dec.raw=self.flash
        return dec.decode(addr)
    def run(self):
        stop={self.labels['L1f34']:'onebyte',self.labels['L1eca']:'zero',self.labels['old_vendor_dispatch']:'legacy',self.labels['L1de2']:'flash'}
        for _ in range(350):
            if self.pc in stop:
                self.outcome=stop[self.pc]
                if self.outcome=='onebyte':return (self.outcome,self.r[18] if False else self.mem[0x010a])
                if self.outcome=='flash':return (self.outcome, ((self.mem[0x0111]<<8)|self.mem[0x0110], self.r[24]))
                return (self.outcome,None)
            i=self.dec(self.pc)
            assert i.op!='WORD',('unknown opcode',hex(self.pc),hex(i.words[0]))
            self.trace.append((self.pc,i.op,i.operands,self.cycle))
            self.pc+=i.size
            ops=i.operands.split(', ') if i.operands else []
            op=i.op
            delay=1
            if op in ('rjmp','rcall'):
                if op=='rcall':self.stack.append(self.pc);delay=3
                else:delay=2
                self.pc=i.target
            elif op=='ret':
                self.pc=self.stack.pop();delay=4
            elif op in ('brbc','brbs'):
                bit=int(ops[0].rstrip(",")); cond=self.flag(bit)==(op=='brbs');delay=2 if cond else 1
                if cond:self.pc=i.target
            elif op=='ldi':self.r[self.register(ops[0])]=self.numeric(ops[1])
            elif op=='ldd':
                rd=self.register(ops[0]);p,off=ops[1].split('+')
                base=self.r[28]|self.r[29]<<8 if p=='Y' else self.r[30]|self.r[31]<<8
                self.r[rd]=self.mem[base+int(off)];delay=2
            elif op=='std':
                p,off=ops[0].split('+');rr=self.register(ops[1])
                base=self.r[28]|self.r[29]<<8 if p=='Y' else self.r[30]|self.r[31]<<8
                self.mem[base+int(off)]=self.r[rr];delay=2
            elif op in ('tst','and'):
                d=self.register(ops[0]);b=self.register(ops[1]);self.r[d]&=self.r[b];self.logic(self.r[d])
            elif op=='or':
                d=self.register(ops[0]);b=self.register(ops[1]);self.r[d]|=self.r[b];self.logic(self.r[d])
            elif op=='eor':
                d=self.register(ops[0]);b=self.register(ops[1]);self.r[d]^=self.r[b];self.logic(self.r[d])
            elif op=='sub':
                d=self.register(ops[0]);b=self.register(ops[1]);a=self.r[d];bb=self.r[b]
                self.r[d]=(a-bb)&255;self.ssub(a,bb)
            elif op=='cp':
                self.ssub(self.r[self.register(ops[0])],self.r[self.register(ops[1])])
            elif op=='cpi':self.ssub(self.r[self.register(ops[0])],self.numeric(ops[1]))
            elif op=='cpc':
                old_zero=self.flag(1)
                aa=self.r[self.register(ops[0])];bb=self.r[self.register(ops[1])]+(1 if self.flag(0) else 0)
                self.ssub(aa,bb)
                self.setflag(1,old_zero and aa==bb)
            elif op in ('subi','sbci'):
                d=self.register(ops[0]); a=self.r[d]
                old_zero=self.flag(1)
                v=self.numeric(ops[1])+(1 if op=='sbci' and self.flag(0) else 0)
                self.r[d]=(a-v)&255
                self.ssub(a,v)
                if op=='sbci': self.setflag(1, old_zero and self.r[d]==0)
            elif op=='mov':
                self.r[self.register(ops[0])]=self.r[self.register(ops[1])]
            elif op=='movw':
                d=self.register(ops[0]);sr=self.register(ops[1]);self.r[d]=self.r[sr];self.r[d+1]=self.r[sr+1]
            elif op in ('add','adc'):
                d=self.register(ops[0]);b=self.register(ops[1]);a=self.r[d];carry=(1 if op=='adc' and self.flag(0) else 0)
                ss=a+self.r[b]+carry;self.r[d]=ss&255
                self.setflag(0,ss>255);self.setflag(1,(ss&255)==0)
                self.setflag(2,(ss&128)!=0);self.setflag(3,False);self.setflag(4,(ss&128)!=0)
            elif op=='andi':
                d=self.register(ops[0]);self.r[d]&=self.numeric(ops[1]);self.logic(self.r[d])
            elif op=='lsr':
                d=self.register(ops[0]);v=self.r[d];self.r[d]=v>>1;self.setflag(0,v&1);self.setflag(1,(v>>1)==0)
            elif op=='sbic':
                addr=int(ops[0],0);bit=int(ops[1]);assert addr<0x20,'invalid SBIC I/O address'
                if (self.io.get(addr,0)&(1<<bit))==0:
                    nextins=self.dec(self.pc);self.pc+=nextins.size;delay=2 if nextins.size==2 else 3
            elif op=='sbrc':
                d=self.register(ops[0]);bit=int(ops[1]);
                if not self.r[d]&(1<<bit):
                    nextins=self.dec(self.pc);self.pc+=nextins.size;delay=2 if nextins.size==2 else 3
            elif op=='in':self.r[self.register(ops[0])]=self.io.get(self.numeric(ops[1]),0)
            elif op=='out':
                addr=self.numeric(ops[0]);self.io[addr]=self.r[self.register(ops[1])]
                if addr==0x1f:self.last_eempe_cycle=None
            elif op=='sbi':
                addr=self.numeric(ops[0]);bit=self.numeric(ops[1]);delay=2
                assert addr<0x20,'invalid SBI I/O address'
                v=self.io.get(addr,0)
                self.io[addr]=v|(1<<bit)
                if addr==0x1f and bit==2:
                    self.last_eempe_cycle=self.cycle+delay
                if addr==0x1f and bit==1:
                    assert self.last_eempe_cycle is not None
                    assert self.cycle-self.last_eempe_cycle <=4, ('EEMPE 4-cycle rule violated',self.trace[-4:])
                    self.last_eempe_cycle=None
                    self.eeprom[self.io.get(0x21,0)]=self.io.get(0x20,0)
                    self.eeprom_writes+=1
                if addr==0x1f and bit==0:
                    assert not self.io[0x1f]&2, 'EEPROM read during write!'
                    self.io[0x20]=self.eeprom[self.io.get(0x21,0)]
            elif op=='bset':self.setflag(self.numeric(ops[0]),True)
            elif op=='bclr':self.setflag(self.numeric(ops[0]),False)
            else:raise AssertionError((hex(self.pc-2),op,i.operands))
            self.cycle+=delay
        raise AssertionError(('timeout',hex(self.pc),self.trace[-12:]))

class CPUInstructionTests(unittest.TestCase):
    def test_each_eeprom_address(self):
        for address in range(64):
            with self.subTest(address=address):
                image=bytes((i+address)&255 for i in range(64))
                a=AVR(request=0xA0,address=address,contents=image)
                self.assertEqual(a.run(),('onebyte',image[address]))
                self.assertEqual(a.eeprom_writes,0)
                b=AVR(request=0xC0,address=address,index=0xA5,contents=image)
                self.assertEqual(b.run(),('onebyte',0))
                self.assertEqual(b.eeprom[address],0xA5)
                self.assertEqual(b.eeprom_writes,1)
    def test_many_written_values(self):
        rng=random.Random(20261025)
        for _ in range(800):
            addr=rng.randrange(64); data=rng.randrange(256)
            a=AVR(request=0xC0,address=addr,index=data)
            self.assertEqual(a.run(),('onebyte',0))
            self.assertEqual(a.eeprom[addr],data)
    def test_read_out_of_range_returns_zero_length(self):
        for address in (64,65,127,255,256,0x0101,0xFFFF):
            x=AVR(request=0xA0,address=address)
            self.assertEqual(x.run(),('zero',None));self.assertEqual(x.eeprom_writes,0)
    def test_write_out_of_range_returns_status2(self):
        for address in (64,65,127,255,256,0x0101,0xffff):
            x=AVR(request=0xC0,address=address,index=255)
            self.assertEqual(x.run(),('onebyte',2));self.assertEqual(x.eeprom_writes,0)
        x=AVR(request=0xC0,address=0,index=0x100)
        self.assertEqual(x.run(),('onebyte',2))
    def test_busy_conditions(self):
        # Active SPM page erase/write halts the ATtiny88 CPU; testing
        # a simultaneous USB SETUP with SPMCSR busy would be unreachable.
        x=AVR(request=0xc0,address=12,index=1,ep_busy=True)
        self.assertEqual(x.run(),('onebyte',1));self.assertEqual(x.eeprom_writes,0)
        y=AVR(request=0xf0,ep_busy=True)
        self.assertEqual(y.run(),('onebyte',1))
        z=AVR(request=0xf0)
        self.assertEqual(z.run(),('onebyte',0))
        x=AVR(request=0xa0,address=0,ep_busy=True)
        self.assertEqual(x.run(),('zero',None))
    def test_write_rejects_partial_flash_buffer(self):
        for pointer in (1,2,3,31,62,63,0x40+2,0x7f,0xff):
            with self.subTest(pointer=pointer):
                a=AVR(request=0xc0,address=5,index=0x5a)
                a.r[4]=pointer
                self.assertEqual(a.run(),('onebyte',2))
                self.assertEqual(a.eeprom_writes,0)
        for pointer in (0,0x40,0x80,0xC0):
            with self.subTest(pointer=pointer):
                a=AVR(request=0xc0,address=5,index=0x5a)
                a.r[4]=pointer
                self.assertEqual(a.run(),('onebyte',0))
                self.assertEqual(a.eeprom[5],0x5a)

    def test_write_status_wrong_request_type_cannot_touch_eeprom(self):
        for typ in (0x40,0x80,0x00):
            x=AVR(request=0xc0,address=12,index=1,request_type=typ)
            self.assertEqual(x.run(),('legacy',None));self.assertEqual(x.eeprom_writes,0)
    def test_eeprom_write_exact_program_sequence(self):
        x=AVR(request=0xc0,address=2,index=0x6a)
        self.assertEqual(x.run(),('onebyte',0))
        es=[(a,b,c) for _,a,b,c in x.trace if a in ('sbi','out','in')]
        self.assertIn(('out','0x21, r16',x.trace[next(i for i,(_,a,b,_) in enumerate(x.trace) if a=='out' and b=='0x21, r16')][3]),es)
        labels=[(a,b) for _,a,b,_ in x.trace]
        pos=labels.index(('sbi','0x1f, 2'))
        self.assertEqual(labels[pos+1],('sbi','0x1f, 1'))
        self.assertEqual(x.io[0x21],2)
        self.assertEqual(x.io[0x20],0x6a)
        self.assertEqual(x.eeprom[2],0x6a)

if __name__=='__main__':unittest.main(verbosity=2)


class FlashCPUInstructionTests(unittest.TestCase):
    """Actually execute the assembled Flash-read dispatcher on a CPU subset emulator."""
    def test_every_flash_block(self):
        limit=0x19c0-4
        for addr in range(0, limit, 8):
            count=min(8,limit-addr)
            vm=AVR(request=0xb0,address=addr,length=count)
            self.assertEqual(vm.run(),('flash',(addr,count)),hex(addr))
            self.assertEqual(vm.eeprom_writes,0)
    def test_last_byte_and_all_lengths(self):
        limit=0x19c0-4
        for length in range(1,9):
            for addr in (0,3,255,256,limit-length):
                with self.subTest(length=length,addr=addr):
                    vm=AVR(request=0xb0,address=addr,length=length)
                    self.assertEqual(vm.run(),('flash',(addr,length)))
    def test_boundaries_invalid_windex_and_wraparound(self):
        limit=0x19c0-4
        vectors=[(limit,1,0),(limit-1,2,0),(limit-8,9,0),
                 (65535,8,0),(65534,8,0),(0,0,0),(0,9,0),
                 (0,256,0),(0,1,1),(0,1,256),(0,1,65535),
                 (0xffff,0xffff,0)]
        for a,l,idx in vectors:
            vm=AVR(request=0xb0,address=a,length=l,index=idx)
            self.assertEqual(vm.run(),('zero',None), (a,l,idx))
    def test_vendor_out_cannot_read_flash(self):
        for t in (0x40,0x80,0):
            vm=AVR(request=0xb0,address=0,length=8,request_type=t)
            self.assertEqual(vm.run(),('legacy',None))

    def test_randomized_address_length_index_machine_code(self):
        rng=random.Random(276022)
        for i in range(512):
            addr=rng.randrange(65536)
            length=rng.choice([0,1,2,3,4,6,8,9,12,128,256,65535])
            idx=rng.choice([0,0,0,1,0x100,0xffff])
            result=AVR(request=0xb0,address=addr,length=length,index=idx).run()
            expected=('flash',(addr,length)) if (1<=length<=8 and idx==0 and addr+length<=0x19bc) else ('zero',None)
            self.assertEqual(result,expected,(i,addr,length,idx))
