#!/usr/bin/env python3
"""Build both firmware modes and check real descriptors, placements and C behavior."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import build

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def target(data, at):
    word = int.from_bytes(data[at:at + 2], 'little')
    assert word & 0xf000 == 0xc000
    delta = word & 0xfff
    return (at + 2 + 2 * (delta - 0x1000 if delta & 0x800 else delta)) % 8192


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path)
    parser.add_argument('--cc', default='cc')
    args = parser.parse_args()
    toolchain = build.base.find_toolchain(args.toolchain)
    sys.path.insert(0, str(REPO / 'experimental/attiny88/compact'))
    from host import compact_programmer27 as programmer
    for simulate in (False, True):
        elf = build.build(toolchain, simulate)
        name = elf.stem
        binary = elf.with_suffix('.bin').read_bytes()
        symbols = {fields[2]: int(fields[0], 16)
                   for line in build.base.run_tool(toolchain, 'avr-nm', '-n', '--defined-only', elf).splitlines()
                   if len(fields := line.split()) == 3}
        def data(symbol, size):
            return binary[symbols[symbol]:symbols[symbol] + size]
        device = data('usbDescriptorDevice', 18)
        assert device[:8] == bytes([18, 1, 0x10, 1, 0, 0, 0, 8])
        assert device[8:12] == bytes.fromhex('c016d927')
        cfg = data('usbDescriptorConfiguration', 34)
        assert cfg[:9] == bytes([9, 2, 34, 0, 1, 1, 0, 0x80, 50])
        assert cfg[9:18] == bytes([9, 4, 0, 0, 1, 3, 0, 0, 0])
        assert cfg[18:27] == bytes([9, 0x21, 0x11, 1, 0, 1, 0x22, 56, 0])
        assert cfg[27:] == bytes([7, 5, 0x81, 3, 8, 0, 10])
        desc = data('usbDescriptorHidReport', 56)
        bits, pos, size, count, report_id = {}, 0, 0, 0, 0
        while pos < len(desc):
            prefix = desc[pos]
            length = (0, 1, 2, 4)[prefix & 3]
            tag = prefix & 0xfc
            value = int.from_bytes(desc[pos + 1:pos + 1 + length], 'little')
            if tag == 0x74: size = value
            elif tag == 0x94: count = value
            elif tag == 0x84: report_id = value
            elif tag in (0x80, 0x90, 0xb0):
                bits[report_id, tag] = bits.get((report_id, tag), 0) + size * count
            pos += 1 + length
        assert bits == {(1, 0x80): 16, (2, 0x90): 8, (3, 0xb0): 56}
        assert target(binary, 2) == symbols['__vector_1'] != symbols['__bad_interrupt']
        cells = build.base.read_hex(elf.with_suffix('.hex'))
        for _, boot_at, _ in programmer.USB_PROFILES.values():
            packed = programmer.pack_application(cells, boot_at=boot_at).image
            assert all(packed[at] == value for at, value in cells.items() if at >= 2)
            assert target(packed, 0) == boot_at
            assert target(packed, boot_at - 4) == target(binary, 0)
        disasm = build.base.run_tool(toolchain, 'avr-objdump', '-d', elf)
        assert not any('spm' in line.split(';')[0].split() for line in disasm.splitlines())
        exe = ROOT / 'build' / (name + '-test' + ('.exe' if os.name == 'nt' else ''))
        subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                        f'-DREMOTE_SIMULATE={int(simulate)}', '-I', str(ROOT),
                        str(ROOT / 'remote.c'), str(ROOT / 'tests/remote_test.c'),
                        '-o', str(exe)], check=True)
        scenarios = ('simulation',) if simulate else ('debounce', 'repeat', 'backpressure', 'mapping', 'led-idle')
        for scenario in scenarios:
            subprocess.run([str(exe), scenario], check=True)
    for line in (build.KEYBOARD / 'usbdrv/SHA256SUMS').read_text().splitlines():
        expected, name = line.split()
        assert hashlib.sha256((build.KEYBOARD / 'usbdrv' / name).read_bytes()).hexdigest() == expected
    storage_test = ROOT / 'build' / ('storage-test.exe' if os.name == 'nt' else 'storage-test')
    subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT),
                    str(ROOT / 'remote.c'), str(ROOT / 'storage.c'), str(ROOT / 'tests/storage_test.c'),
                    '-o', str(storage_test)], check=True)
    subprocess.run([str(storage_test)], check=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py'],
                   cwd=ROOT, check=True)
    for source in ('controller.py', 'windows_backend.py', 'protocol.py'):
        compile((ROOT / source).read_text(encoding='utf-8'), str(ROOT / source), 'exec')
    print('PASS: both modes, HID/placement, vendor hashes, 6 GPIO scenarios, EEPROM journal and 5 host tests')


if __name__ == '__main__':
    main()
