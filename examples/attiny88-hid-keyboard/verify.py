#!/usr/bin/env python3
"""Offline checks of real firmware bytes, loader placement and C report logic."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import build
from common import avr, verification

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path)
    parser.add_argument('--cc', default='cc', help='Native C compiler for behavior tests')
    args = parser.parse_args()
    toolchain = build.find_toolchain(args.toolchain)
    elf = build.build(toolchain)
    binary = (ROOT / 'build/keyboard.bin').read_bytes()
    symbols = verification.symbols(toolchain, elf)

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
    size = count = 0
    for tag, value in verification.hid_items(report):
        if tag == 0x74:
            size = value
        elif tag == 0x94:
            count = value
        elif tag in bits:
            bits[tag] += size * count
        assert tag != 0x84, 'Boot keyboard must not use report IDs'
    assert bits == {0x80: 64, 0x90: 8}

    disassembly = build.run_tool(toolchain, 'avr-objdump', '-d', elf)
    assert not any('spm' in line.split(';')[0].split() for line in disassembly.splitlines())
    sys.path.insert(0, str(REPO / 'experimental/attiny88/compact'))
    from host import compact_programmer27 as programmer
    cells = build.read_hex(ROOT / 'build/keyboard.hex')
    verification.check_placement(binary, cells, symbols, programmer)
    print('PASS: descriptors, RESET/INT0 vectors, compact 3.0 placement, no SPM')

    verification.verify_vendor()
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
