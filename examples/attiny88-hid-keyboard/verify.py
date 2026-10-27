#!/usr/bin/env python3
"""Offline checks of real firmware bytes, loader placement and C report logic."""
import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import build

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def rjmp_target(data, address):
    word = int.from_bytes(data[address:address + 2], 'little')
    assert word & 0xF000 == 0xC000, 'Expected a normal ATtiny88 RJMP vector'
    offset = word & 0xFFF
    if offset & 0x800:
        offset -= 0x1000
    return (address + 2 + 2 * offset) % 8192


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path)
    parser.add_argument('--cc', default='cc', help='Native C compiler for behavior tests')
    args = parser.parse_args()
    toolchain = build.find_toolchain(args.toolchain)
    elf = build.build(toolchain)
    binary = (ROOT / 'build/keyboard.bin').read_bytes()
    symbols = {}
    for line in build.run_tool(toolchain, 'avr-nm', '-n', '--defined-only', elf).splitlines():
        address, _, name = line.split()
        symbols[name] = int(address, 16)

    def data(name, size):
        start = symbols[name]
        return binary[start:start + size]

    device = data('usbDescriptorDevice', 18)
    assert device[:8] == bytes([18, 1, 0x10, 1, 0, 0, 0, 8])
    assert device[8:12] == bytes.fromhex('c016db27')
    assert device[16] == 0  # No serial or personal information in the device identity.
    config = data('usbDescriptorConfiguration', 34)
    assert config[:9] == bytes([9, 2, 34, 0, 1, 1, 0, 0x80, 50])
    assert config[9:18] == bytes([9, 4, 0, 0, 1, 3, 1, 1, 0])
    assert config[18:27] == bytes([9, 0x21, 0x11, 1, 0, 1, 0x22, 63, 0])
    assert config[27:] == bytes([7, 5, 0x81, 3, 8, 0, 10])

    report = data('usbDescriptorHidReport', 63)
    assert report[:6] == bytes.fromhex('05010906a101') and report[-1] == 0xC0
    bits = {0x80: 0, 0x90: 0}  # Input and Output Main items.
    size = count = position = 0
    while position < len(report):
        prefix = report[position]
        length = (0, 1, 2, 4)[prefix & 3]
        tag = prefix & 0xFC
        value = int.from_bytes(report[position + 1:position + 1 + length], 'little')
        if tag == 0x74:
            size = value
        elif tag == 0x94:
            count = value
        elif tag in bits:
            bits[tag] += size * count
        assert tag != 0x84, 'Boot keyboard must not use report IDs'
        position += 1 + length
    assert bits == {0x80: 64, 0x90: 8}

    assert rjmp_target(binary, 0) > 2
    assert rjmp_target(binary, 2) == symbols['__vector_1']
    assert symbols['__vector_1'] != symbols['__bad_interrupt']
    disassembly = build.run_tool(toolchain, 'avr-objdump', '-d', elf)
    assert not any('spm' in line.split(';')[0].split() for line in disassembly.splitlines())
    sys.path.insert(0, str(REPO / 'experimental/attiny88/compact'))
    from host import compact_programmer27 as programmer
    cells = build.read_hex(ROOT / 'build/keyboard.hex')
    for _, boot_at, _ in programmer.USB_PROFILES.values():
        prepared = programmer.pack_application(cells, boot_at=boot_at)
        for address, value in cells.items():
            if address >= 2:
                assert prepared.image[address] == value
        assert rjmp_target(prepared.image, 0) == boot_at
        assert rjmp_target(prepared.image, boot_at - 4) == rjmp_target(binary, 0)
        assert prepared.image[boot_at - 2:boot_at] == b'\xff\xff'
    print('PASS: descriptors, RESET/INT0 vectors, compact 3.0 placement, no SPM')

    for line in (ROOT / 'usbdrv/SHA256SUMS').read_text(encoding='ascii').splitlines():
        expected, name = line.split()
        assert hashlib.sha256((ROOT / 'usbdrv' / name).read_bytes()).hexdigest() == expected
    print('PASS: pinned V-USB sources are unchanged')
    test = ROOT / 'build' / ('keyboard-test.exe' if os.name == 'nt' else 'keyboard-test')
    subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT),
                    str(ROOT / 'keyboard.c'), str(ROOT / 'tests/keyboard_test.c'),
                    '-o', str(test)], check=True)
    for scenario in ('sequence', 'backpressure', 'idle', 'reset'):
        subprocess.run([str(test), scenario], check=True)
    print('PASS: C keyboard behavior (4 scenarios)')


if __name__ == '__main__':
    main()
