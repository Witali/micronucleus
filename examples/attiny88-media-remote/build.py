#!/usr/bin/env python3
"""Build independent GPIO-only and optional simulated-button media firmware."""
import argparse
import importlib.util
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
KEYBOARD = ROOT.parent / 'attiny88-hid-keyboard'
spec = importlib.util.spec_from_file_location('tiny88_build_tools', KEYBOARD / 'build.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def build(toolchain, simulate=False):
    output = ROOT / 'build'
    output.mkdir(exist_ok=True)
    name = 'remote-test' if simulate else 'remote'
    elf = output / (name + '.elf')
    hexfile = output / (name + '.hex')
    driver = KEYBOARD / 'usbdrv'
    base.run_tool(toolchain, 'avr-gcc', '-mmcu=attiny88', '-DF_CPU=16000000UL',
                  f'-DREMOTE_SIMULATE={int(simulate)}', '-Os', '-std=c11',
                  '-Wall', '-Wextra', '-Werror', '-ffunction-sections', '-fdata-sections',
                  '-I', ROOT, '-I', driver, ROOT / 'main.c', ROOT / 'remote.c', ROOT / 'storage.c',
                  driver / 'usbdrv.c', driver / 'usbdrvasm.S', '-Wl,--gc-sections',
                  f'-Wl,-Map={output / (name + ".map")}', '-o', elf)
    sizes = {}
    for line in base.run_tool(toolchain, 'avr-size', '-A', elf).splitlines():
        fields = line.split()
        if fields and fields[0] in ('.text', '.data', '.bss'):
            sizes[fields[0]] = int(fields[1])
    flash = sizes.get('.text', 0) + sizes.get('.data', 0)
    ram = sizes.get('.data', 0) + sizes.get('.bss', 0)
    assert 0 < flash <= base.APPLICATION_LIMIT and ram <= 384, (flash, ram)
    base.run_tool(toolchain, 'avr-objcopy', '-O', 'ihex', '-R', '.eeprom', elf, hexfile)
    base.run_tool(toolchain, 'avr-objcopy', '-O', 'binary', '-R', '.eeprom', elf, output / (name + '.bin'))
    base.read_hex(hexfile)
    print(f'{name}: {flash} Flash bytes; {ram}/512 static SRAM bytes')
    print('HEX SHA-256:', hashlib.sha256(hexfile.read_bytes()).hexdigest())
    return elf


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path)
    args = parser.parse_args()
    compiler = base.find_toolchain(args.toolchain)
    build(compiler)
    build(compiler, simulate=True)
