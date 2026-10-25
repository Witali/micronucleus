#!/usr/bin/env python3
"""Audit Intel HEX ranges and ATtiny88 bootloader page accounting (stdlib only)."""
import argparse
import json
from pathlib import Path

FLASH_BYTES = 8192
PAGE_BYTES = 64
POSTSCRIPT_BYTES = 4  # Micronucleus t88_default: OSCCAL_SAVE_CALIB == 0


def parse_hex(path):
    data = {}
    ext_linear = 0
    start_address = None
    records = 0
    for lineno, raw in enumerate(Path(path).read_text().splitlines(), 1):
        if not raw.strip():
            continue
        assert raw.startswith(':'), f'line {lineno}: missing colon'
        b = bytes.fromhex(raw[1:].strip())
        assert len(b) >= 5 and b[0] == len(b)-5, f'line {lineno}: wrong length'
        assert sum(b) % 256 == 0, f'line {lineno}: wrong checksum'
        length, address, kind = b[0], int.from_bytes(b[1:3], 'big'), b[3]
        payload = b[4:-1]
        if kind == 0:
            for i,v in enumerate(payload):
                a = ext_linear + address + i
                assert a not in data, f'line {lineno}: duplicate 0x{a:04x}'
                data[a] = v
            records += 1
        elif kind == 4:
            assert length == 2
            ext_linear = int.from_bytes(payload, 'big') << 16
        elif kind == 5:
            assert length == 4
            start_address = int.from_bytes(payload, 'big')
        elif kind == 1:
            break
        elif kind == 3:
            # Start segment address, not additional flash data
            pass
        else:
            raise ValueError(f'line {lineno}: unsupported record type {kind}')
    assert data, 'No flash data found'
    lo, hi = min(data), max(data)+1
    assert hi <= FLASH_BYTES, f'Image extends beyond flash 0x{hi:04X}'
    assert len(data) == hi-lo, 'HEX image is sparse; cannot equate span with code size'
    return {'code_start':lo, 'code_end_exclusive':hi, 'code_bytes':len(data),
            'free_after_code':FLASH_BYTES-hi, 'records':records,
            'start_address_record':start_address,
            'reserved_bootloader_bytes':FLASH_BYTES-lo,
            'user_code_limit':lo-POSTSCRIPT_BYTES,
            'pages_reserved':(FLASH_BYTES-lo)//PAGE_BYTES}


def main():
    pa=argparse.ArgumentParser()
    pa.add_argument('hexfile')
    pa.add_argument('--json',action='store_true')
    args=pa.parse_args()
    result=parse_hex(args.hexfile)
    if args.json:
        print(json.dumps(result,indent=2))
    else:
        print(f"{Path(args.hexfile).name}: {result['code_bytes']} B code, "
              f"0x{result['code_start']:04X}..0x{result['code_end_exclusive']-1:04X}; "
              f"reserved {result['reserved_bootloader_bytes']} B; "
              f"user program <= {result['user_code_limit']} B")

if __name__=='__main__':
    main()
