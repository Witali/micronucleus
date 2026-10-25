#!/usr/bin/env python3
"""Fix the two packet-level defects before preparing a hardware candidate.

Historical sources/images stay unchanged. USB RX/TX bit-engine bytes remain
identical; routing and RAM/Flash response copying are outside that engine.
"""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location('base_builder',ROOT.parent/'build.py')
    base = importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    spec = importlib.util.spec_from_file_location('image_records',ROOT/'build.py')
    helper = importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    source = (ROOT.parent/'variants/strict_usb_1328/micronucleus_t88_plus_strict.S').read_text()
    assert 'r2,' not in source and 'r2\n' not in source
    source = source.replace('    ldd     r24, Y+23\n    andi    r24, 0x60',
                            '    mov     r2, r1    /* New SETUP defaults to a Flash response. */\n'
                            '    ldd     r24, Y+23\n    andi    r24, 0x60',1)
    source = source.replace('L1dce:\n    mov     r7, r1\n',
                            'L1dce:\n    mov     r7, r1\n'
                            '    cpi     r25, 0xa0\n    brlo    legacy_vendor\n'
                            '    rjmp    L1f0c\nlegacy_vendor:\n',1)
    source = source.replace('    lpm     r25, Z+  /* same read and advance; LPM Rd,Z+ supported on tiny88 */',
                            '    sbrc    r2, 0\n    ld      r25, Z+\n'
                            '    sbrs    r2, 0\n    lpm     r25, Z+ /* Flash and SRAM have distinct address spaces. */',1)
    source = source.replace('    ldi     r19, 0x01                        /* repeated 16-bit pointer high */',
                            '    ldi     r19, 0x01                        /* repeated 16-bit pointer high */\n'
                            '    mov     r2, r19    /* Standard/EEPROM response buffer is SRAM. */',1)
    out = ROOT.parent/'variants/strict_usb_verified'
    out.mkdir(exist_ok=True)
    asm = out/'micronucleus_t88_verified.S';asm.write_text(source)
    body, symbols = base.compile_asm(asm,0x1ac0,'verified_1ac0')
    (ROOT/'build/verified-symbols.json').write_text(json.dumps(symbols))
    assert len(body)==1344, len(body)
    old, oldsym = base.compile_asm(ROOT.parent/'variants/strict_usb_1328/micronucleus_t88_plus_strict.S',0x1ac0,'strict_reference')
    for start,end in [('usb_crc16_append','USB_handler'),('USB_handler','usb_program_page')]:
        assert body[symbols[start]-0x1ac0:symbols[end]-0x1ac0]==old[oldsym[start]-0x1ac0:oldsym[end]-0x1ac0]
    (out/'BOOTLOADER_BODY_1AC0_VERIFIED.bin').write_bytes(body)
    image=bytearray(b'\xff'*8192);image[:2]=(0xcd5f).to_bytes(2,'little');image[0x1ac0:]=body
    lines=[helper.record(0,image[:2])]+[helper.record(a,image[a:a+16]) for a in range(0x1ac0,8192,16)]
    lines.append(helper.record(0,b'',1))
    (out/'ISP_FULL_1AC0_VERIFIED_FRESH_ONLY.hex').write_text('\n'.join(lines)+'\n')
    print('PASS: packet routing + SRAM reply correction; 1344 bytes; CRC and USB handler byte-identical')
    print('sha256:',hashlib.sha256(body).hexdigest())


if __name__=='__main__':main()
