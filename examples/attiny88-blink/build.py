#!/usr/bin/env python3
"""Build a small application-only ATtiny88 LED test; never access hardware."""
from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from common import avr


def main():
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    elf = build / 'blink.elf'
    hexfile = build / 'blink.hex'
    toolchain = avr.find_toolchain()
    avr.run_tool(toolchain, 'avr-gcc', '-mmcu=attiny88', '-DF_CPU=16000000UL', '-Os',
                 '-std=c11', '-Wall', '-Wextra', '-Werror', '-ffunction-sections',
                 '-fdata-sections', '-Wl,--gc-sections', str(ROOT / 'main.c'),
                 '-o', elf)
    flash_bytes, _ = avr.section_usage(toolchain, elf)
    if not 0 < flash_bytes <= 1024:
        raise RuntimeError(f'Unexpected application size: {flash_bytes}')
    avr.run_tool(toolchain, 'avr-objcopy', '-O', 'ihex', '-R', '.eeprom', elf, hexfile)
    avr.read_hex(hexfile, 1024)
    print(avr.run_tool(toolchain, 'avr-size', elf).strip())
    print('Application Flash bytes:', flash_bytes)
    print('HEX SHA-256:', hashlib.sha256(hexfile.read_bytes()).hexdigest())
    print('Output:', hexfile)


if __name__ == '__main__':
    main()
