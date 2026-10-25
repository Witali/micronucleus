#!/usr/bin/env python3
"""Flash-memory SPM unit/boundary tests for reconstructed & relocated bootloader.
Models SPM at the command level: byte word fill, erase and write page.
Not a USB simulator or hardware validation.
"""
from pathlib import Path
import importlib.util,sys,random,json
root=Path(__file__).resolve().parent.parent
# The original differential test imports avr_decoder and has no main side effects.
spec=importlib.util.spec_from_file_location('old_diff',root/'tests/emulator_diff_test.py')
m=importlib.util.module_from_spec(spec);sys.modules['old_diff']=m;spec.loader.exec_module(m)
m.BASE={'name':'upstream','start':0x1b00,
         'bin':root/'build/base.bin','o':root/'build/base.o'}
m.OPT={'name':'upstream','start':0x1b40,
         'bin':root/'build/boot_1b40.bin','o':root/'build/boot_1b40.o'}
class SPMSim(m.Sim):
 def __init__(self, build, initial):
  super().__init__(build,initial)
  self.flash_writes=[];self.page_buffer={};self.spm_count=0;self.unaligned_writes=[]
  self.flash_backup=self.flash[:]
 def step(self):
  at=self.pc
  # the supplied simulator is incomplete for real USB cycles, here testing SPM operations only
  w=int.from_bytes(self.flash[at:at+2],'little')
  super().step()
  if w==0x95e8:
   ctl=self.m[0x57] or self.io.get(0x37,0)
   self.spm_count+=1
   z=self.word(30)
   page=z&~63
   assert ctl in (1,3,5,17),(self.name,hex(at),'SPMCSR',ctl)
   assert page<0x2000,(self.name,hex(at),hex(z))
   if ctl==1:
    assert z&1==0,('word address not even',z)
    self.page_buffer[z]=self.r[0];self.page_buffer[z+1]=self.r[1]
   elif ctl==3:
    self.flash[page:page+64]=b'\xff'*64
   elif ctl==5:
    
    if z&63: self.unaligned_writes.append((at,z))
    for addr in range(page,page+64):
     if addr in self.page_buffer:self.flash[addr] &=self.page_buffer[addr]
    self.page_buffer.clear()
   elif ctl==17:self.page_buffer.clear()
   self.flash_writes.append((at,ctl,z))
   self.m[0x57]=0;self.io[0x37]=0

def case(build,pc,regs,stop,limit=2000):
 init={'memory':bytes(0x300),'registers':[0]*32}
 s=SPMSim(build,init);s.pc=s.labels[pc]
 for i,v in regs.items():s.r[i]=v
 for _ in range(limit):
  if s.pc==s.labels[stop]:return s
  s.step()
 raise AssertionError(('limit',s.name,pc,s.pc))
results=[]
for build in (m.BASE,m.OPT):
 init={'memory':bytes(0x300),'registers':[0]*32};name=build['name']
 # 1) Test page buffer single word load / R1 reset / R4:R5 increments
 for ptr in (0,2,0x100,0x1a00):
  a=SPMSim(build,init);a.pc=a.labels['usb_program_page'];a.calls=[0xffff]
  a.setword(4,ptr);a.r[24]=0x12;a.r[25]=0x34
  while a.pc!=0xffff:
   a.step()
  loaded=a.page_buffer.get(ptr, None)
  expected_lo= ((0xc000+(a.base//2)-1)&255) if ptr==0 else 0x12
  expected_hi= ((0xc000+(a.base//2)-1)>>8) if ptr==0 else 0x34
  assert a.page_buffer[ptr]==expected_lo and a.page_buffer[ptr+1]==expected_hi,(name,ptr,a.page_buffer)
  assert a.word(4)==ptr+2,(name,ptr,'ptr advancement')
  assert a.r[1]==0,(name,ptr,'R1 not zero')
  results.append((name,'buffer word',hex(ptr),'PASS'))
 # 2) Erasure loop runs from page BOOT-64 down to page 0, without erasing boot page
 e=case(build,'L1d5e',{1:0,3:2},'L1d7e',limit=2500)
 erased=[(ctl,z) for at,ctl,z in e.flash_writes if ctl==3]
 expected=list(range(e.base-64,-1,-64))
 assert [z for ctl,z in erased]==expected,(name,'erase addresses',len(erased),len(expected))
 assert e.flash[e.base:e.base+32]==e.flash_backup[e.base:e.base+32],(name,'boot code overwritten')
 results.append((name,'erase app only',len(erased),'PASS'))
 # 3) Boundary of last app page and first boot page for page write function
 for off in (-128,-64,-2,0,2,64):
  target=e.base+off
  # set r3 to 0x40, r4=r5=target+2 (last SPM word pointer after buffering)
  s=SPMSim(build,init);s.pc=s.labels['L1d86']
  s.setword(4,(target+2)&0xffff);s.r[3]=0x40
  # the SPM page writer enters L1d9a; any write should happen before it
  for _ in range(70):
   if s.pc==s.labels['L1d9a']:break
   s.step()
  else:raise AssertionError((name,'page write guard flow'))
  wr=[(ctl,z) for at,ctl,z in s.flash_writes if ctl==5]
  assert bool(wr)==(target<e.base),(name,'wrong write permission',hex(target),wr)
  if build is m.OPT: assert not s.unaligned_writes,(name,'unaligned SPM page write',s.unaligned_writes)
  results.append((name,'page write guard',hex(target),'PASS' if not s.unaligned_writes else 'LEGACY DATASHEET VIOLATION'))

 # 4) End-to-end synthetic Flash page fill + commit (32 words) including reset-vector patch.
 rng=random.Random(17931)
 for page in (0,64,0x1000,build['start']-128,build['start']-64):
  a=SPMSim(build,init)
  a.setword(4,page)
  expected=bytearray(64)
  for i in range(0,64,2):
   lo=rng.randrange(256);hi=rng.randrange(256)
   expected[i]=lo;expected[i+1]=hi
   a.r[24]=lo;a.r[25]=hi
   a.pc=a.labels['usb_program_page'];a.calls=[0xffff]
   for _ in range(16):
    if a.pc==0xffff:break
    a.step()
   assert a.pc==0xffff,(name,'usb_program_page return',hex(page),i)
  if page==0:
   vector=(0xc000+(build['start']//2)-1)&0xffff
   expected[0:2]=vector.to_bytes(2,'little')
  a.r[3]=0x40;a.pc=a.labels['L1d86']
  for _ in range(60):
   if a.pc==a.labels['L1d9a']:break
   a.step()
  else:raise AssertionError((name,'commit timeout',hex(page)))
  assert bytes(a.flash[page:page+64])==bytes(expected),(name,'data mismatch',hex(page),a.flash[page:page+64].hex(),expected.hex())
  if build is m.OPT:assert not a.unaligned_writes,(name,'unaligned page commit',hex(page),a.unaligned_writes)
  results.append((name,'32-word page fill/commit',hex(page),'PASS' if not a.unaligned_writes else 'LEGACY DATASHEET VIOLATION'))

legacy_violations=sum(c[-1]=='LEGACY DATASHEET VIOLATION' for c in results)
print('SPM test cases:',len(results),'model passed with legacy alignment mismatches:',legacy_violations)
print('\n'.join(map(str,results)))
(root/'report/spm_model_results.json').write_text(json.dumps({'result':'PASS: PASS2 AND PASS3 SPM PAGE WRITES ALIGNED','tests':len(results),'legacy_violations':legacy_violations,'cases':results,'limitations':['Models SPM registers and flash commands; NOT bus timing, SPM busy latency, EEPROM interactions or hardware'], 'source':'spm_boundary_audit.py'},indent=2)+'\n')
