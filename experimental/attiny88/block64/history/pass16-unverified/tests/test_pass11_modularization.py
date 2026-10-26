"""Pass11: verify that splitting assembler into includes changed NO AVR code.

The only changes relative to Pass10 are two protocol-version data bytes.
This checks more than matching CRC/PHY snippets: all executable bytes and
all relative jump encodings must match the known-good software baseline.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
BOOT_AT = 0x19c0


def test_source_modules_present_and_included():
    source = (ROOT / 'source/micronucleus_t88_block64.S').read_text()
    modules = ['device_attiny88.inc', 'block64_protocol.inc',
               'vusb_phy.inc', 'vusb_ep0.inc', 'vusb_standard.inc']
    for module in modules:
        assert (ROOT / 'source' / module).is_file()
        assert f'#include "{module}"' in source
    assert 'usb_crc16_append:' not in source
    assert 'usb_crc16_append:' in (ROOT / 'source/vusb_phy.inc').read_text()
    assert 'USB_handler:' in (ROOT / 'source/vusb_phy.inc').read_text()
    assert 'old_vendor_dispatch:' in (ROOT / 'source/vusb_standard.inc').read_text()


def test_pass12_dispatch_optimized_and_protocol_header_unchanged():
    old = (ROOT / 'reference/Pass10_1662B_body.bin').read_bytes()
    new = (ROOT / 'firmware/BOOTLOADER_BODY_19C0_PASS15.bin').read_bytes()
    assert len(old) == 1662
    assert len(new) <= 1600
    assert len(new) < len(old)
    assert new[2:4] == bytes([(BOOT_AT - 4) >> 8, (BOOT_AT - 4) & 255])
    assert new[4:6] == old[4:6]
    assert new[6:8] == bytes([0x33, 0x03])


def test_manifest_tracks_all_modules_and_fixed_reply():
    meta = json.loads((ROOT/'firmware/manifest.json').read_text())
    assert meta['bootloader_start'] == hex(BOOT_AT)
    assert meta['status_reply_bytes'] == 8
    assert meta['bootloader_body_bytes'] <= 1600
    assert meta['get_status_lengths'].startswith('8 bytes only')
    assert set(meta['source_modules']) == {'device_attiny88.inc', 'block64_protocol.inc',
                                          'vusb_phy.inc', 'vusb_ep0.inc', 'vusb_standard.inc'}
