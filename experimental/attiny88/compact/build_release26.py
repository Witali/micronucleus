#!/usr/bin/env python3
"""Reproducible Pass26 build: experimental V-USB, NO actual device programming."""
from pathlib import Path
import hashlib,json
from check_build import build
from host.compact_programmer import FLASH_SIZE,PAGE_BYTES,record,USB_VID,USB_PID,USB_PROFILES
from audit_phy26 import audit
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass26.S'
OUT=ROOT/'firmware';OUT.mkdir(exist_ok=True)
profiles=(('NONE','off',0x0550,0x1B40,1206),('ACTIVE_HIGH','high',0x0551,0x1B00,1220),('ACTIVE_LOW','low',0x0552,0x1B00,1218))
manifest={
 'release':'Micronucleus+ Pass26, research candidate (not hardware validated)',
 'date':'2026-10-27','target':'ATtiny88 / 16 MHz','protocol':'USB control v5.5; auto-increment cursor; fixed READ8/WRITE4; Select+Erase',
 'flash_bytes':FLASH_SIZE,'page_bytes':PAGE_BYTES,'eeprom_bytes':64,
 'usb_vid':hex(USB_VID),'usb_pid':hex(USB_PID),
 'warning':'No actual USB or ISP hardware verification. Inherits Pass25 RX-entry 4-cycle phase shift; RX r23 remap is still hardware-unverified; Power loss during RESET page erase may break boot.',
 'builds':[]}
for mode,name,version,boot,expected in profiles:
 r=build(SRC,mode,boot)
 assert r['size']==expected,(name,r['size'],expected)
 assert r['size']<=FLASH_SIZE-boot
 assert USB_PROFILES[version]==(f'Pass26 / {"no LED; 19 pages" if name=="off" else "LED active-high" if name=="high" else "LED active-low"}',boot,expected)
 phy_size=r['symbols']['flash_buffer_append_word']-r['symbols']['USB_handler']
 assert phy_size==492,phy_size
 audit(mode,boot)
 start=r['symbols']['USB_handler']-boot
 desc=r['body'][start-18:start]
 assert len(desc)==18
 assert int.from_bytes(desc[12:14],'little')==version,(name,desc.hex())
 reset=(0xc000 | ((boot//2-1)&0x0fff)).to_bytes(2,'little')
 image=bytearray(b'\xff'*FLASH_SIZE)
 image[0:2]=reset
 image[boot:boot+len(r['body'])]=r['body']
 assert image[boot-4:boot]==b'\xff'*4
 prefix=f'Pass26_{name}'
 (OUT/f'{prefix}_body.bin').write_bytes(r['body'])
 (OUT/f'{prefix}_ISP_FRESH_8192.bin').write_bytes(image)
 lines=[record(0,reset)]
 for offset in range(boot,FLASH_SIZE,16):
  lines.append(record(offset,image[offset:offset+16]))
 lines.append(record(0,b'',1))
 (OUT/f'{prefix}_ISP_FRESH_EXPERIMENTAL.hex').write_text('\n'.join(lines)+'\n')
 info=dict(led=mode,bcdDevice=hex(version),boot_at=hex(boot),code_bytes=r['size'],
  reserved_flash_bytes=FLASH_SIZE-boot,app_bytes=boot-4,USB_PHY_bytes=phy_size,
  code_sha256=r['sha256'],full_sha256=hashlib.sha256(image).hexdigest(),
  body_file=f'{prefix}_body.bin',reset_vector_word=hex(int.from_bytes(reset,'little')))
 manifest['builds'].append(info)
 print('PASS',name,'body',r['size'],'PHY',phy_size,'APP',boot-4,'bcdDevice',hex(version))
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
 entries=[]
 for p in sorted(OUT.iterdir()):
  if p.is_file() and p.name!='SHA256SUMS.txt':entries.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}')
 (OUT/'SHA256SUMS.txt').write_text('\n'.join(entries)+'\n')
 print('PASS PASS26: all firmware artifacts generated without hardware programming')
