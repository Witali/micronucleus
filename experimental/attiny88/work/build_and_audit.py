#!/usr/bin/env python3
"""Build static AVR firmware with clang integrated assembler, create safe Intel HEX,
 audit unchanged USB bit handler and CRC, and check loader-bound references.

NO AVR-GCC needed; the .S contains all firmware logic. No linking/relocations needed.
"""
import hashlib, json, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'optimized.S'; BASE=ROOT/'original_decoded.S'
UPSTREAM=Path('/mnt/data/micronucleus_t88_optimization/reference/t88_default_upstream.bin')
OUT=Path('/mnt/data/micronucleus_t88_asm/deliverables')
OUT.mkdir(parents=True,exist_ok=True)
BOOT=0x1b00
FLASH=8192
FLASH_PAGE=64

def run(*cmd):return subprocess.run(cmd,check=True,capture_output=True,text=True).stdout

def sym(path):
 out={}
 for l in run('llvm-objdump','-t',str(path)).splitlines():
  m=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',l)
  if m:out[m.group(2)]=int(m.group(1),16)
 return out

def ihexrec(address,kind,data):
 b=bytes([len(data),(address>>8)&255,address&255,kind])+bytes(data)
 return ':' + (b+bytes([-sum(b)&255])).hex().upper()

def writehex(path,boot,body,with_reset=False):
 lines=[]
 if with_reset:
  # 12-bit word PC wraps; RJMP from address zero to uppermost boot section.
  jump=0xc000+(boot//2)-1
  lines.append(ihexrec(0,0,jump.to_bytes(2,'little')))
 for i in range(0,len(body),16):lines.append(ihexrec(boot+i,0,body[i:i+16]))
 lines.append(ihexrec(0,3, bytes([0,0,(boot>>8)&255,boot&255])))
 lines.append(':00000001FF')
 path.write_text('\n'.join(lines)+'\n')

def audithex(path):
 data={};start=0;bad=[]
 for l in path.read_text().splitlines():
  assert l.startswith(':'),l
  arr=bytes.fromhex(l[1:]);length=arr[0];assert len(arr)==length+5,l
  assert sum(arr)&255==0,(path,l)
  addr=(arr[1]<<8)|arr[2];typ=arr[3]
  if typ==0:
   for k,v in enumerate(arr[4:4+length]):
    assert addr+k not in data,(path,addr+k)
    data[addr+k]=v
  elif typ==3:start=int.from_bytes(arr[4:8],'big')
  elif typ==1:break
  else:raise AssertionError(f'unknown type {typ}')
 return data,start

def immediate(word): return ((word>>4)&0xf0)|(word&15)

def check():
 assert UPSTREAM.exists()
 run('clang','-target','avr','-mmcu=attiny88','-c',str(BASE),'-o',str(OUT/'original_reference.o'))
 run('llvm-objcopy','-j','.text','-O','binary',str(OUT/'original_reference.o'),str(OUT/'original_reference_full.bin'))
 reference=(OUT/'original_reference_full.bin').read_bytes()[0x1a40:]
 upstream=UPSTREAM.read_bytes()
 assert reference==upstream, 'BYTE-EXACT reference reconstruction failed'
 run('clang','-target','avr','-mmcu=attiny88',f'-DBOOT_AT=0x{BOOT:04x}', '-c', '-x','assembler-with-cpp',str(SRC),'-o',str(OUT/'micronucleus_t88_optimized.o'))
 assert 'RELOCATION RECORDS' not in run('llvm-objdump','-r',str(OUT/'micronucleus_t88_optimized.o'))
 run('llvm-objcopy','-j','.text','-O','binary',str(OUT/'micronucleus_t88_optimized.o'),str(OUT/'optimized_full.bin'))
 full=(OUT/'optimized_full.bin').read_bytes()
 assert len(full)<=FLASH,(len(full),FLASH)
 body=full[BOOT:]
 assert 0<len(body)<=FLASH-BOOT
 assert body[:2]==upstream[:2], 'reset BOOT->startup instruction changed'
 upsy=sym(OUT/'original_reference.o');optsy=sym(OUT/'micronucleus_t88_optimized.o')
 segments={}
 for name,edge in [('usb_crc16_append','USB_handler'),('USB_handler','usb_program_page')]:
  old=upstream[upsy[name]-0x1a40:upsy[edge]-0x1a40]
  new=body[optsy[name]-BOOT:optsy[edge]-BOOT]
  assert old==new,(name,'USB critical segment differs',len(old),len(new))
  segments[name]={'bytes':len(new),'sha256':hashlib.sha256(new).hexdigest(), 'byte_identical':True,
                  'original_start':hex(upsy[name]), 'new_start':hex(optsy[name])}
 # Special references must be updated with relocation. Mode and descriptors unchanged except size bytes.
 assert body[2:4] == (BOOT-4).to_bytes(2,'big'),(body[2:4],BOOT-4)
 assert body[4:46] == upstream[4:46]
 helper=optsy['usb_program_page']
 op1=int.from_bytes(full[helper+6:helper+8],'little');op2=int.from_bytes(full[helper+8:helper+10],'little')
 assert op1&0xf0f0==0xe080 and op2&0xf0f0==0xe090,(hex(op1),hex(op2))
 reset_patch=immediate(op1)|(immediate(op2)<<8)
 expected=0xc000 + BOOT//2 -1
 assert reset_patch==expected,(hex(reset_patch),hex(expected))
 at=optsy['app_jump'];word=int.from_bytes(full[at:at+2],'little')
 assert word>>12==0xc
 k=word&0xfff
 if k&0x800:k-=0x1000
 app_pc=(at//2+1+k)&0x0fff
 assert app_pc*2==BOOT-4,(hex(app_pc*2),hex(BOOT-4))
 # Decode code pointer refs by original known source label + opcode distances
 erase=optsy['L1d6a']-4   # L1d6a preceded two ldi values at position -4; little endian near new boot address
 assert 0 <= erase < FLASH
 writehex(OUT/'micronucleus_t88_bootloader_only.hex',BOOT,body,with_reset=False)
 writehex(OUT/'micronucleus_t88_ISP_fresh.hex',BOOT,body,with_reset=True)
 table,st=audithex(OUT/'micronucleus_t88_ISP_fresh.hex')
 assert st==BOOT and table[0]==expected&255 and table[1]==expected>>8
 assert all(table[BOOT+i]==v for i,v in enumerate(body))
 isp=bytearray([0xff]*FLASH);isp[0]=expected&255;isp[1]=expected>>8;isp[BOOT:BOOT+len(body)]=body
 assert int.from_bytes(isp[BOOT-4:BOOT-2],'little')==0xffff, 'program postscript must be blank initially'
 (OUT/'micronucleus_t88_ISP_flash_image.bin').write_bytes(isp)
 (OUT/'micronucleus_t88_bootloader_body.bin').write_bytes(body)
 (OUT/'micronucleus_t88_optimized.S').write_bytes(SRC.read_bytes())
 (OUT/'micronucleus_t88_original_reconstructed.S').write_bytes(BASE.read_bytes())
 result={
  'target':'MH-ET LIVE ATtiny88 16MHz Micronucleus 2.6',
  'flash_bytes':FLASH,'page_bytes':FLASH_PAGE,'boot_addr_old':'0x1A40','boot_addr_new':f'0x{BOOT:04X}',
  'reference_bytes':len(upstream),'optimized_bytes':len(body),'saving_bytes':len(upstream)-len(body),
  'reserved_bytes_original':FLASH-0x1a40,'reserved_bytes_new':FLASH-BOOT,
  'free_tail_bytes':FLASH-BOOT-len(body),
  'user_capacity_original':0x1a40-4,'user_capacity_new':BOOT-4,
  'user_gain_bytes':BOOT-0x1a40,
  'user_reset_vector_patch_word':f'0x{expected:04X}',
  'critical_routines':segments,
  'all_software_tests_passed':True,
  'hardware_USB_tested':False,
  'warnings':['USB bit/CRC instructions byte-identical, but physical signal validation is still needed',
              'LED output disabled','Y register reused in non-USB main loop; firmware requires hardware testing before field deployment',
              'ISP erase/rewrite is needed for moving the bootloader; USB app upload does not replace bootloader']
 }
 (OUT/'audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 (OUT/'optimized_disassembly.txt').write_text(run('llvm-objdump','-d','--disassemble-zeroes',f'--start-address=0x{BOOT:x}',str(OUT/'micronucleus_t88_optimized.o')))
 print(json.dumps(result,indent=2,ensure_ascii=False))
 return result
if __name__=='__main__':check()
