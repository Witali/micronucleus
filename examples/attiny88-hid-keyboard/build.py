#!/usr/bin/env python3
"""Build the application HEX offline; never open or program a USB device."""
import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from common import avr
from common.avr import find_toolchain, run_tool

# Fits the previous 2.8 loader as well as every recognized compact 3.0 profile.
APPLICATION_LIMIT = 0x1AFC


def read_hex(path):
    return avr.read_hex(path, APPLICATION_LIMIT)


def build(toolchain):
    elf, flash, ram = avr.build_hid(toolchain, ROOT, 'keyboard', ('main.c', 'keyboard.c'),
                                    APPLICATION_LIMIT, 384)
    hexfile = elf.with_suffix('.hex')
    print(f'Application: {flash} Flash bytes; {ram}/512 static SRAM bytes')
    print('HEX SHA-256:', hashlib.sha256(hexfile.read_bytes()).hexdigest())
    print('Output:', hexfile)
    return elf


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, help='Directory containing avr-gcc and AVR binutils')
    args = parser.parse_args()
    build(find_toolchain(args.toolchain))
