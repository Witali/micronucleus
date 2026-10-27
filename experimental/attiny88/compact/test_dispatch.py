#!/usr/bin/env python3
"""Execute actual compiled AVR branch/CPI opcodes through Block dispatch."""
from check_build import build
from pathlib import Path
import subprocess,re,sys
ROOT=Path(__file__).parent
DIR=ROOT/'variants/strict_usb_optimized'
ENDBLOCK={'ee_read','flash_read','ee_write','ee_ready','usb_standard_dispatch'}

def disasm(obj):
 txt=subprocess.check_output(['llvm-objdump','-d',str(obj)],text=True)
 d={}
 for line in txt.splitlines():
  m=re.match(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*([a-z][a-z0-9]*)\s*(.*)$',line)
  if m:
   pc=int(m[1],16);name=m[2].lower();arg=m[3].strip()
   d[pc]=(name,arg)
 return d

def route(art,dis,req_type,req):
 syms=art['symbols']; stop={syms[k]:k for k in ENDBLOCK}
 pc=syms['usb_dispatch_extended_or_standard_request'];z=0;r24=0;r25=req
 for i in range(40):
  if pc in stop: return stop[pc]
  op,args=dis[pc]
  if op=='ldd':
   assert args.startswith('r24, '),(hex(pc),op,args)
   r24=req_type;pc+=2
  elif op=='cpi':
   reg,imm=args.split(', ');v=r24 if reg=='r24' else r25
   z=(v==int(imm,0));pc+=2
  elif op in ('breq','brne'):
   delta=int(args.replace('.',''),0)
   taken=z if op=='breq' else not z
   pc+=2+delta if taken else 2
  elif op=='rjmp':
   pc+=2+int(args.replace('.',''),0)
  else: raise AssertionError((hex(pc),op,args))
 raise AssertionError(('never landed',hex(pc),req_type,req))

def test():
 for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
  old=build(DIR/'micronucleus_t88_optimized.S',mode)
  new=build(DIR/'micronucleus_t88_pass16.S',mode)
  old_d=disasm(old['obj']);new_d=disasm(new['obj'])
  for req_type in (0x00,0x40,0x80,0xc0):
   for req in range(256):
    a=route(old,old_d,req_type,req)
    b=route(new,new_d,req_type,req)
    if a!=b:raise AssertionError((mode,req_type,req,a,b))
  print('PASS',mode,4*256,'compiled USB request routing cases')

if __name__=='__main__':test()
