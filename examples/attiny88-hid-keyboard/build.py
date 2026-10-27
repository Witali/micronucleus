#!/usr/bin/env python3
"""Build the application HEX offline; never open or program a USB device."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
# Fits the previous 2.8 loader as well as every recognized compact 3.0 profile.
APPLICATION_LIMIT = 0x1AFC


def find_toolchain(directory=None):
    if directory:
        return Path(directory)
    compiler = shutil.which('avr-gcc')
    if compiler:
        return Path(compiler).parent
    arduino = Path(os.environ.get('LOCALAPPDATA', '')) / 'Arduino15/packages/arduino/tools/avr-gcc'
    candidates = sorted(arduino.glob('*/bin/avr-gcc.exe'))
    if candidates:
        return candidates[-1].parent
    raise SystemExit('AVR-GCC not found. Add its bin directory to PATH or use --toolchain DIR.')


def run_tool(toolchain, name, *arguments):
    executable = toolchain / (name + ('.exe' if os.name == 'nt' else ''))
    return subprocess.check_output([str(executable), *map(str, arguments)], text=True)


def read_hex(path):
    cells = {}
    eof = False
    for line in path.read_text(encoding='ascii').splitlines():
        if eof or not line.startswith(':'):
            raise ValueError('Invalid Intel HEX record order')
        record = bytes.fromhex(line[1:])
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) % 256:
            raise ValueError('Invalid Intel HEX length/checksum')
        size, address, kind = record[0], int.from_bytes(record[1:3], 'big'), record[3]
        if kind == 0:
            for offset, value in enumerate(record[4:-1]):
                at = address + offset
                if at in cells:
                    raise ValueError('Overlapping Intel HEX data')
                cells[at] = value
        elif kind == 1 and size == 0 and address == 0:
            eof = True
        else:
            raise ValueError('Unexpected Intel HEX record type/address space')
    if not eof or not cells or min(cells) != 0 or max(cells) >= APPLICATION_LIMIT:
        raise ValueError('HEX must start at RESET and stay below the application postscript')
    return cells


def build(toolchain):
    output = ROOT / 'build'
    output.mkdir(exist_ok=True)
    elf = output / 'keyboard.elf'
    hexfile = output / 'keyboard.hex'
    run_tool(toolchain, 'avr-gcc', '-mmcu=attiny88', '-DF_CPU=16000000UL',
             '-Os', '-std=c11', '-Wall', '-Wextra', '-Werror',
             '-ffunction-sections', '-fdata-sections', '-I', ROOT, '-I', ROOT / 'usbdrv',
             ROOT / 'main.c', ROOT / 'keyboard.c', ROOT / 'usbdrv/usbdrv.c',
             ROOT / 'usbdrv/usbdrvasm.S', '-Wl,--gc-sections',
             f'-Wl,-Map={output / "keyboard.map"}', '-o', elf)
    sections = run_tool(toolchain, 'avr-size', '-A', elf)
    sizes = {parts[0]: int(parts[1]) for line in sections.splitlines()
             if (parts := line.split()) and parts[0] in ('.text', '.data', '.bss')}
    flash = sizes.get('.text', 0) + sizes.get('.data', 0)
    ram = sizes.get('.data', 0) + sizes.get('.bss', 0)
    if not 0 < flash <= APPLICATION_LIMIT or ram > 384:
        raise RuntimeError(f'Application budget exceeded: Flash={flash}, static SRAM={ram}')
    run_tool(toolchain, 'avr-objcopy', '-O', 'ihex', '-R', '.eeprom', elf, hexfile)
    run_tool(toolchain, 'avr-objcopy', '-O', 'binary', '-R', '.eeprom', elf, output / 'keyboard.bin')
    read_hex(hexfile)
    print(f'Application: {flash} Flash bytes; {ram}/512 static SRAM bytes')
    print('HEX SHA-256:', hashlib.sha256(hexfile.read_bytes()).hexdigest())
    print('Output:', hexfile)
    return elf


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, help='Directory containing avr-gcc and AVR binutils')
    args = parser.parse_args()
    build(find_toolchain(args.toolchain))
