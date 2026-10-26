#!/usr/bin/env python3
"""Static release invariants; no programming of a physical board."""
from pathlib import Path
import json,hashlib,subprocess,re
ROOT=Path(__file__).resolve().parent.parent
FW=ROOT/'firmware'; BOOT=0x1940; FLASH=8192
manifest=json.loads((FW/'manifest.json').read_text())
body=(FW/'BOOTLOADER_BODY_1940_SPLIT.bin').read_bytes()
whole=(FW/'ISP_FULL_8192_1940_SPLIT.bin').read_bytes()
assert len(body)==1728
assert manifest['application_bytes']==BOOT-4
assert len(whole)==FLASH
assert whole[BOOT:]==body
assert whole[BOOT-4:BOOT]==b'\xff'*4
assert whole[2:BOOT-4]==b'\xff'*(BOOT-6)
assert whole[:2]==(0xc000|(((BOOT//2)-1)&0x0fff)).to_bytes(2,'little')
assert body[2:4]==bytes([(BOOT-4)>>8,(BOOT-4)&255])
assert body[8]==0xe3 and body[0x28:0x2a]==b'\x01\x03'
assert hashlib.sha256(body).hexdigest()==manifest['sha256_body']
text=(FW/'ISP_FULL_1940_SPLIT_EXPERIMENTAL.hex').read_text().splitlines()
records=[]
for line in text:
    assert line.startswith(':'),line
    r=bytes.fromhex(line[1:]); assert len(r)==r[0]+5 and sum(r)&255==0
    addr=int.from_bytes(r[1:3],'big'); typ=r[3]
    if typ==0:records.append((addr,r[4:-1]))
    else:assert typ==1 and r[0]==0
assert text[-1]==':00000001FF'
img=bytearray([0xff]*FLASH)
for a,b in records:
    assert a+len(b)<=FLASH
    img[a:a+len(b)]=b
assert bytes(img)==whole
source=(ROOT/'source/micronucleus_t88_block64.S').read_text()
assert '#define OP_ERASE_PAGE 0x14' in source
assert 'block_flash_erase_only:' in source
assert 'block_commit_flash:' in source
assert 'block_cache_flash_loop:' not in source
assert 'block_spm_after_quiet:' in source
# Confirm low-level USB+CRC unchanged against the original V-USB assembler.
subprocess.run(['clang','-target','avr','-mmcu=attiny88','-c','-x','assembler-with-cpp',
                str(ROOT/'reference/previous_bulk8_1344.S'),'-o',str(ROOT/'build/ref_1344.o')],check=True)
subprocess.run(['llvm-objcopy','-O','binary','-j','.text',str(ROOT/'build/ref_1344.o'),
                str(ROOT/'build/ref_1344.bin')],check=True)
def syms(path):
    t=subprocess.check_output(['llvm-objdump','-t',str(path)],text=True)
    return {m.group(2):int(m.group(1),16) for m in re.finditer(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',t,re.M)}
a=syms(ROOT/'build/ref_1344.o');b=syms(ROOT/'build/block64.o')
prev=(ROOT/'build/ref_1344.bin').read_bytes();curr=(ROOT/'build/block64.full.bin').read_bytes()
assert prev[a['usb_crc16_append']:a['USB_handler']]==curr[b['usb_crc16_append']:b['USB_handler']]
assert prev[a['USB_handler']:a['usb_program_page']]==curr[b['USB_handler']:b['main']]
result={'layout':'PASS','intel_hex_checksums':'PASS','crc16_bitcode_unchanged':True,
        'usb_bit_engine_unchanged':True,'boot_at':hex(BOOT),'app_bytes':BOOT-4,
        'firmware_code_bytes':len(body), 'sha256_body':hashlib.sha256(body).hexdigest(),
        'spm_physical_usb_hardware_test':'NOT PERFORMED'}
(ROOT/'docs/RELEASE_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
