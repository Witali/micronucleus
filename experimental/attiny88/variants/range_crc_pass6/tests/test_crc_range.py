#!/usr/bin/env python3
"""Machine-code CRC range tests using assembled AVR instructions (not a USB bus model)."""
import sys, random, pathlib, subprocess, re, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from emulator_diff_test import Sim,dec

BOOT=int((ROOT/'build.py').read_text().split('BOOT_AT=')[1].split('\n')[0],0)
BUILD={'name':'upstream','start':BOOT,'bin':ROOT/'firmware/BOOTLOADER_BODY_CRC_PLUS.bin','o':ROOT/'build/plus_crc.o'}

class CRCDevice(Sim):
 def __init__(self,rom=None,eeprom=None):
  mem=bytearray(0x300); regs=[0]*32;regs[1]=0;regs[28]=0;regs[29]=1
  super().__init__(BUILD,{'memory':mem,'registers':regs})
  self.eeprom=bytes(eeprom) if eeprom is not None else bytes([i*17&255 for i in range(64)])
  if rom is not None:self.flash[:BOOT-4]=rom[:BOOT-4]
  self.calls=[]
  self.io[0x1f]=0; self.io[0x20]=0;self.io[0x21]=0
 def request(self,opcode,start=0,end=0,length=1):
  self.pc=self.labels['L1f0c'];self.calls=[];self.steps=0
  self.r[25]=opcode;self.r[28]=0;self.r[29]=1
  self.m[0x0117]=0xC0;self.m[0x0118]=opcode
  self.m[0x0119]=start&255;self.m[0x011a]=start>>8
  self.m[0x011b]=end&255;self.m[0x011c]=end>>8
  self.m[0x011d]=length&255;self.m[0x011e]=length>>8
  for i in range(20000):
   if self.pc==self.labels['L1f34']:
    return bytes(self.m[0x010a:0x010b])
   if self.pc==self.labels['L1f22']:
    return bytes(self.m[0x0138:0x013b])
   pc=self.pc
   dec.START=self.base;dec.raw=bytes(self.flash[self.base:])
   ins=dec.decode(pc)
   if ins.op=='sbi' and ins.operands=='0x1f, 0':
    self.io[0x20]=self.eeprom[self.io[0x21]]
   self.step()
  raise AssertionError(('step timeout',opcode,hex(self.pc),hex(self.base)))

def reference_crc(seq):
 crc=0xffff
 for b in seq:
  crc ^= b
  for j in range(8):crc=(crc>>1)^(0xa001 if crc&1 else 0)
 return crc^0xffff

class CRCRangeTests(unittest.TestCase):
 def test_many_flash_and_eeprom_ranges(self):
  rng=random.Random(48151)
  flash=bytes(rng.getrandbits(8) for _ in range(8192))
  eeprom=bytes(rng.getrandbits(8) for _ in range(64))
  for memory,opcode,size in ((flash,0xd0,BOOT-4),(eeprom,0xd1,64)):
   for index in range(60):
    a=rng.randrange(size);z=min(size,a+rng.randrange(1,150))
    d=CRCDevice(rom=flash,eeprom=eeprom)
    self.assertEqual(d.request(opcode,a,z),b'\x00')
    status=0;iterations=0
    while status==0:
     response=d.request(0xd2,start=rng.randrange(1,17),length=3)
     status=response[0];iterations+=1
     self.assertLess(iterations,200)
     self.assertEqual(int.from_bytes(response[1:],'little'),reference_crc(memory[a:d.m[0x0130]+(d.m[0x0131]<<8)]))
    self.assertEqual(status,1)
    self.assertEqual(int.from_bytes(response[1:],'little'),reference_crc(memory[a:z]),(opcode,a,z,response))
    self.assertEqual(d.request(0xd2,start=8,length=3),response)
 def test_full_flash_and_full_eeprom(self):
  rng=random.Random(418)
  flash=bytes(rng.getrandbits(8) for _ in range(8192))
  eeprom=bytes(rng.getrandbits(8) for _ in range(64))
  for opcode,src,end in ((0xd0,flash,BOOT-4),(0xd1,eeprom,64)):
   d=CRCDevice(rom=flash,eeprom=eeprom)
   self.assertEqual(d.request(opcode,0,end),b'\x00')
   steps=0
   while True:
    packet=d.request(0xd2,start=16,length=3)
    steps+=1
    self.assertLessEqual(steps,(end+15)//16)
    if packet[0]: break
   self.assertEqual(packet[0],1)
   self.assertEqual(int.from_bytes(packet[1:],'little'),reference_crc(src[:end]))

 def test_range_rejections(self):
  d=CRCDevice()
  for op,lo,hi in ((0xd0,0,0),(0xd0,0,BOOT-3),(0xd0,100,50),(0xd1,0,65),(0xd1,63,0),(0xd1,64,64),(0xd1,0,257)):
   self.assertEqual(d.request(op,lo,hi),b'\x02',(op,lo,hi))
  self.assertEqual(d.request(0xd2,8,length=3)[0],2)
 def test_crc_shared_core_unchanged(self):
  import build
  t=build.symbols(ROOT/'build/plus_crc.o')
  a=(ROOT/'firmware/BOOTLOADER_BODY_CRC_PLUS.bin').read_bytes()
  s=t['usb_crc16_append']-BOOT;e=t['USB_handler']-BOOT
  ref=build.symbols(ROOT/'build/reference_pass3.o')
  old=(ROOT/'reference/Pass3_1216.bin').read_bytes()
  baseline=old[ref['usb_crc16_append']-0x1b40:ref['USB_handler']-0x1b40]
  self.assertEqual(a[s:e],baseline)
  self.assertIn('rcall   L1aa0',(ROOT/'source/micronucleus_t88_plus.S').read_text())

if __name__=='__main__': unittest.main(verbosity=2)
