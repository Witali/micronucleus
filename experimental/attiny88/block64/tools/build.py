#!/usr/bin/env python3
"""Reproducible assembler build and Intel HEX generation; NEVER flashes hardware."""
from pathlib import Path
import subprocess, json, hashlib, re
from avr_build import assemble
from layout import BOOT, FLASH, APP, RESERVED
ROOT=Path(__file__).resolve().parent.parent
SRC=ROOT/'source/micronucleus_t88_block64.S'
BUILD=ROOT/'build';FW=ROOT/'firmware'

def run(*args):return subprocess.check_output(list(args),stderr=subprocess.STDOUT,text=True)

def rec(addr, data, kind=0):
    base=bytes([len(data),(addr>>8)&255,addr&255,kind])+data
    return ':'+(base+bytes([(-sum(base))&255])).hex().upper()

def symbols(path):
    result={}
    for line in run('llvm-objdump','-t',str(path)).splitlines():
        match=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',line)
        if match:result[match.group(2)]=int(match.group(1),16)
    return result

def build():
    BUILD.mkdir(exist_ok=True); FW.mkdir(exist_ok=True)
    obj=BUILD/'block64.o';raw=BUILD/'block64.full.bin'
    assemble(SRC, obj, raw)
    # llvm-objcopy extracts sections without resolving unknown ELF symbols.
    # Refuse to produce a supposedly flashable image with unresolved branches.
    relocation_report=run('llvm-objdump','-r',str(obj))
    assert 'R_AVR_' not in relocation_report, ('Unresolved AVR relocations:',relocation_report)
    binary=raw.read_bytes()
    assert binary[:BOOT]==bytes(BOOT),'Nonempty .text before loader region'
    body=binary[BOOT:]
    assert len(body)<=RESERVED,('Bootloader exceeds its explicit Flash reservation:',len(body),RESERVED)
    assert len(body)%2==0
    assert body[2:4]==bytes([APP>>8,APP&255])
    assert body[2:8]==bytes([APP>>8,APP&255,64,64,0x33,0x03])
    assert body[8:10]==b'\x09\x02' and body[0x26:0x28]==b'\x03\x03'
    assert binary[BOOT:BOOT+2]!=b'\xff\xff'
    image=bytearray(b'\xff'*FLASH)
    reset=0xC000|(((BOOT//2)-1)&0xFFF)
    image[0:2]=reset.to_bytes(2,'little')
    image[BOOT:BOOT+len(body)]=body
    assert image[APP:BOOT]==b'\xff'*4
    (FW/'bootloader.bin').write_bytes(body)
    (FW/'isp-full.bin').write_bytes(image)
    lines=[rec(0,image[:2])]
    for adr in range(BOOT,FLASH,16):
        part=image[adr:adr+16]
        if any(b!=255 for b in part):lines.append(rec(adr,part))
    lines.append(rec(0,b'',1))
    hexf=FW/'isp-fresh.hex'
    hexf.write_text('\n'.join(lines)+'\n')
    for line in lines:
        if not line.startswith(':'):continue
        blob=bytes.fromhex(line[1:]); assert sum(blob)%256==0
    sym=symbols(obj)
    (FW/'symbols.txt').write_text('\n'.join(f'{name:42s} 0x{addr:04X}' for name,addr in sorted(sym.items(),key=lambda pair:pair[1]))+'\n')
    manifest={
        'note':'EXPERIMENTAL DEVELOPMENT. Known USB transaction defects; not hardware verified.',
        'mcpu':'ATtiny88 16MHz external clock',
        'protocol_version':'3.3',
        'development_stage':'ACK-gated transfers, empty DATA CRC and cached token CRC5',
        'release_ready':False,
        'hardware_verified':False,
        'known_usb_contract_failures':['nonempty_data_ack_before_crc'],
        'body_file':'bootloader.bin',
        'isp_binary_file':'isp-full.bin',
        'isp_hex_file':'isp-fresh.hex',
        'bootloader_start':hex(BOOT),
        'bootloader_body_bytes':len(body),
        'reserved_flash_bytes':FLASH-BOOT,
        'application_bytes':APP,
        'flash_page_bytes':64,
        'eeprom_bytes':64,
        'flash_page_protocol':'separate ERASE_PAGE and 64-byte WRITE',
        'spm_guard':'own status ZLP acknowledged within bounded SOP window, then quiet interval',
        'usb_vid_pid':'16d0:0753',
        'protocol_commands':{'read':'0x10','write':'0x11','get_status':'0x12','run':'0x13','erase_page':'0x14'},
        'get_status_layout':['result','state','app_hi','app_lo','page_bytes','eeprom_bytes','protocol_marker','features'],
        'get_status_lengths':'8 bytes only (supported host contract; USB EP0 still clips to wLength)',
        'reset_vector_opcode':hex(reset),
        'critical_usb_code_bytes':sym['main']-sym['USB_handler'],
        'crc16_code_bytes':sym['USB_handler']-sym['usb_crc16_append'],
        'status_reply_bytes':8,
        'sha256_body':hashlib.sha256(body).hexdigest(),
        'sha256_full_binary':hashlib.sha256(image).hexdigest(),
        'sha256_source':hashlib.sha256(SRC.read_bytes()).hexdigest(),
        'source_modules': sorted(f.name for f in (ROOT/'source').glob('*.inc')),
        'sha256_source_modules': {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (ROOT/'source').glob('*.inc')},
    }
    (FW/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':build()
