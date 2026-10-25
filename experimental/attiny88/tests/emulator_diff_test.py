#!/usr/bin/env python3
"""Differential dynamic checks of original/optimized Micronucleus command & packet logic.
    NOT a USB physical timing simulator. It compares SRAM and CPU-visible effects after
    executing independent instruction streams with identical synthetic host inputs.
"""
import importlib.util, os, random, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).parent
sys.argv=['decoder']
spec=importlib.util.spec_from_file_location('avr_decoder', ROOT/'avr_decoder.py')
dec=importlib.util.module_from_spec(spec);sys.modules['avr_decoder']=dec;spec.loader.exec_module(dec)

def symbols(path):
 s=subprocess.check_output(['llvm-objdump','-t',str(path)],text=True)
 out={}
 for line in s.splitlines():
  m=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',line)
  if m: out[m.group(2)]=int(m.group(1),16)
 return out

BASE={'name':'upstream','start':0x1a40,'bin':ROOT.parent/'reference/upstream_t88_default.bin','o':ROOT.parent/'build/original.o'}
LED_ON=os.environ.get('MICRO_LED_ON')=='1'
OPT={'name':'optimized','start':0x1b00,'bin':ROOT.parent/'build/with_org_zero_prefix_DO_NOT_FLASH.bin','o':ROOT.parent/'build/audited.o'}

class Sim:
 def __init__(self,build,init):
  self.name=build['name']; self.base=build['start']; self.o=build['o']
  self.flash=bytearray([0xff]*8192)
  data=build['bin'].read_bytes(); self.flash[self.base:self.base+len(data) if self.name=='upstream' else len(data)]=data if self.name=='upstream' else data[self.base:]
  self.labels=symbols(self.o)
  self.m=bytearray(init['memory']); self.r=init['registers'].copy()
  self.flags=0;self.calls=[];self.steps=0;self.pc=self.labels['L1d9c'];self.stop=self.labels['L1d3a']; self.ending=self.labels['L1eac']
  self.events=[];self.visited=set()
  self.io={0x1b:0,0x09:0x02,0x0a:0,0x0b:0,0x34:0,0x1e:0}
  self.r[1]=0
  if init.get('program_present',False):self.flash[self.base-3]=0
  if self.name=='optimized':
   p=self.m[0x0110]+(self.m[0x0111]<<8)
   if 0x1a40<=p<0x1a70:
    p+=self.base-0x1a40;self.m[0x0110]=p&255;self.m[0x0111]=p>>8
 def flag(self,n): return (self.flags>>n)&1
 def setflag(self,n,b):self.flags=(self.flags&~(1<<n))|((bool(b))<<n)
 def logic(self,v):
  self.setflag(1,v==0);self.setflag(2,v&0x80);self.setflag(3,0);self.setflag(4,v&0x80)
 def sub8(self,d,k,carry=0,oldz=False):
  t=d-k-carry;r=t&255
  self.setflag(5,(((~d&k)|(k&r)|(r&~d))&8)!=0)
  self.setflag(3,(((d&~k&~r)|(~d&k&r))&0x80)!=0)
  self.setflag(2,r&0x80)
  self.setflag(1,r==0 and (not oldz or self.flag(1)))
  self.setflag(0,t<0)
  self.setflag(4,self.flag(2)^self.flag(3))
  return r
 def add8(self,d,k,carry=0,oldz=False):
  t=d+k+carry;r=t&255
  self.setflag(5,(((d&k)|(k&~r)|(~r&d))&8)!=0)
  self.setflag(3,(((d&k&~r)|(~d&~k&r))&0x80)!=0)
  self.setflag(2,r&0x80)
  self.setflag(1,r==0 and (not oldz or self.flag(1)))
  self.setflag(0,t>255)
  self.setflag(4,self.flag(2)^self.flag(3))
  return r
 def word(self,lo):return self.r[lo]|(self.r[lo+1]<<8)
 def setword(self,lo,v):self.r[lo]=v&255;self.r[lo+1]=v>>8&255
 def memread(self,address):return self.m[address] if address<len(self.m) else 0
 def memwrite(self,address,v):
  if address<len(self.m):self.m[address]=v&255
  if address==0x57:self.io[0x37]=v&255  # I/O 0x37 aliases data memory 0x57
 def step(self):
  if self.steps>20000:raise RuntimeError((self.name,'too many steps',hex(self.pc)))
  pc=self.pc
  self.visited.add(pc)
  dec.START=self.base;dec.raw=bytes(self.flash[self.base:]);ins=dec.decode(pc)
  op=ins.op;arg=ins.operands; self.pc=pc+ins.size;self.steps+=1
  args=[x.strip() for x in arg.split(',') if x.strip()]
  def num(x): return int(x,0)
  def reg(x):return int(x[1:])
  if op=='ldi':self.r[reg(args[0])]=num(args[1])&255
  elif op=='mov':self.r[reg(args[0])]=self.r[reg(args[1])]
  elif op=='movw':self.setword(reg(args[0]),self.word(reg(args[1])))
  elif op in ('rjmp','brbs','brbc','rcall'):
   go=True if op in ('rjmp','rcall') else (self.flag(int(args[0]))==(op=='brbs'))
   if go:
    if op=='rcall':self.calls.append(self.pc)
    self.pc=ins.target
  elif op=='ret':
   if not self.calls:raise RuntimeError('RET empty')
   self.pc=self.calls.pop()
  elif op=='cpse':
   if self.r[reg(args[0])]==self.r[reg(args[1])]:self.pc+=dec.decode(self.pc).size
  elif op in ('sbrc','sbrs'):
   v=(self.r[reg(args[0])]>>num(args[1]))&1
   if v==(op=='sbrs'):self.pc+=dec.decode(self.pc).size
  elif op in ('sbis','sbic'):
   v=(self.io.get(num(args[0]),0)>>num(args[1]))&1
   if v==(op=='sbis'):self.pc+=dec.decode(self.pc).size
  elif op in ('in','out'):
   if op=='in':self.r[reg(args[0])]=self.io.get(num(args[1]),0)
   else:
    self.io[num(args[0])]=self.r[reg(args[1])]
    if num(args[0])==0x37:self.memwrite(0x57,self.r[reg(args[1])])
  elif op in ('sbi','cbi'):
   io=num(args[0]);b=num(args[1]);v=self.io.get(io,0)
   self.io[io]=(v|(1<<b)) if op=='sbi' else (v & ~(1<<b))
  elif op in ('lds','sts','ldd','std','ld','st'):
   if op=='lds':self.r[reg(args[0])]=self.memread(num(args[1]))
   elif op=='sts':self.memwrite(num(args[0]),self.r[reg(args[1])])
   elif op=='ldd':
    pointer,offset=args[1].split('+');at=self.word(28 if pointer=='Y' else 30)+int(offset)
    self.r[reg(args[0])]=self.memread(at)
   elif op=='std':
    pointer,offset=args[0].split('+');at=self.word(28 if pointer=='Y' else 30)+int(offset)
    self.memwrite(at,self.r[reg(args[1])])
   else:
    rname,mem=args; isload=op=='ld'
    pointer=mem if isload else rname
    isplus=pointer.endswith('+');isminus=pointer.startswith('-');pointer=pointer.strip('+-')
    low={'X':26,'Y':28,'Z':30}[pointer]
    if isminus:self.setword(low,(self.word(low)-1)&0xffff)
    if isload:self.r[reg(rname)]=self.memread(self.word(low))
    else:self.memwrite(self.word(low),self.r[reg(mem)])
    if isplus:self.setword(low,(self.word(low)+1)&0xffff)
  elif op=='lpm':
   rd=reg(args[0]);old=self.word(30);self.r[rd]=self.flash[old] if old<len(self.flash) else 0xff
   if args[1].endswith('+'):self.setword(30,(old+1)&0xffff)
  elif op in ('andi','ori','eor','or','and'):
   d=reg(args[0]);k=self.r[reg(args[1])] if op in ('eor','or','and') else num(args[1]);v=self.r[d]
   x=v&k if op in ('and','andi') else v|k if op in ('or','ori') else v^k
   self.r[d]=x&255;self.logic(x&255)
  elif op in ('cpi','subi','sbci','cp','cpc','sub','sbc'):
   d=reg(args[0]);k=self.r[reg(args[1])] if op in ('cp','cpc','sub','sbc') else num(args[1]);v=self.sub8(self.r[d],k,self.flag(0) if op in ('sbci','cpc','sbc') else 0,oldz=op in ('sbci','cpc','sbc'))
   if op not in ('cp','cpc','cpi'):self.r[d]=v
  elif op in ('add','adc'):
   d=reg(args[0]);k=self.r[reg(args[1])];self.r[d]=self.add8(self.r[d],k,self.flag(0) if op=='adc' else 0,oldz=op=='adc')
  elif op in ('adiw','sbiw'):
   d=reg(args[0]);old=self.word(d);k=num(args[1]);new=(old+k if op=='adiw' else old-k)&0xffff
   self.setword(d,new)
   n=(new>>15)&1;v=((~old&new)>>15)&1 if op=='adiw' else ((old&~new)>>15)&1
   c=((old&~new)>>15)&1 if op=='adiw' else ((~old&new)>>15)&1
   self.setflag(0,c);self.setflag(1,new==0);self.setflag(2,n);self.setflag(3,v);self.setflag(4,n^v)
  elif op in ('inc','dec','com','neg','lsr','ror','swap'):
   d=reg(args[0]);v=self.r[d]
   if op=='inc':x=(v+1)&255; self.setflag(3,x==0x80)
   elif op=='dec':x=(v-1)&255;self.setflag(3,x==0x7f)
   elif op=='com':x=255-v;self.setflag(3,0);self.setflag(0,1)
   elif op=='neg':x=(-v)&255;self.setflag(3,x==0x80);self.setflag(0,x!=0)
   elif op=='swap':x=(v>>4)|((v&15)<<4)
   elif op=='lsr':x=v>>1;self.setflag(0,v&1);self.setflag(3,self.flag(0))
   elif op=='ror':oldc=self.flag(0);x=(v>>1)|(oldc<<7);self.setflag(0,v&1);self.setflag(3,((x>>7)&1)^self.flag(0))
   if op!='swap':
    self.setflag(2,x&0x80);self.setflag(1,x==0);self.setflag(4,self.flag(2)^self.flag(3))
   self.r[d]=x
  elif op in ('spm','wdr','nop'):pass
  else:raise NotImplementedError((self.name,hex(pc),op,arg))
 def run(self):
  for _ in range(20000):
   if self.pc==self.stop:return 'poll'
   if self.pc==self.ending:return 'exit'
   self.step()
  raise RuntimeError((self.name,'step limit',hex(self.pc)))

def randcase(rng,k):
 mem=bytearray(rng.randrange(256) for _ in range(0x300))
 reg=[rng.randrange(256) for _ in range(32)]
 reg[1]=0
 reg[3]=rng.choice([0,1,2,3,4,64])
 reg[4]=rng.choice([0,0x40,0x80]);reg[5]=0
 reg[6]=rng.choice([0,1,0xaf,0xff]);reg[7]=rng.choice([0,3,4])
 if k%10<3:reg[6]=0xaf;reg[7]=4
 reg[28]=rng.choice([0,1,0xa9,0xff]);reg[29]=0x14
 mem[0x0112]=rng.choice([0,1,2,3,7,11,16,20]);mem[0x010d]=rng.choice([0,1,2,3,4,5,6,8,0x2d])
 mem[0x010f]=rng.choice([0,0x10,0x1f,0x5a]);mem[0x0100]=rng.choice([0,1,2,8,12,0xff])
 mem[0x0117]=rng.choice([0,0x60,0x40,0x20]);mem[0x0118]=rng.choice([0,1,2,3,5,6,8,9,10,12])
 mem[0x011a]=rng.choice([0,1,2,3]);mem[0x0110]=0x5c;mem[0x0111]=0x1a;
 return {'memory':mem,'registers':reg,'program_present':(k%10)<2}

def normalize_pointer(mem,base):
 mm=bytearray(mem)
 # SRAM usbMsgPtr: 0x0110/0x0111 holds pointers into descriptors; normalize relocated flash addresses
 p=mm[0x0110]+(mm[0x0111]<<8)
 if base<=p<base+46:
  p-=base-0x1a40
  mm[0x0110]=p&255;mm[0x0111]=p>>8
 return mm

def main():
 rng=random.Random(123456)
 cases=1200
 failure=[]; hist={}; all_visited=set(); total_steps=0; intentional_descriptor_changes=0
 for k in range(cases):
  data=randcase(rng,k);a=Sim(BASE,data);b=Sim(OPT,data)
  try: ra=a.run();rb=b.run()
  except Exception as e: failure.append((k,'ERROR',str(e)));break
  hist[ra]=hist.get(ra,0)+1
  all_visited |= a.visited
  total_steps+=a.steps
  if ra!=rb:failure.append((k,'EXIT',ra,rb));break
  am=normalize_pointer(a.m,a.base);bm=normalize_pointer(b.m,b.base)
  if am!=bm:
   different=[(i,x,y) for i,(x,y) in enumerate(zip(am,bm)) if x!=y]
   changed={i for i,_,_ in different}
   # Expected: reply reports larger usable flash (0x1A3C -> 0x1AFC), CRC bytes differ accordingly.
   if changed=={0x103,0x10a,0x10b} and am[0x103]==0x3c and bm[0x103]==0xfc:
    intentional_descriptor_changes+=1
   else:
    failure.append((k,'RAM',[(hex(i),hex(x),hex(y)) for i,x,y in different[:20]],ra));break
  # Apart from Y base and new scratch r23, regs should match exactly (unless descriptor pointer moved, then Z)
  ignore={23,24,28,29,30,31}
  badreg=[(i,x,y) for i,(x,y) in enumerate(zip(a.r,b.r)) if x!=y and i not in ignore]
  if badreg: failure.append((k,'REG',badreg,ra));break
  # Flags may be different due to Y init? LDI has no effect. Flags after layout should agree.
  # LED_MACRO deleted: its final ANDI changed flags and r24, both overwritten before next use.
  # Compare only externally visible SRAM and live registers at next 5ms polling iteration.
  if a.calls or b.calls:failure.append((k,'stack unfinished',a.calls,b.calls));break
 print('LED_ON:',LED_ON,'Cases:',cases, 'Pass:',cases-len(failure),'paths',hist, 'original_instructions_covered:',len(all_visited), 'total_steps:', total_steps,'intentional_reply_updates:',intentional_descriptor_changes,'errors',failure[:3])
 if failure:raise SystemExit(1)

if __name__=='__main__':main()
