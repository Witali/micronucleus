#!/usr/bin/env python3
"""Portable audited Micronucleus ATtiny88 assembler build / static safety gates.
Requires clang AVR backend + llvm-objcopy. Does not establish hardware USB stability.
"""
from pathlib import Path
import hashlib, subprocess
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'source/micronucleus_t88_audited.S'
OUT=ROOT/'build'
OUT.mkdir(exist_ok=True)
FLASH=8192;BOOT=0x1b00;REFERENCE=ROOT/'reference/upstream_t88_default.bin'

def run(*cmd):
 subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
def hx(addr,typ,payload=b''):
 buf=bytes([len(payload), (addr>>8)&255, addr&255,typ])+payload
 return ':'+(buf+bytes([-sum(buf)&255])).hex().upper()
def emit_hex(path,body,reset=True):
 data=[]
 if reset:
  reset_word=0xc000|(BOOT//2-1)&0xfff
  data.append(hx(0,0,reset_word.to_bytes(2,'little')))
 for offset in range(0,len(body),16):data.append(hx(BOOT+offset,0,body[offset:offset+16]))
 data.append(hx(0,3,bytes((0,0,BOOT>>8,BOOT&255))))
 data.append(':00000001FF')
 path.write_text('\n'.join(data)+'\n')

def main():
 obj=OUT/'audited.o'; binfile=OUT/'full_zero_padded_DO_NOT_FLASH.bin'
 run('clang','-target','avr','-mmcu=attiny88',f'-DBOOT_AT=0x{BOOT:x}', '-c','-x','assembler-with-cpp',str(SRC),'-o',str(obj))
 run('llvm-objcopy','-j','.text','-O','binary',str(obj),str(binfile))
 run('clang','-target','avr','-mmcu=attiny88', '-c',str(ROOT/'reference/original_reconstructed.S'),'-o',str(OUT/'original.o'))
 full=binfile.read_bytes()
 assert len(full)<=FLASH,'Loader goes beyond flash'
 body=full[BOOT:];assert 0<len(body)<=FLASH-BOOT
 ref=REFERENCE.read_bytes()
 # These V-USB subroutines MUST remain byte-identical.
 assert body[0x46:0x46+44]==ref[0x4c:0x4c+44],'CRC timing changed'
 assert body[0x72:0x72+534]==ref[0x78:0x78+534],'USB bit timing changed'
 assert body[2:4]==bytes(((BOOT-4)>>8,(BOOT-4)&255)),'User capacity descriptor wrong'
 vector=(0xc000|(BOOT//2-1)&0xfff).to_bytes(2,'little')
 assert len(body)==1256,('Unexpected assembled size; audit again before flashing',len(body))
 (OUT/'bootloader_body.bin').write_bytes(body)
 flash=bytearray(b'\xff'*FLASH);flash[:2]=vector;flash[BOOT:BOOT+len(body)]=body
 (OUT/'ISP_fresh.bin').write_bytes(flash)
 emit_hex(OUT/'ISP_fresh.hex',body,True)
 assert body==(ROOT/'firmware/bootloader_1256.bin').read_bytes(),'Binary mismatch to audited release'
 assert (OUT/'ISP_fresh.hex').read_bytes()==(ROOT/'firmware/ISP_FRESH_1B00.hex').read_bytes(),'HEX mismatch to audited release'
 print('PASS: body 1256 bytes, boot 0x1B00, app max 6908 bytes, CRC/USB bytes unchanged; reproducible HEX/BIN.')
 print('WARNING: Use ISP to install BOOTLOADER. USB upload writes only the APPLICATION, not the bootloader.')
 print('WARNING: Fresh ISP image erases existing user program. Hardware USB not tested.')
if __name__=='__main__':main()
