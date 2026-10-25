#!/usr/bin/env python3
"""Reproducible AVR assembly build of the V-USB optimized Micronucleus ATtiny88 loader.
Dependencies: LLVM clang with AVR backend, llvm-objcopy, llvm-objdump.
WARNING: output ISP_FULL image is for a spare/test board and erases the user application.
"""
from pathlib import Path
import re,subprocess,hashlib
ROOT=Path(__file__).resolve().parent
BOOT=0x1B40
FLASH=8192
POSTSCRIPT=4
SOURCE=ROOT/'source/micronucleus_t88_vusb_optimized.S'

def cmd(*args):
 p=subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 return p.stdout

def rec(address,data=b'',kind=0):
 b=bytes([len(data),(address>>8)&255,address&255,kind])+data
 return ':'+(b+bytes([(-sum(b))&255])).hex().upper()

def heximage(image,boot):
 lines=[rec(0,image[:2])]
 for addr in range(boot,FLASH,16):
  chunk=image[addr:addr+16]
  if any(v!=0xff for v in chunk):
   lines.append(rec(addr,chunk))
 lines.extend([rec(0,bytes([0,0,(boot>>8)&255,boot&255]),3),':00000001FF'])
 return '\n'.join(lines)+'\n'

def symbol_table(obj):
 out={}
 for l in cmd('llvm-objdump','-t',str(obj)).splitlines():
  m=re.match(r'^([a-fA-F0-9]+)\s+\S+\s+\.text\s+[a-fA-F0-9]+\s+(.+)$',l)
  if m: out[m.group(2)]=int(m.group(1),16)
 return out

def compile_source(source,obj,boot):
 cmd('clang','-target','avr','-mmcu=attiny88',f'-DBOOT_AT=0x{boot:04X}',
   '-c','-x','assembler-with-cpp',str(source),'-o',str(obj))
 raw=ROOT/'build'/f'{obj.stem}_with_leading_zeros_DO_NOT_FLASH.bin'
 cmd('llvm-objcopy','-O','binary','-j','.text',str(obj),str(raw))
 data=raw.read_bytes()
 assert len(data)<=FLASH,(obj,'image exceeds Flash')
 return data[boot:],symbol_table(obj)

def main():
 for fold in ('build','firmware'): (ROOT/fold).mkdir(exist_ok=True)
 bootobj=ROOT/'build/optimized_1b40.o'
 data,syms=compile_source(SOURCE,bootobj,BOOT)
 assert len(data)==1216,(len(data),1216)
 assert BOOT+len(data)<=FLASH
 assert data[2:4]==bytes([(BOOT-POSTSCRIPT)>>8,(BOOT-POSTSCRIPT)&255]),('descriptor',data[2:4])
 rjmp=(0xc000|(((BOOT//2)-1)&0x0fff)).to_bytes(2,'little')
 image=bytearray([255]*FLASH);image[:2]=rjmp;image[BOOT:BOOT+len(data)]=data
 assert image[BOOT-POSTSCRIPT:BOOT]==b'\xff'*4
 (ROOT/'firmware/BOOTLOADER_BODY_1B40_1216.bin').write_bytes(data)
 (ROOT/'firmware/ISP_FULL_8192_FRESH_ONLY.bin').write_bytes(image)
 (ROOT/'firmware/ISP_FULL_1B40_FRESH_ONLY.hex').write_text(heximage(image,BOOT))
 # A clean bootloader-only HEX deliberately lacks the reset vector. NOT a USB user firmware.
 lines=[rec(addr,data[addr-BOOT:addr-BOOT+16]) for addr in range(BOOT,FLASH,16)]
 (ROOT/'firmware/BOOT_ONLY_WITHOUT_RESET_DO_NOT_UPLOAD_USB.hex').write_text('\n'.join(lines+[':00000001FF'])+'\n')
 baseline,base_syms=compile_source(ROOT/'reference/pass2_1230.S',ROOT/'build/baseline_1b00.o',0x1b00)
 assert len(baseline)==1230
 (ROOT/'build/baseline_1b00.bin').write_bytes(baseline)
 assert data[syms['usb_crc16_append']-BOOT:syms['USB_handler']-BOOT] == baseline[base_syms['usb_crc16_append']-0x1b00:base_syms['USB_handler']-0x1b00], 'CRC should be untouched'
 (ROOT/'build/optimized_1b40.bin').write_bytes(data)
 # compatibility with test harnesses
 (ROOT/'build/base.bin').write_bytes(baseline)
 (ROOT/'build/base.o').write_bytes((ROOT/'build/baseline_1b00.o').read_bytes())
 (ROOT/'build/boot_1b40.bin').write_bytes(data)
 (ROOT/'build/boot_1b40.o').write_bytes(bootobj.read_bytes())
 sha=hashlib.sha256(data).hexdigest()
 print(f'PASS: Micronucleus ATtiny88 V-USB optimized: {len(data)}B at 0x{BOOT:04X}..0x{BOOT+len(data)-1:04X}; app max {BOOT-POSTSCRIPT}B; sha256 {sha}')
 print('NOTE: ISP_FULL images require external ISP and erase the user app. Hardware USB testing not yet performed.')
if __name__=='__main__':main()
