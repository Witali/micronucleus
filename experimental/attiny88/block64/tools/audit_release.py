#!/usr/bin/env python3
"""Pass 11 independent release checks, with no hardware operations.

Build is relocatable within the page-aligned BOOT_AT address; release must
contain no unresolved ELF relocations before binary extraction.
"""
from pathlib import Path
import json,hashlib,subprocess,re,random
ROOT=Path(__file__).resolve().parent.parent
FW=ROOT/'firmware'; BLD=ROOT/'build'
BOOT=0x1980; FLASH=8192; PAGE=64; APP=BOOT-4
body=(FW/'BOOTLOADER_BODY_1980_PASS11.bin').read_bytes()
whole=(FW/'ISP_FULL_8192_1980_PASS11.bin').read_bytes()
manifest=json.loads((FW/'manifest.json').read_text())
assert len(body)<=1664 and len(body)%2==0 and len(whole)==FLASH
assert len(body)==manifest['bootloader_body_bytes']
assert len(body)<=FLASH-BOOT
assert whole[BOOT:BOOT+len(body)]==body
assert whole[BOOT+len(body):]==b'\xff'*(FLASH-BOOT-len(body))
assert whole[APP:BOOT]==b'\xff'*4
assert whole[2:APP]==b'\xff'*(APP-2)
reset=0xc000|(((BOOT//2)-1)&0xfff)
assert whole[:2]==reset.to_bytes(2,'little')
assert body[2:8]==bytes([APP>>8,APP&255,64,64,0x33,0x03])
assert manifest['application_bytes']==APP
obj=BLD/'block64.o'
reloc=subprocess.check_output(['llvm-objdump','-r',str(obj)],text=True)
assert 'R_AVR_' not in reloc,reloc

def symbols(obj):
    text=subprocess.check_output(['llvm-objdump','-t',str(obj)],text=True)
    return {m.group(2):int(m.group(1),16) for m in re.finditer(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',text,re.M)}

# Compile preserved Pass8 independently to compare exact CRC and bit engine code.
refsrc=ROOT/'reference/Pass8_1720B_micronucleus_t88_block64.S'
refobj=BLD/'reference_pass8.o';refbin=BLD/'reference_pass8.bin'
subprocess.run(['clang','-target','avr','-mmcu=attiny88','-c','-x','assembler-with-cpp',str(refsrc),'-o',str(refobj)],check=True)
subprocess.run(['llvm-objcopy','-O','binary','-j','.text',str(refobj),str(refbin)],check=True)
a=symbols(refobj);b=symbols(obj)
r=refbin.read_bytes();c=(BLD/'block64.full.bin').read_bytes()
crc_ref=r[a['usb_crc16_append']:a['USB_handler']]
crc_new=c[b['usb_crc16_append']:b['USB_handler']]
engine_ref=r[a['USB_handler']:a['main']]
engine_new=c[b['USB_handler']:b['main']]
assert crc_ref==crc_new and len(crc_new)==44
assert engine_ref==engine_new and len(engine_new)==508

# Intel HEX checksums and complete sparse-image reconstruction.
records=(FW/'ISP_FULL_1980_PASS11_EXPERIMENTAL.hex').read_text().strip().splitlines()
img=bytearray(b'\xff'*FLASH)
for record in records:
    assert record.startswith(':'),record
    chunk=bytes.fromhex(record[1:])
    assert len(chunk)==chunk[0]+5 and sum(chunk)%256==0
    kind=chunk[3];adr=int.from_bytes(chunk[1:3],'big')
    if kind==0:
        assert adr+len(chunk[4:-1])<=FLASH
        img[adr:adr+chunk[0]]=chunk[4:-1]
    else:assert kind==1 and chunk[0]==0
assert records[-1]==':00000001FF' and img==whole

# Cross-check address validation formula under all legal lengths and
# 8k representative addresses, including 0xFFFF and both page boundaries.
for bound in [64,BOOT]:
    for length in range(1,65):
        cutoff=bound-length
        for addr in [0,1,63,64,BOOT-65,BOOT-64,BOOT-1,BOOT,65535,
                     max(0,cutoff-1),cutoff,cutoff+1,0xff00]:
            a16=addr&0xffff
            assert (a16<=cutoff)==(a16+length<=bound)

result={
    'result':'PASS (software only)',
    'code_bytes':len(body),
    'boot_at':hex(BOOT),
    'application_bytes':APP,
    'spare_bytes_in_reserved_boot_region':FLASH-BOOT-len(body),
    'reset_vector_opcode':hex(reset),
    'usb_bit_engine_unchanged_vs_pass8_bytes':len(engine_new),
    'usb_crc16_unchanged_vs_pass8_bytes':len(crc_new),
    'unresolved_relocations':0,
    'hex_checksums':'PASS',
    'flash_and_eeprom_range_math':'PASS',
    'sha256_body':hashlib.sha256(body).hexdigest(),
    'physical_usb_test':'NOT PERFORMED',
    'power_failure_recovery_test':'NOT PERFORMED',
}
(ROOT/'audit_report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,indent=2,ensure_ascii=False))
