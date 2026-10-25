#!/usr/bin/env python3
"""Rebuild and verify the archived strict USB variant without flashing hardware."""
import hashlib

from build import BOOT_AT, ROOT, compile_asm, record


def main():
    variant = ROOT / 'variants/strict_usb_1328'
    body, syms = compile_asm(variant / 'micronucleus_t88_plus_strict.S', BOOT_AT, 'strict_1ac0')
    reference, ref_syms = compile_asm(ROOT / 'reference/Pass3_1216.S', 0x1B40, 'reference_pass3')
    assert len(body) == 1328
    assert body == (variant / 'BOOTLOADER_BODY_1AC0_STRICT_1328.bin').read_bytes()
    for first, last in [('usb_crc16_append', 'USB_handler'), ('USB_handler', 'usb_program_page')]:
        actual = body[syms[first] - BOOT_AT:syms[last] - BOOT_AT]
        expected = reference[ref_syms[first] - 0x1B40:ref_syms[last] - 0x1B40]
        assert actual == expected, f'Strict USB section differs: {first}'
        print(f'CHECK strict {first}: {len(actual)} byte-identical bytes')
    reset = (0xC000 | ((BOOT_AT // 2 - 1) & 0xFFF)).to_bytes(2, 'little')
    image = bytearray(b'\xff' * 8192)
    image[:2] = reset
    image[BOOT_AT:BOOT_AT + len(body)] = body
    lines = [record(0, image[:2])]
    lines += [record(a, image[a:a + 16]) for a in range(BOOT_AT, 8192, 16)
              if any(b != 255 for b in image[a:a + 16])]
    lines.append(record(0, b'', 1))
    assert '\n'.join(lines) + '\n' == (variant / 'ISP_FULL_1AC0_STRICT_FRESH_ONLY.hex').read_text()
    print('PASS: archived strict USB body and ISP HEX reproduced; 1328 bytes')
    print('sha256:', hashlib.sha256(body).hexdigest())


if __name__ == '__main__':
    main()
