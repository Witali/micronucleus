#!/usr/bin/env python3
"""Build an ATtiny88 application updater for the pinned or configured loader."""
from pathlib import Path
import argparse
import binascii
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
IMAGE_ADDRESS = 0x1AC0
EXPECTED = 'ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc'


def record(address, payload=b'', kind=0):
    data = bytes([len(payload), address >> 8, address & 255, kind]) + payload
    return ':' + (data + bytes([-sum(data) & 255])).hex().upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    manifests = parser.add_mutually_exclusive_group()
    manifests.add_argument('--firmware-manifest', type=Path,
                           help='firmware.json from build_verified.py, including LED variants')
    manifests.add_argument('--compact-manifest', type=Path,
                           help='Protocol3.0 compact firmware27/manifest.json')
    parser.add_argument('--led-profile', choices=('NONE', 'ACTIVE_HIGH', 'ACTIVE_LOW'), default='NONE',
                        help='Profile from --compact-manifest (default: NONE)')
    parser.add_argument('--output-dir', type=Path, help='Separate updater output directory')
    args = parser.parse_args()
    image_address = IMAGE_ADDRESS
    if args.compact_manifest:
        manifest_path = args.compact_manifest.resolve()
        firmware = json.loads(manifest_path.read_text())
        assert firmware['target'] == 'ATtiny88, external 16 MHz clock', 'Wrong compact target'
        assert firmware['protocol'] == 'v3.0', 'Unsupported compact protocol'
        selected = [item for item in firmware['builds'] if item['led'] == args.led_profile]
        assert len(selected) == 1, 'Missing or duplicate compact profile'
        profile = selected[0]
        image_address = int(profile['boot_at'], 0)
        assert 0x1800 <= image_address <= 0x1bc0 and image_address % 64 == 0, 'Invalid boot boundary'
        body_path = (manifest_path.parent / profile['body_file']).resolve()
        assert body_path.parent == manifest_path.parent, 'Image must be beside its manifest'
        image = body_path.read_bytes()
        assert len(image) == profile['code_bytes'] <= 8192 - image_address, 'Invalid code length'
        assert hashlib.sha256(image).hexdigest() == profile['code_sha256'], 'Compact body hash mismatch'
        assert profile['app_bytes'] == image_address - 4
        assert profile['reserved_bytes'] == 8192 - image_address
        # Compact3.0 has standard descriptors at the front, without legacy INFO.
        # Validate USB identity instead of interpreting descriptor bytes as INFO.
        descriptor = image[20:38]
        assert descriptor[:8] == bytes([18, 1, 0x10, 1, 0xff, 0, 0, 8]), 'Wrong USB descriptor'
        assert descriptor[8:12] == bytes([0xd0, 0x16, 0x53, 7]), 'Wrong USB VID/PID'
        assert int.from_bytes(descriptor[12:14], 'little') == int(profile['bcdDevice'], 0)
        assert int(profile['bcdDevice'], 0) == {'NONE': 0x0300, 'ACTIVE_HIGH': 0x0301,
                                              'ACTIVE_LOW': 0x0302}[args.led_profile]
        assert image[2:20] == bytes([9, 2, 18, 0, 1, 1, 0, 0x80, 50,
                                     9, 4, 0, 0, 0, 0, 0, 0, 0])
        default_build = ROOT / 'build' / ('compact30-' + args.led_profile.lower())
    elif args.firmware_manifest:
        manifest_path = args.firmware_manifest.resolve()
        firmware = json.loads(manifest_path.read_text())
        assert firmware['target'] == 'attiny88', 'Wrong target'
        image_address = firmware['image_address']
        assert 0x1800 <= image_address <= 0x1b00 and image_address % 64 == 0, 'Invalid boot boundary'
        image = (manifest_path.parent/firmware['body_file']).read_bytes()
        assert len(image) == firmware['code_bytes'] <= 8192-image_address, 'Invalid code length'
        assert hashlib.sha256(image).hexdigest() == firmware['body_sha256'], 'Body hash mismatch'
        assert firmware['application_bytes'] == image_address-4
        default_build = manifest_path.parent/'updater'
    else:
        image = (ROOT.parent / 'variants/strict_usb_verified/BOOTLOADER_BODY_1AC0_VERIFIED.bin').read_bytes()
        assert len(image) == 1344 and hashlib.sha256(image).hexdigest() == EXPECTED
        default_build = ROOT/'build'
    if not args.compact_manifest:
        assert int.from_bytes(image[2:4], 'big') == image_address-4, 'Descriptor capacity mismatch'
        assert image[4] == 64 and image[6:8] == bytes([0x93, 0x11]), 'Wrong page size or device signature'
    body_sha256 = hashlib.sha256(image).hexdigest()
    build = (args.output_dir or default_build).resolve()
    build.mkdir(parents=True, exist_ok=True)
    code_bytes = len(image)
    image = image.ljust(8192 - image_address, b'\xff')
    (build/'bootloader-image.bin').write_bytes(image)
    crc = binascii.crc_hqx(image, 0xffff)
    header = '#include <avr/pgmspace.h>\n'
    header += f'#define IMAGE_ADDRESS 0x{image_address:X}u\n#define IMAGE_CRC 0x{crc:04X}u\n'
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
    assert 0x80 + len(body) < min(0x1800, image_address-64), 'Updater overlaps old/new loader or postscript'
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
    manifest = {'image_address': image_address, 'image_crc16_ccitt': crc,
                'image_sha256': body_sha256, 'padded_image_bytes': len(image),
                'padded_image_sha256': hashlib.sha256(image).hexdigest(),
                'image_file': 'bootloader-image.bin',
                'updater_end': 0x80 + len(body), 'symbols': symbols}
    if args.compact_manifest:
        manifest.update(protocol='v3.0', target='attiny88', led=args.led_profile,
                        bcdDevice=profile['bcdDevice'], code_bytes=code_bytes,
                        application_bytes=image_address - 4,
                        updater_hex_sha256=hashlib.sha256((build/'updater.hex').read_bytes()).hexdigest())
    (build / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('PASS: updater application end', hex(manifest['updater_end']),
          f'; target 0x{image_address:04X}, code {code_bytes} bytes, padded to', len(image), '; CRC', hex(crc))
    print('Output:', build / 'updater.hex')


if __name__ == '__main__':
    main()
