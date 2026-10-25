#!/usr/bin/env python3
"""Build an ATtiny88 application updater around the pinned strict USB image."""
from pathlib import Path
import binascii
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
IMAGE_ADDRESS = 0x1AC0
EXPECTED = '850cecac7cd4e106443942982e9f1c409d70abffbaad6f718fc7450903dfeb18'


def record(address, payload=b'', kind=0):
    data = bytes([len(payload), address >> 8, address & 255, kind]) + payload
    return ':' + (data + bytes([-sum(data) & 255])).hex().upper()


def main():
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    image = (ROOT.parent / 'variants/strict_usb_verified/BOOTLOADER_BODY_1AC0_VERIFIED.bin').read_bytes()
    assert len(image) == 1344 and hashlib.sha256(image).hexdigest() == EXPECTED
    image = image.ljust(8192 - IMAGE_ADDRESS, b'\xff')
    crc = binascii.crc_hqx(image, 0xffff)
    header = '#include <avr/pgmspace.h>\n'
    header += f'#define IMAGE_ADDRESS 0x{IMAGE_ADDRESS:X}u\n#define IMAGE_CRC 0x{crc:04X}u\n'
    header += 'const uint8_t bootloader_image[] PROGMEM = {\n'
    header += ',\n'.join(','.join(f'0x{x:02x}' for x in image[i:i+16]) for i in range(0, len(image), 16))
    header += '\n};\n'
    (build / 'image.h').write_text(header)
    elf = build / 'updater.elf'
    subprocess.run(['avr-gcc', '-mmcu=attiny88', '-DF_CPU=16000000UL', '-Os', '-g',
                    '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-fno-jump-tables',
                    '-ffunction-sections', '-fdata-sections', '-I', str(build),
                    '-Wl,--relax,--gc-sections,--section-start=.text=0x80',
                    str(ROOT / 'updater.c'), '-o', str(elf)], check=True)
    subprocess.run(['avr-objcopy', '-O', 'binary', '-j', '.text', '-j', '.data', str(elf),
                    str(build / 'updater.body.bin')], check=True)
    body = (build / 'updater.body.bin').read_bytes()
    assert 0x80 + len(body) < 0x1800, 'Updater overlaps old/new loader or postscript'
    # The stock uploader redirects RESET to itself and saves this entry in its postscript.
    reset = (0xC000 | (0x80 // 2 - 1)).to_bytes(2, 'little')
    lines = [record(0, reset)]
    lines += [record(0x80 + i, body[i:i+16]) for i in range(0, len(body), 16)]
    lines.append(record(0, b'', 1))
    (build / 'updater.hex').write_text('\n'.join(lines) + '\n')
    flash = bytearray(b'\xff' * 8192)
    flash[:2] = reset
    flash[0x80:0x80 + len(body)] = body
    (build / 'updater.flash.bin').write_bytes(flash)
    symbols = {}
    for line in subprocess.check_output(['avr-nm', '-n', str(elf)], text=True).splitlines():
        cols = line.split()
        if len(cols) == 3:
            symbols[cols[2]] = int(cols[0], 16)
    manifest = {'image_address': IMAGE_ADDRESS, 'image_crc16_ccitt': crc,
                'image_sha256': EXPECTED, 'padded_image_bytes': len(image),
                'updater_end': 0x80 + len(body), 'symbols': symbols}
    (build / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('PASS: updater application end', hex(manifest['updater_end']),
          '; embedded corrected strict image 1344 bytes, padded to', len(image), '; CRC', hex(crc))
    print('Output:', build / 'updater.hex')


if __name__ == '__main__':
    main()
