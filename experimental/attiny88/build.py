#!/usr/bin/env python3
"""Build ATtiny88 Micronucleus assembly optimization pass 2. Needs clang(AVR backend), llvm-objcopy and llvm-objdump."""
from pathlib import Path
import subprocess, re
ROOT=Path(__file__).resolve().parent
BOOT=0x1B00
FLASH=8192
EXPECT=1230

def check_run(*argv):
 return subprocess.run(argv,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).stdout

def symbols(obj):
 s=check_run('llvm-objdump','-t',str(obj));found={}
 for line in s.splitlines():
  m=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',line)
  if m:found[m.group(2)]=int(m.group(1),16)
 return found

def record(addr,kind,data=b''):
 h=bytes([len(data),(addr>>8)&255,addr&255,kind])+data
 return ':'+(h+bytes([-sum(h)&255])).hex().upper()

def hex_lines(boot,body,reset):
 lines=[]
 if reset:lines.append(record(0,0,(0xc000|((boot//2-1)&0xfff)).to_bytes(2,'little')))
 for k in range(0,len(body),16): lines.append(record(boot+k,0,body[k:k+16]))
 lines += [record(0,3,bytes([0,0,(boot>>8)&255,boot&255])),':00000001FF']
 return '\n'.join(lines)+'\n'

def main():
 build=ROOT/'build';fw=ROOT/'firmware';build.mkdir(exist_ok=True);fw.mkdir(exist_ok=True)
 obj=build/'optimized.o';full=build/'with_org_zero_prefix_DO_NOT_FLASH.bin'
 check_run('clang','-target','avr','-mmcu=attiny88',f'-DBOOT_AT={BOOT}', '-c','-x','assembler-with-cpp',str(ROOT/'source/micronucleus_t88_optimized.S'),'-o',str(obj))
 check_run('llvm-objcopy','-O','binary','-j','.text',str(obj),str(full))
 data=full.read_bytes();assert len(data)<=FLASH
 body=data[BOOT:];assert len(body)==EXPECT,(len(body),EXPECT)
 sy=symbols(obj); old=(ROOT/'reference/previous_audited_1256.bin').read_bytes()
 assert sy['USB_handler']==BOOT+0x72
 assert sy['usb_program_page']-sy['USB_handler']==534
 assert body[sy['USB_handler']-BOOT:sy['usb_program_page']-BOOT]==old[0x72:0x72+534],'USB driver byte mismatch'
 assert body[sy['usb_crc16_append']-BOOT:sy['USB_handler']-BOOT]==old[0x46:0x46+44],'CRC byte mismatch'
 assert body[2:4]==bytes([((BOOT-4)>>8)&255,(BOOT-4)&255])
 assert len(body)<=FLASH-BOOT
 reset=(0xc000|((BOOT//2-1)&0xfff)).to_bytes(2,'little')
 image=bytearray([255]*FLASH);image[:2]=reset;image[BOOT:BOOT+len(body)]=body
 (fw/'bootloader_1230_body.bin').write_bytes(body)
 (fw/'ISP_FRESH_8192.bin').write_bytes(image)
 (fw/'ISP_FRESH_1B00.hex').write_text(hex_lines(BOOT,body,True))
 (fw/'BOOTLOADER_ONLY_NO_RESET.hex').write_text(hex_lines(BOOT,body,False))
 (build/'audited.o').write_bytes(obj.read_bytes())
 (build/'bootloader_body.bin').write_bytes(body)
 (build/'ISP_fresh.bin').write_bytes(image)
 print('PASS build: source -> 1230 B, 0x1B00, USB handler 534 B and CRC 44 B unchanged')
 print('WARNING Fresh ISP image erases app; do not attempt to USB-flash the bootloader through itself.')
if __name__=='__main__':main()
