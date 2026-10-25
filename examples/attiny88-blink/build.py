#!/usr/bin/env python3
"""Build a small application-only ATtiny88 LED test; never access hardware."""
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    elf = build / 'blink.elf'
    hexfile = build / 'blink.hex'
    subprocess.run(['avr-gcc', '-mmcu=attiny88', '-DF_CPU=16000000UL', '-Os',
                    '-std=c11', '-Wall', '-Wextra', '-Werror', '-ffunction-sections',
                    '-fdata-sections', '-Wl,--gc-sections', str(ROOT / 'main.c'),
                    '-o', str(elf)], check=True)
    sections = subprocess.check_output(['avr-size', '-A', str(elf)], text=True)
    sizes = {line.split()[0]: int(line.split()[1]) for line in sections.splitlines()
             if line.startswith(('.text ', '.data '))}
    flash_bytes = sum(sizes.values())
    if not 0 < flash_bytes <= 1024:
        raise RuntimeError(f'Unexpected application size: {flash_bytes}')
    subprocess.run(['avr-objcopy', '-O', 'ihex', '-R', '.eeprom', str(elf), str(hexfile)], check=True)
    cells = {}
    eof = False
    for line in hexfile.read_text(encoding='ascii').splitlines():
        record = bytes.fromhex(line[1:])
        if not line.startswith(':') or len(record) != record[0] + 5 or sum(record) % 256:
            raise RuntimeError('Invalid Intel HEX record')
        if record[3] == 0:
            address = int.from_bytes(record[1:3], 'big')
            cells.update({address + i: value for i, value in enumerate(record[4:-1])})
        elif record[3] == 1:
            eof = True
        elif record[3] not in (3, 5):
            raise RuntimeError('Unexpected Intel HEX address space')
    if not eof or not cells or min(cells) != 0 or max(cells) >= 1024:
        raise RuntimeError('HEX exceeds the application smoke-test bounds')
    print(subprocess.check_output(['avr-size', str(elf)], text=True).strip())
    print('Application Flash bytes:', flash_bytes)
    print('HEX SHA-256:', hashlib.sha256(hexfile.read_bytes()).hexdigest())
    print('Output:', hexfile)


if __name__ == '__main__':
    main()
