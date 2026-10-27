#!/usr/bin/env python3
"""Exact non-relocated AVR instruction audit of Pass24 vs Pass25 USB PHY.

This is an opcode/control-flow equivalence check, not a physical USB certification.
It permits only 2 PUSH and 2 POP removals and one dead-time RJMP removal.
It normalizes PC-relative AVR branches to target instruction identity.
"""
from pathlib import Path
from check_build import build

ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'variants/strict_usb_optimized'
BASE=FOLDER/'micronucleus_t88_pass24.S'
NEW=FOLDER/'micronucleus_t88_pass25.S'

def phys(art):
 begin=art['symbols']['USB_handler'];end=art['symbols']['flash_buffer_append_word'];body=art['body'];boot=art['boot']
 mem={a:body[a-boot:a-boot+2] for a in range(begin,end,2)}
 code=[];pc=begin
 while pc<end:
  word=int.from_bytes(body[pc-boot:pc-boot+2],'little')
  if (word&0xfe0f) in (0x9000,0x9200) or (word&0xfe0e) in (0x940c,0x940e):
   sz=4
  else:sz=2
  code.append((pc,word,bytes(body[pc-boot:pc-boot+sz])))
  pc+=sz
 assert pc==end,(hex(pc),hex(end))
 return code

def rjmp(word):return word&0xf000==0xc000

def brxx(word):return (word&0xfc00) in (0xf000,0xf400)

def branch_target(pc,word):
 if rjmp(word):
  off=word&0xfff
  if off&0x800:off-=4096
 elif brxx(word):
  off=(word>>3)&0x7f
  if off&0x40:off-=128
 else:return None
 return pc+2+off*2

def audit(mode,boot):
 old=build(BASE,mode,boot)
 new=build(NEW,mode,boot)
 a=phys(old);b=phys(new)
 syms=old['symbols']
 removed={syms['USB_handler'],syms['USB_handler']+2, syms['usb_rx_overflow']-2,
          syms['usb_handler_return'],syms['usb_handler_return']+2}
 aa=[e for e in a if e[0] not in removed]
 assert len(aa)==len(b),(len(aa),len(b))
 assert len(a)==len(b)+5
 assert syms['usb_handler_return'] in removed
 # Instruction relocation table: deleted PCs route to next retained instruction
 remap={x[0]:y[0] for x,y in zip(aa,b)}
 nextpc={x[0]:x[0] for x in aa}
 for o in removed:
  candidate=min(x[0] for x in aa if x[0]>o)
  nextpc[o]=candidate
 # Normalize PC-relative branches to the corresponding semantic instruction address
 for (pc,w,orig),(npc,nw,dst) in zip(aa,b):
  if rjmp(w) and rjmp(nw):
   a_target=branch_target(pc,w)
   b_target=branch_target(npc,nw)
   # If a branch points at a removed instruction, it must now point to its successor
   should=remap[nextpc.get(a_target,a_target)] if a_target in nextpc else a_target
   assert should==b_target,('rjmp target',hex(pc),hex(npc),hex(a_target),hex(should),hex(b_target))
  elif brxx(w) and brxx(nw):
   assert (w&0xfc07)==(nw&0xfc07),('branch opcode',hex(pc),hex(npc),hex(w),hex(nw))
   a_target=branch_target(pc,w);b_target=branch_target(npc,nw)
   should=remap[nextpc.get(a_target,a_target)] if a_target in nextpc else a_target
   assert should==b_target,('BR target',hex(pc),hex(npc),hex(a_target),hex(should),hex(b_target))
  else:
   assert orig==dst,('opcode mismatch',hex(pc),hex(npc),orig.hex(),dst.hex())
 # Check only five deletions, with the intended opcodes
 removedbytes={p:int.from_bytes(old['body'][p-boot:p-boot+2],'little') for p in removed}
 assert [removedbytes[syms['USB_handler']+k] for k in (0,2)]==[0x93cf,0x93df]  # PUSH r28/29
 assert [removedbytes[syms['usb_handler_return']+k] for k in (0,2)]==[0x91df,0x91cf] # POP r29/28
 assert rjmp(removedbytes[syms['usb_rx_overflow']-2])
 assert len(b)==len(a)-5
 print('PASS',mode,hex(boot),'PHY',old['symbols']['flash_buffer_append_word']-old['symbols']['USB_handler'],'->',new['symbols']['flash_buffer_append_word']-new['symbols']['USB_handler'],
       'all retained opcodes and branch targets match; removed PUSH2/POP2/RJMP1')

if __name__=='__main__':
 for mode,boot in (('NONE',0x1b40),('ACTIVE_HIGH',0x1b00),('ACTIVE_LOW',0x1b00)):
  audit(mode,boot)
