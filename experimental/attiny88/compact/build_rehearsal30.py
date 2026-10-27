#!/usr/bin/env python3
"""Build a read-only protocol3.0 application trial; never program a device."""
import argparse
import hashlib
import json
from pathlib import Path

from check_build import build
from build_candidate import checked_build
from host.compact_programmer27 import record, parse_intel_hex

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed-capacity', type=int, required=True)
    args = parser.parse_args()
    capacity = args.installed_capacity
    assert (capacity + 4) % 64 == 0 and 0x1800 <= capacity < 0x1C00
    out = ROOT / 'build/rehearsal30'
    out.mkdir(parents=True, exist_ok=True)
    source = out / 'micronucleus_t88_rehearsal30.S'
    source.write_text('#define BOOT_VERSION_BCD 0x0390\n'
                      '#define COMPACT_REHEARSAL_READ_ONLY 1\n'
                      f'#include "{ROOT / "source/micronucleus_t88_compact.S"}"\n')
    artifact = build(source, 'NONE', 0x1000)
    normal = checked_build('NONE', 0x1000)
    assert 0x1000 + artifact['size'] < capacity - 64
    def phy(item):
        start, end = [item['symbols'][key] - item['boot'] for key in
                      ('USB_handler', 'flash_buffer_append_word')]
        return item['body'][start:end]
    assert phy(artifact) == phy(normal), 'Trial must preserve the production PHY'
    assert int.from_bytes(artifact['body'][32:34], 'little') == 0x0390
    wrapper = out / 'micronucleus_t88_rehearsal_entry.S'
    wrapper.write_text('    .text\n    .org 0x80\n    .global bootloader_start\nbootloader_start:\n'
                       '    cli\n    ldi r16, 2\n    out 0x3e, r16\n'
                       # Explicit RJMP encoding avoids assembler literal/PC-relative ambiguity.
                       '    ldi r16, 0xff\n    out 0x3d, r16\n    clr r1\n    .word 0xc7b9\n')
    entry = build(wrapper, 'NONE', 0x80)['body']
    assert len(entry) == 14 and entry[:2] == b'\xf8\x94'
    jump = int.from_bytes(entry[-2:], 'little') & 0xFFF
    if jump & 0x800:
        jump -= 4096
    assert 0x80 + len(entry) + 2 * jump == 0x1000
    lines = [record(0, (0xC03F).to_bytes(2, 'little')), record(0x80, entry)]
    lines += [record(0x1000 + offset, artifact['body'][offset:offset + 16])
              for offset in range(0, artifact['size'], 16)]
    lines.append(record(0, b'', 1))
    text = '\n'.join(lines) + '\n'
    image = parse_intel_hex(text)
    assert max(image) < capacity - 64
    assert not any(0xFC0 <= address < 0x1000 for address in image)
    (out / 'rehearsal.hex').write_text(text)
    (out / 'body.bin').write_bytes(artifact['body'])
    # Exercise all private request bytes at emitted opcodes, before any upload.
    from tests27 import nvm_opcodes
    for request in range(256):
        machine = nvm_opcodes.new_machine(artifact)
        machine.r[25] = request
        machine.ram.update({27: 0, 28: 0})
        machine.run('bootloader_handle_vendor_request', stop=('usb_rx_release_buffer',), limit=250)
        assert machine.r[2] == 0 and machine.r[3] in (0, 2)
        assert all(event[0] == 0x11 for event in machine.spms), (request, machine.spms)
        assert not any(event[1] in (0x1F, 0x20, 0x21) for event in machine.io_events)
    metadata = dict(protocol='3.0', bcdDevice='0x0390', read_only=True,
                    address=0x1000, body_bytes=artifact['size'],
                    last_hex_address=max(image), installed_application_bytes=capacity,
                    installed_boot_address=capacity + 4, phy_identical=True,
                    private_opcodes_verified=256,
                    body_sha256=hashlib.sha256(artifact['body']).hexdigest(),
                    hex_sha256=hashlib.sha256(text.encode()).hexdigest())
    (out / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))
    print('PASS application-only HEX; installed bootloader/postscript outside image')


if __name__ == '__main__':
    main()
