#!/usr/bin/env python3
"""Build both firmware modes and check real descriptors, placements and C behavior."""
import argparse
import re
import os
from pathlib import Path
import subprocess
import sys
import build
from common import avr, verification

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path)
    parser.add_argument('--cc', default='cc')
    args = parser.parse_args()
    toolchain = avr.find_toolchain(args.toolchain)
    sys.path.insert(0, str(REPO / 'experimental/attiny88/compact'))
    from host import compact_programmer27 as programmer
    for simulate in (False, True):
        elf = build.build(toolchain, simulate)
        name = elf.stem
        binary = elf.with_suffix('.bin').read_bytes()
        symbols = verification.symbols(toolchain, elf)
        def data(symbol, size):
            return binary[symbols[symbol]:symbols[symbol] + size]
        device = data('usbDescriptorDevice', 18)
        assert device[:8] == bytes([18, 1, 0x10, 1, 0, 0, 0, 8])
        assert device[8:12] == bytes.fromhex('c016db27')
        cfg = data('usbDescriptorConfiguration', 34)
        assert cfg[:9] == bytes([9, 2, 34, 0, 1, 1, 0, 0x80, 50])
        assert cfg[9:18] == bytes([9, 4, 0, 0, 1, 3, 0, 0, 0])
        assert cfg[18:27] == bytes([9, 0x21, 0x11, 1, 0, 1, 0x22, 111, 0])
        assert cfg[27:] == bytes([7, 5, 0x81, 3, 8, 0, 10])
        desc = data('usbDescriptorHidReport', 111)
        bits, size, count, report_id = {}, 0, 0, 0
        for tag, value in verification.hid_items(desc):
            if tag == 0x74: size = value
            elif tag == 0x94: count = value
            elif tag == 0x84: report_id = value
            elif tag in (0x80, 0x90, 0xb0):
                bits[report_id, tag] = bits.get((report_id, tag), 0) + size * count
        assert bits == {(1, 0x80): 16, (4, 0x80): 56, (2, 0x90): 8, (5, 0x90): 8, (6, 0x90): 8, (3, 0xb0): 416}
        assert all((length + 8) // 8 <= 8 for (report, tag), length in bits.items() if tag == 0x80)
        cells = avr.read_hex(elf.with_suffix('.hex'), build.APPLICATION_LIMIT)
        verification.check_placement(binary, cells, symbols, programmer)
        disasm = avr.run_tool(toolchain, 'avr-objdump', '-d', elf)
        assert not any('spm' in line.split(';')[0].split() for line in disasm.splitlines())
        for bit in (3, 4, 5):
            for opcode in ('sbi', 'cbi'):
                assert re.search(r'\b%s\s+0x0b,\s*%d\b' % (opcode, bit), disasm), 'Layer LEDs must preserve USB PORTD bits atomically'
        exe = ROOT / 'build' / (name + '-test' + ('.exe' if os.name == 'nt' else ''))
        subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                        f'-DREMOTE_SIMULATE={int(simulate)}', '-I', str(ROOT),
                        str(ROOT / 'remote.c'), str(ROOT / 'tests/remote_test.c'),
                        '-o', str(exe)], check=True)
        scenarios = ('simulation',) if simulate else ('consumer', 'keyboard', 'layers', 'backpressure', 'validation')
        for scenario in scenarios:
            subprocess.run([str(exe), scenario], check=True)
    verification.verify_vendor()
    storage_test = ROOT / 'build' / ('storage-test.exe' if os.name == 'nt' else 'storage-test')
    subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT),
                    str(ROOT / 'remote.c'), str(ROOT / 'storage.c'), str(ROOT / 'control.c'), str(ROOT / 'tests/storage_test.c'),
                    '-o', str(storage_test)], check=True)
    subprocess.run([str(storage_test)], check=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py'],
                   cwd=ROOT, check=True)
    for source in ROOT.glob('*.py'):
        compile(source.read_text(encoding='utf-8'), str(source), 'exec')
    print('PASS: both modes, HID/placement, 6 input/layer scenarios, interrupted EEPROM saves, multi-packet HID and host tests')


if __name__ == '__main__':
    main()
