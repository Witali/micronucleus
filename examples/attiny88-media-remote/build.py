#!/usr/bin/env python3
"""Build independent GPIO-only and optional simulated-button media firmware."""
import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from common import avr

APPLICATION_LIMIT = 0x1AFC


def build(toolchain, simulate=False):
    name = 'remote-test' if simulate else 'remote'
    elf, flash, ram = avr.build_hid(toolchain, ROOT, name,
                                    ('main.c', 'remote.c', 'storage.c', 'control.c'),
                                    APPLICATION_LIMIT, 384,
                                    defines=(f'-DREMOTE_SIMULATE={int(simulate)}',))
    print(f'{name}: {flash} Flash bytes; {ram}/512 static SRAM bytes')
    print('HEX SHA-256:', hashlib.sha256(elf.with_suffix('.hex').read_bytes()).hexdigest())
    return elf


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path)
    args = parser.parse_args()
    compiler = avr.find_toolchain(args.toolchain)
    build(compiler)
    build(compiler, simulate=True)
