#!/usr/bin/env python3
"""Build the experimental ATtiny88 Micronucleus EEPROM-extended bootloader.
No hardware flashing is done by this script.
"""
from __future__ import annotations
from pathlib import Path
import hashlib, re, subprocess

ROOT=Path(__file__).resolve().parent
BOOT_AT=0x1AC0
FLASH=8192
POSTSCRIPT=4
SOURCE=ROOT/'source/micronucleus_t88_plus.S'
ORIGINAL=ROOT/'reference/Pass3_1216.S'
DEVICE_INCLUDE=ROOT/'vendor/microchip/ATtiny_DFP-3.4.278/include'
EXPECTED_BODY_SHA256='6f573edc063f1e7751d551ac2ee3384ecfc92d807fa2db5e279e1d063327413d'


def command(*args):
    return subprocess.run(args,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout


def symbols(obj):
    result={}
    for line in command('llvm-objdump','-t',str(obj)).splitlines():
        m=re.match(r'^([0-9a-f]+)\s+\S+\s+(?:\.text|\*ABS\*)\s+[0-9a-f]+\s+(.+)$',line)
        if m: result[m[2]]=int(m[1],16)
    return result


def compile_asm(file,boot,outfile,defines=()):
    (ROOT/'build').mkdir(exist_ok=True)
    obj=ROOT/'build'/f'{outfile}.o'
    raw=ROOT/'build'/f'{outfile}.full.bin'
    command('clang','-target','avr','-mmcu=attiny88',f'-DBOOT_AT=0x{boot:04X}',
            '-I',str(DEVICE_INCLUDE),
            *(f'-D{define}' for define in defines),
            '-c','-x','assembler-with-cpp',str(file),'-o',str(obj))
    # LLVM 18 emits AVR branch relocations even for same-section labels.
    # Resolve them before extracting bytes; otherwise jumps remain placeholders.
    elf=ROOT/'build'/f'{outfile}.elf'
    command('avr-ld','--entry=bootloader_start','-Ttext=0',str(obj),'-o',str(elf))
    command('llvm-objcopy','-O','binary','-j','.text',str(elf),str(raw))
    contents=raw.read_bytes()
    assert all(b==0 for b in contents[:boot]), 'Build did not reserve lower Flash with zeros as expected'
    return contents[boot:],symbols(obj)


def record(addr,data=b'',typ=0):
    b=bytes([len(data),(addr>>8)&255,addr&255,typ])+data
    return ':'+(b+bytes([(-sum(b))&255])).hex().upper()


def main():
    (ROOT/'firmware').mkdir(exist_ok=True)
    boot,syms=compile_asm(SOURCE,BOOT_AT,'plus_1ac0')
    assert len(boot)<=FLASH-BOOT_AT, (len(boot),'exceeds reserved Flash')
    assert (len(boot)%2)==0
    assert boot[2:4]==bytes([(BOOT_AT-POSTSCRIPT)>>8,(BOOT_AT-POSTSCRIPT)&255])
    assert boot[8]==0xE0, f'Feature flags missing: {boot[8]:02X}'
    assert boot[0x28]==8 and boot[0x29]==2, 'Expected bcdDevice 2.8'
    rjmp=(0xc000|(((BOOT_AT//2)-1)&0x0fff)).to_bytes(2,'little')
    image=bytearray([0xff]*FLASH)
    image[0:2]=rjmp
    image[BOOT_AT:BOOT_AT+len(boot)]=boot
    assert bytes(image[BOOT_AT-POSTSCRIPT:BOOT_AT])==b'\xff'*4
    (ROOT/'firmware/BOOTLOADER_BODY_1AC0_PLUS.bin').write_bytes(boot)
    (ROOT/'firmware/ISP_FULL_8192_1AC0_FRESH_ONLY.bin').write_bytes(image)
    lines=[record(0,image[:2])]+[record(addr,image[addr:addr+16]) for addr in range(BOOT_AT,FLASH,16) if any(x!=255 for x in image[addr:addr+16])]
    lines.append(record(0,b'',1))
    (ROOT/'firmware/ISP_FULL_1AC0_PLUS_FRESH_ONLY.hex').write_text('\n'.join(lines)+'\n')
    base,bsyms=compile_asm(ORIGINAL,0x1B40,'reference_pass3')
    old_fast,ofsyms=compile_asm(ROOT/'reference/Pass5_Fast_1344.S',0x1AC0,'reference_pass5')
    assert old_fast==(ROOT/'reference/Pass5_Fast_1344.bin').read_bytes(), 'Pass5 baseline not reproducible'
    # USB-CRC must remain exactly identical. The USB bit engine is allowed
    # precisely three 2-cycle PCIFR stores and one 2-cycle SRAM store rewrite.
    # The maintained source uses semantic names. Reference objects retain
    # their historical symbol spelling; compare the same byte boundaries.
    for first,last,reference_last in [('usb_crc16_append','USB_handler','USB_handler'),
                                      ('USB_handler','flash_buffer_append_word','usb_program_page')]:
        a=boot[syms[first]-BOOT_AT:syms[last]-BOOT_AT]
        b=base[bsyms[first]-0x1B40:bsyms[reference_last]-0x1B40]
        if first=='usb_crc16_append':
            assert a==b, 'USB CRC changed!'
            print('CHECK V-USB CRC: 44 bytes byte-identical')
        else:
            assert len(b)==516 and len(a)==508
            print('CHECK USB handler size: 516 -> 508 bytes; structural proof in tests/test_usb_patch.py')

    assert syms['ee_ready'] < syms['ee_read'] < syms['ee_write'] < syms['ee_return_one'] < syms['flash_read']
    assert len(boot)==1320, 'Build size changed; re-audit before release'
    assert hashlib.sha256(boot).hexdigest()==EXPECTED_BODY_SHA256, 'Historical body changed; re-audit before release'
    print('PASS: code bytes:',len(boot),'range',hex(BOOT_AT),hex(BOOT_AT+len(boot)-1))
    print('PASS: EEPROM bit 0x40 / Flash Read bit 0x80 / MCUSR bit 0x20, version 2.8, app memory',BOOT_AT-POSTSCRIPT,'bytes')
    print('sha256:',hashlib.sha256(boot).hexdigest())
    print('WARNING: experimental ISP-only build; USB hardware tests outstanding.')

if __name__=='__main__': main()
