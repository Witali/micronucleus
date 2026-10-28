#!/usr/bin/env python3
"""Build reproducible Pass35 bare code and fresh-ISP reference images.

No hardware access. Flash-only 17-page ACK-safe experimental v4.1 variant.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from check_build import build

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'firmware35'
PROFILES=[('NONE',0x1bc0,1036,0x0450,'off'),
          ('ACTIVE_HIGH',0x1bc0,1056,0x0451,'high'),
          ('ACTIVE_LOW',0x1bc0,1054,0x0452,'low')]

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def intelhex_sparse(data:bytes)->str:
    lines=[]
    for start in range(0,len(data),16):
        chunk=data[start:start+16]
        if all(x==0xff for x in chunk):continue
        record=bytes([len(chunk),start>>8,start&255,0])+chunk
        lines.append(':'+ (record+bytes([(-sum(record))&255])).hex().upper())
    lines.append(':00000001FF')
    return '\n'.join(lines)+'\n'

def create():
    OUT.mkdir(exist_ok=True)
    builds=[];hashes=[]
    for led,boot,expected,bcd,suffix in PROFILES:
        a=build('source/micronucleus_t88_compact.S',mode=led,boot=boot)
        body=a['body']
        assert len(body)==expected and boot+len(body)<=8192,(led,len(body),expected)
        assert int.from_bytes(body[32:34],'little')==bcd
        assert body[:2]!=b'\xff\xff'
        reserved=8192-boot
        reset=0xc000|((boot//2-1)&0xfff)
        full=bytearray(b'\xff')*8192
        full[:2]=reset.to_bytes(2,'little')
        full[boot:boot+len(body)]=body
        stem='Pass35_'+suffix
        body_fn=stem+'_body.bin'
        isp_fn=stem+'_ISP_FRESH_8192.bin'
        hex_fn=stem+'_ISP_FRESH_EXPERIMENTAL.hex'
        (OUT/body_fn).write_bytes(body)
        (OUT/isp_fn).write_bytes(full)
        (OUT/hex_fn).write_text(intelhex_sparse(full),encoding='ascii')
        builds.append({'led':led,'bcdDevice':f'0x{bcd:04x}',
            'boot_at':f'0x{boot:04x}', 'code_bytes':len(body),
            'reserved_bytes':reserved,'app_bytes':boot-4,
            'postscript_at':f'0x{boot-4:04x}',
            'code_sha256':digest(body),'isp_sha256':digest(full),
            'body_file':body_fn,'isp_bin':isp_fn,'isp_hex':hex_fn,
            'usb_phy_bytes':a['symbols']['startup']-a['symbols']['USB_handler']})
        for fn in (body_fn,isp_fn,hex_fn):
            hashes.append((digest((OUT/fn).read_bytes()),fn))
        print(f'{led:12}: code {len(body):4} B; PHY {builds[-1]["usb_phy_bytes"]:3} B; boot=0x{boot:04x}; app={boot-4}; SHA256={digest(body)}')
    srcpaths=sorted((ROOT/'source').glob('*.inc'))+list((ROOT/'source').glob('*.S'))
    meta={'title':'Micronucleus+ Pass35, experimental v4.1, 2026-10-28',
          'target':'ATtiny88 external 16 MHz',
          'installed_or_hardware_tested':False,
          'protocol':'vendor v4.1: SELECT(1), SELECT+ERASE(2), WRITE2(3), RUN(4), COMMIT_PAGE(5), READ8(0xB0); absolute byte addresses',
          'ack':'IN DATA held until ACK; deferred Flash SPM and RUN blocked while TX DATA remains unacknowledged; ACK eligibility marker is short-lived; idempotent WRITE2; COMMIT unknown completion checked via readback',
          'remaining_limitations':['Incoming USB DATA CRC16 not validated before ACK',
             'USB token CRC5/endpoint admission incomplete',
             'Malformed or duplicate SETUP/OUT acceptance not fully USB 2.0 compliant',
             'No real hardware, analog waveform or hub testing',
             'Power loss during RESET-page erase/write may require ISP',
             'Flash SPM stalls CPU, host must wait before next USB request'],
          'source_sha256':{p.name:digest(p.read_bytes()) for p in srcpaths},
          'builds':builds}
    (OUT/'manifest.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    hashes.append((digest((OUT/'manifest.json').read_bytes()),'manifest.json'))
    (OUT/'SHA256SUMS.txt').write_text(''.join(f'{s}  {n}\n' for s,n in hashes),encoding='ascii')
    return meta
if __name__=='__main__':create()
