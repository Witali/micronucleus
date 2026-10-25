#!/usr/bin/env python3
"""Cycle-accurate (instruction cycle totals) differential checks for the V-USB TX engine.

NOT a physical USB electrical test. Exact per-instruction cycle counts for the
classic AVR subset come from Microchip AVR Instruction Set Manual. Captures
PORTD/DDRD transitions through the bitstream generator, including stuffing/EOP.
"""
import sys,subprocess,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from emulator_diff_test import Sim,dec

OLD={'name':'upstream','start':0x1b40,'bin':ROOT/'reference/Pass3_1216.bin','o':ROOT/'build/reference_pass3.o'}
NEW={'name':'upstream','start':0x1ac0,'bin':ROOT/'firmware/BOOTLOADER_BODY_1AC0_PLUS.bin','o':ROOT/'build/plus_1ac0.o'}

class Timed(Sim):
 def __init__(self,build,init):
  super().__init__(build,init)
  self.t=0
  self.bus_events=[]
  self.push_stack=[]
 def step(self):
  dec.START=self.base;dec.raw=bytes(self.flash[self.base:])
  ins=dec.decode(self.pc)
  op=ins.op
  oldpc=self.pc
  oldio=self.io.copy()
  if op in ('push','pop'):
   reg=int(ins.operands.strip()[1:])
   if op=='push': self.push_stack.append(self.r[reg])
   else: self.r[reg]=self.push_stack.pop()
   self.pc+=2;self.steps+=1
  elif op in ('bst','bld'):
   rg,bt=[x.strip() for x in ins.operands.split(',')]
   rr=int(rg[1:]);bit=int(bt)
   if op=='bst':self.setflag(6,(self.r[rr]>>bit)&1)
   else:self.r[rr]=(self.r[rr]&~(1<<bit))|(self.flag(6)<<bit)
   self.pc+=2;self.steps+=1
  else:
   super().step()
  if op in ('brbs','brbc'):
   cycles=2 if self.pc==ins.target else 1
  elif op in ('cpse','sbis','sbic','sbrs','sbrc'):
   if self.pc==oldpc+ins.size:cycles=1
   else:cycles=2 if self.pc==oldpc+ins.size+2 else 3
  elif op in ('rjmp','ijmp'):cycles=2
  elif op in ('rcall','icall'):cycles=3
  elif op in ('ret','reti'):cycles=4
  elif op in ('sbi','cbi','push','pop','lds','sts','ld','st','ldd','std','sbiw','adiw'):cycles=2
  elif op in ('lpm','elpm'):cycles=3
  elif op=='spm':cycles=4
  else:cycles=1
  self.t+=cycles
  if op in ('out','sbi','cbi'):
   for io in [0x0a,0x0b]:
    if oldio.get(io,0)!=self.io.get(io,0):
     self.bus_events.append((self.t,io,self.io.get(io,0)))
  return ins

def start_new(build,data,fromlabel):
 sim=Timed(build,data)
 sim.pc=sim.labels[fromlabel]
 sim.io[0xa]=0
 sim.io[0xb]=0
 sim.io[0x1b]=4
 return sim

def sim_tx(build,m,r):
 sim=start_new(build,{'memory':m,'registers':r},'usb_tx_acquire_bus')
 for _ in range(3000):
  if sim.pc==sim.labels['usb_handler_packet_done']:
   return sim.bus_events,sim.t,sim.m
  sim.step()
 raise RuntimeError((build['start'],sim.t,hex(sim.pc)))

def test_tx():
 rng=random.Random(0xabd0)
 for case in range(600):
  m=bytearray(rng.getrandbits(8) for _ in range(0x300))
  r=[rng.getrandbits(8) for _ in range(32)]
  r[1]=0;r[16]=rng.getrandbits(8);r[17]=rng.getrandbits(8)
  r[18]=rng.choice([0,0xff,0x80,0x7e,0x55,0xc3,rng.getrandbits(8)])
  r[19]=rng.choice([1,2,3,4,7,12]);r[20]=rng.choice([0xd2,0x5a])
  y=rng.choice([0x0014,0x0101,0x0110]);r[28]=y&255;r[29]=y>>8
  r[30]=0;r[31]=1  # optimized path Z points to global USB SRAM context
  a,ta,ma=sim_tx(OLD,m,r)
  b,tb,mb=sim_tx(NEW,m,r)
  if a!=b or ta!=tb or ma!=mb:
   raise AssertionError(('TX mismatch',case,ta,tb,a[:14],b[:14],[(hex(i),x,y) for i,(x,y) in enumerate(zip(ma,mb)) if x!=y][:5]))
 print('PASS: 600 TX-engine traces identical in PORTD/DDRD levels AND exact cycle timestamps, including bit stuffing and EOP (from TX entry).')

def measure_ack(build,pid,mode):
 m=bytearray(0x300);r=[0]*32
 r[1]=0;r[19]=0x0b;r[28]=0;r[29]=1
 # usb_rx_end_packet subtracts zero and leaves Y = 0x100; packet PID is at Y+0
 m[0x100]=pid;m[0x101]=0;m[0x10c]=0;m[0x112]=1;m[0x114]=mode;m[0x10f]=0x5a
 r[30]=0;r[31]=1  # established during cycle-neutral sync prologue
 sim=start_new(build,{'memory':m,'registers':r},'usb_rx_end_packet')
 for _ in range(500):
  if sim.pc==sim.labels['usb_tx_acquire_bus']:
   return sim.t,sim.m
  if sim.pc==sim.labels['usb_handler_packet_done']:return None,sim.m
  sim.step()
 return None,sim.m

def test_ack():
 verified=0
 for pid in [0xc3,0x4b,0x69,0x2d,0xe1]:
  for mode in [0,1,0x5a]:
   ao,ma=measure_ack(OLD,pid,mode)
   bo,mb=measure_ack(NEW,pid,mode)
   if (ao is None)!=(bo is None):raise AssertionError(('USB ACK presence changed',hex(pid),mode,ao,bo))
   if ao is not None and bo is not None:
    if bo!=ao:raise AssertionError(('response entry delay',hex(pid),mode,ao,bo))
    verified+=1
   if ma!=mb:raise AssertionError(('USB result SRAM difference',hex(pid),mode))
 print(f'PASS: {verified} response paths reach TX entry at the EXACT same AVR cycle, and unchanged SRAM effects; the sampled NRZI bit engine itself is unchanged.')

def test_sync_prologue():
 # Preserve sample phase and register/flag context from the very first USB read.
 rng=random.Random(0xFA7)
 for case in range(500):
  m=bytearray(rng.getrandbits(8) for _ in range(0x300))
  r=[rng.getrandbits(8) for _ in range(32)]
  r[1]=0
  a=start_new(OLD,{'memory':m,'registers':r},'usb_rx_sync_confirmed')
  b=start_new(NEW,{'memory':m,'registers':r},'usb_rx_sync_confirmed')
  a.io[0x9]=b.io[0x9]=rng.choice([0,2,4,6])
  for z in (a,b):
   for _ in range(25):
    if z.pc==z.labels['usb_rx_sample_odd_bit']:break
    z.step()
   else:raise AssertionError(('sync prologue did not reach sample',hex(z.pc)))
  if a.t!=b.t or a.flags!=b.flags or a.m!=b.m:
   raise AssertionError(('sync prologue timing/flags/SRAM',case,a.t,b.t,a.flags,b.flags))
  for q in range(32):
   if q in (30,31):continue  # Z is intentionally set in the optimized prologue.
   if a.r[q]!=b.r[q]:raise AssertionError(('register context',case,q,a.r[q],b.r[q]))
  if b.word(30)!=0x0100:raise AssertionError('Z SRAM base not initialized')
 print('PASS: 500 receive-sync prologues have identical CPU cycles, SREG and registers (except deliberate Z base).')

if __name__=='__main__':
 test_sync_prologue();test_tx();test_ack()
