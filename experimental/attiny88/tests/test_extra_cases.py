#!/usr/bin/env python3
"""Directed high-level emulator tests + mathematically exhaustive 16-bit boundary check.
Not a USB electrical model. Simulated SPM write semantics tested separately.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import emulator_diff_test as m

BOOT=0x1b00
# Old comparison was CPI ZL,0 / CPC ZH,BOOT_HIGH / BRCC.
# For page-aligned BOOT with low byte zero, borrow equals ZH < BOOT_HI.
for ptr in range(65536):
 old=ptr < BOOT
 new=(ptr>>8)<(BOOT>>8)
 assert old==new,(hex(ptr),old,new)
print('PASS all 65,536 Flash address guard predicates')

labels=['L1ec0','L1f0c','L1f3a','L1f4a','L1f56','L1f62','L1f70']
tests=0
for label in labels:
 for request in range(12):
  states=[]
  for variant in (m.BASE,m.OPT):
   regs=[0]*32
   regs[28]=0;regs[29]=1
   regs[24]=((variant['start']+0x1c)&255) if label=='L1f4a' else 0x60
   regs[25]=((variant['start']+0x1c)>>8) if label=='L1f4a' else request
   mem=bytearray(0x300)
   mem[0x010f]=0x10;mem[0x0100]=0;mem[0x0119]=0x5d;mem[0x011a]=0x1a
   state=m.Sim(variant,{'registers':regs,'memory':mem})
   state.pc=state.labels[label]
   result=state.run()
   states.append((result,m.normalize_pointer(state.m,state.base)))
  assert states[0]==states[1],(label,request,'SRAM/control-flow differ')
  tests+=1
print('PASS',tests,'directed control/descriptor reply tests')

# Main initial USB disconnect/setup delay instruction text has not been edited by this pass.
ref=Path(__file__).resolve().parents[1]/'reference/previous_audited_1256.S'
new=Path(__file__).resolve().parents[1]/'source/micronucleus_t88_optimized.S'
if ref.exists():
 a=ref.read_text();b=new.read_text()
 segment=lambda s:s[s.index('main:'):s.index('L1d6a:',s.index('main:'))]
 assert segment(a)==segment(b),'Initial USB reconnect delay or WDT configuration was changed'
 print('PASS initial WDT and USB reconnect delay code unchanged')
