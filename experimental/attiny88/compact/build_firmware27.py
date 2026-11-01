#!/usr/bin/env python3
"""Build verified Pass27 candidate images; never access programming hardware."""
from pathlib import Path
import hashlib
import json

from build_candidate import checked_build
from check_build import build
from audit_phy27 import audit_candidate
from host.compact_programmer27 import USB_PROFILES, record, parse_intel_hex, DEFAULT_FLASH_DELAY_MS

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'firmware27'
PROFILES = (('NONE', 'off', 0x0300), ('ACTIVE_HIGH', 'high', 0x0301),
            ('ACTIVE_LOW', 'low', 0x0302))


def main():
    OUT.mkdir(exist_ok=True)
    manifest = dict(
        candidate='Pass27 verified software checkpoint, 2026-10-27',
        validation_baseline='ce74532ebbd1d73fdcf1b47e15cb603a19ba52f3',
        source_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in sorted((ROOT / 'source').iterdir()) if path.is_file()},
        target='ATtiny88, external 16 MHz clock', protocol='v3.0',
        hardware_validated=False, fits_1024_bytes=False,
        hardware_tested_profiles=['NONE'], hardware_evidence='hardware30.json',
        toolchain='Clang/LLVM 18.1.3; GNU AVR binutils 2.26.20160125',
        limitations=['Incoming DATA CRC16 validation omitted by accepted design decision',
                     'Token CRC5/endpoint/length admission and ACK-driven retry remain open',
                     f'Host defaults to {DEFAULT_FLASH_DELAY_MS:g} ms quiet after Flash erase/page commit; configurable, same-board tested',
                     'Fresh ISP image erases application; RESET-page power loss needs ISP recovery'],
        builds=[])
    for mode, name, version in PROFILES:
        _, boot, expected = USB_PROFILES[version]
        artifact = checked_build(mode, boot)
        assert artifact['size'] == expected <= 8192 - boot, (
            'Frozen Pass27 builder requires the e405ea7 source checkpoint; '
            'do not overwrite release images with a size-reduction candidate', mode, artifact['size'], expected)
        reference = build(ROOT / 'variants/strict_usb_optimized/micronucleus_t88_pass26.S', mode, boot)
        audit_candidate(reference, artifact, '')
        descriptor = artifact['body'][20:38]
        assert int.from_bytes(descriptor[12:14], 'little') == version
        # RJMP wraps within the ATtiny88's 4096-word program address space.
        reset = (0xC000 | ((boot // 2 - 1) & 0xFFF)).to_bytes(2, 'little')
        displacement = int.from_bytes(reset, 'little') & 0xFFF
        if displacement & 0x800:
            displacement -= 4096
        assert (2 + 2 * displacement) % 8192 == boot
        image = bytearray([255] * 8192)
        image[:2] = reset
        image[boot:boot + expected] = artifact['body']
        assert image[boot - 4:boot] == bytes([255] * 4)
        prefix = 'Pass27_' + name
        body_file = prefix + '_body.bin'
        full_file = prefix + '_ISP_FRESH_8192.bin'
        hex_file = prefix + '_ISP_FRESH_EXPERIMENTAL.hex'
        (OUT / body_file).write_bytes(artifact['body'])
        (OUT / full_file).write_bytes(image)
        lines = [record(0, reset)]
        lines += [record(address, image[address:address + 16])
                  for address in range(boot, 8192, 16)]
        lines.append(record(0, b'', 1))
        text = '\n'.join(lines) + '\n'
        (OUT / hex_file).write_bytes(text.encode('ascii'))
        # Parse independently of the record writer and compare every emitted byte.
        parsed = parse_intel_hex(text)
        wanted = {0: reset[0], 1: reset[1]}
        wanted.update({address: image[address] for address in range(boot, 8192)})
        assert parsed == wanted
        manifest['builds'].append(dict(
            led=mode, bcdDevice=hex(version), boot_at=hex(boot),
            code_bytes=expected, reserved_bytes=8192 - boot, app_bytes=boot - 4,
            spare_bytes=8192 - boot - expected,
            led_ddr_io=hex(artifact['symbols']['led_config_ddr_io']),
            led_port_io=hex(artifact['symbols']['led_config_port_io']),
            led_pin=artifact['symbols']['led_config_pin'],
            body_file=body_file, isp_bin=full_file, isp_hex=hex_file,
            code_sha256=artifact['sha256'],
            isp_sha256=hashlib.sha256(image).hexdigest()))
        print('PASS', mode, expected, 'bytes, boot', hex(boot), 'BIN/HEX/RESET/PHY verified')
    (OUT / 'manifest.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
    files = sorted(path for path in OUT.iterdir()
                   if path.is_file() and path.name != 'SHA256SUMS.txt')
    checksums = [hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name
                 for path in files]
    (OUT / 'SHA256SUMS.txt').write_bytes(('\n'.join(checksums) + '\n').encode())


if __name__ == '__main__':
    main()
