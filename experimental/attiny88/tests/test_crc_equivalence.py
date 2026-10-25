#!/usr/bin/env python3
"""Verify exact unchanged CRC routine for all lengths 0..32, including empty payload."""
from pathlib import Path
import importlib.util,random,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
SROOT=ROOT/'tests'
sys.path.insert(0,str(SROOT))
from emulator_diff_test import Sim

def make_build(name):
 boot=0x1AC0 if name=='plus_1ac0' else 0x1B40
 return {'name':'upstream', 'start':boot,
         'bin':ROOT/('firmware/BOOTLOADER_BODY_1AC0_PLUS.bin' if name=='plus_1ac0' else 'reference/Pass3_1216.bin'),
         'o':ROOT/'build'/('plus_1ac0.o' if name=='plus_1ac0' else 'reference_pass3.o')}

def run_one(build,seq):
 m=bytearray([0]*0x300);p=0x180
 m[p:p+len(seq)]=seq
 r=[0]*32;r[22]=len(seq);r[24]=p&0xff;r[25]=p>>8
 state=Sim(build,{'memory':m,'registers':r})
 state.pc=state.labels['usb_crc16_append']; state.calls=[0xFFFF]
 for n in range(5000):
  if state.pc==0xffff:return bytes(state.m[p+len(seq):p+len(seq)+2]),state.steps
  state.step()
 raise RuntimeError('no return')

def crc_ref(seq):
 crc=0xFFFF
 for val in seq:
  crc ^= val
  for j in range(8):
   if crc&1:crc=(crc>>1)^0xA001
   else:crc>>=1
 return (crc^0xFFFF).to_bytes(2,'little')

def main():
 rng=random.Random(0x1234BEEF)
 a=make_build('pass3');b=make_build('plus_1ac0')
 count=0;stepdelta=[]
 for size in range(0,33):
  seqs=[bytes([0]*size),bytes([255]*size),bytes([0x55]*size),bytes([0xAA]*size),bytes([x*13&255 for x in range(size)])]
  seqs.extend(bytes(rng.getrandbits(8) for _ in range(size)) for i in range(18))
  for seq in seqs:
   x,t=run_one(a,seq);y,u=run_one(b,seq)
   exp=crc_ref(seq)
   if x!=y or y!=exp:raise AssertionError((size,seq.hex(),x.hex(),y.hex(),exp.hex()))
   if u!=t: raise AssertionError(('CRC changed instruction count',t,u))
   stepdelta.append(t-u);count+=1
 print(f'PASS: {count} randomized and edge-vector CRC test cases, sizes 0..32 (including zero length), matching pass2 and independent polynomial. Instruction count difference {min(stepdelta)}..{max(stepdelta)} per call.')
if __name__=='__main__':main()
