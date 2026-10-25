#!/usr/bin/env python3
"""Check the USB whitelist and reject changes to flags, operands and branches."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'tests'))
from source_labels import with_semantic_names
from usb_engine_audit import audit_usb_engine, audit_reply_crc, decode_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifests',nargs='+',type=Path)
    args = parser.parse_args()
    reference = (ROOT.parent/'variants/strict_usb_verified/BOOTLOADER_BODY_1AC0_VERIFIED.bin').read_bytes()
    for file in args.manifests:
        meta = json.loads(file.read_text())
        body = (file.parent/meta['body_file']).read_bytes()
        base, symbols = meta['image_address'], meta['symbols']
        reference_symbols = with_semantic_names(meta['baseline_symbols'])
        def audit(candidate):
            audit_usb_engine(reference,0x1ac0,reference_symbols,candidate,base,symbols)
        audit(body)
        audit_reply_crc(reference,0x1ac0,reference_symbols,body,base,symbols)
        branch = next(item.address for item in decode_engine(body,base,symbols)
                      if item.op in {'brbc','brbs'})
        # A one-bit mutation must not sneak through normalized comparison:
        # SBI's flag, STD's displacement, the tested SREG bit, or branch target.
        mutations = [(symbols['usb_rx_overflow'],1),
                     (symbols['usb_rx_store_token'],1), (branch,1), (branch,8)]
        for address, mask in mutations:
            broken = bytearray(body)
            broken[address-base] ^= mask
            try:
                audit(bytes(broken))
            except AssertionError:
                continue
            raise AssertionError(f'USB audit accepted mutation at {address:#x}, mask {mask:#x}')
        for address in [symbols['usb_tx_copy_flash_payload'],symbols['usb_crc16_mix_byte'],
                        symbols['usb_crc16_core_end']+2]:
            broken=bytearray(body);broken[address-base]^=1
            try:
                audit_reply_crc(reference,0x1ac0,reference_symbols,bytes(broken),base,symbols)
            except AssertionError:
                continue
            raise AssertionError(f'CRC audit accepted mutation at {address:#x}')
        print(f'PASS: {file.parent.name}: exact USB whitelist, branch/skip mapping, '
              'Z-pointer proof, R17 liveness, CRC recurrence and seven rejected opcode mutations')


if __name__ == '__main__':
    main()
