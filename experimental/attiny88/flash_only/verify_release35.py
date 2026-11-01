#!/usr/bin/env python3
"""Read back released images/Intel HEX and check hashes, size, layout, identity."""
import hashlib
import json
from pathlib import Path
from host.image_core import parse_intel_hex
from make_release35 import PROFILES
ROOT=Path(__file__).resolve().parent
F=ROOT/'firmware35'

def check():
    m=json.loads((F/'manifest.json').read_text(encoding='utf8'))
    assert not m['installed_or_hardware_tested']
    for led,boot,size,bcd,suffix in PROFILES:
        q=next(x for x in m['builds'] if x['led']==led)
        body=(F/q['body_file']).read_bytes()
        whole=(F/q['isp_bin']).read_bytes()
        records=parse_intel_hex((F/q['isp_hex']).read_text(encoding='ascii'))
        assert len(body)==size and len(whole)==8192
        assert whole[boot:boot+size]==body
        assert whole[boot+size:]==b'\xff'*(8192-boot-size)
        assert whole[2:boot]==b'\xff'*(boot-2)
        assert whole[boot-4:boot]==b'\xff'*4
        assert int.from_bytes(whole[:2],'little')==0xc000|((boot//2-1)&0xfff)
        assert all(records.get(i,255)==v for i,v in enumerate(whole))
        assert bytes.fromhex(q['code_sha256'])==hashlib.sha256(body).digest()
        assert bytes.fromhex(q['isp_sha256'])==hashlib.sha256(whole).digest()
        assert int.from_bytes(body[32:34],'little')==bcd
        assert boot+size<=8192
        print(f'PASS {led} binary/HEX/RESET/postscript descriptor: {size} code bytes')
    for line in (F/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        expected,filename=line.split('  ')
        assert hashlib.sha256((F/filename).read_bytes()).hexdigest()==expected,filename
    print('PASS SHA-256 manifest and release files')
if __name__=='__main__':check()
