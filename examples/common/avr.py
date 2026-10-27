"""Offline AVR tools and application artifacts; no hardware access."""
import os
from pathlib import Path
import shutil
import subprocess

USB_DRIVER = Path(__file__).resolve().parent / 'usbdrv'


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


def read_hex(path, application_limit):
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
    if not eof or not cells or min(cells) != 0 or max(cells) >= application_limit:
        raise ValueError('HEX must start at RESET and stay below the application postscript')
    return cells


def section_usage(toolchain, elf):
    sections = run_tool(toolchain, 'avr-size', '-A', elf)
    sizes = {parts[0]: int(parts[1]) for line in sections.splitlines()
             if (parts := line.split()) and parts[0] in ('.text', '.data', '.bss')}
    return sizes.get('.text', 0) + sizes.get('.data', 0), sizes.get('.data', 0) + sizes.get('.bss', 0)


def export_application(toolchain, elf, flash_limit, sram_limit):
    flash, ram = section_usage(toolchain, elf)
    if not 0 < flash <= flash_limit or ram > sram_limit:
        raise RuntimeError(f'Application budget exceeded: Flash={flash}, static SRAM={ram}')
    run_tool(toolchain, 'avr-objcopy', '-O', 'ihex', '-R', '.eeprom', elf, elf.with_suffix('.hex'))
    run_tool(toolchain, 'avr-objcopy', '-O', 'binary', '-R', '.eeprom', elf, elf.with_suffix('.bin'))
    read_hex(elf.with_suffix('.hex'), flash_limit)
    return flash, ram


def build_hid(toolchain, root, name, sources, flash_limit, sram_limit, defines=()):
    output = root / 'build'
    output.mkdir(exist_ok=True)
    elf = output / (name + '.elf')
    run_tool(toolchain, 'avr-gcc', '-mmcu=attiny88', '-DF_CPU=16000000UL',
             *defines, '-Os', '-std=c11', '-Wall', '-Wextra', '-Werror',
             '-ffunction-sections', '-fdata-sections', '-I', root, '-I', USB_DRIVER,
             *(root / source for source in sources), USB_DRIVER / 'usbdrv.c',
             USB_DRIVER / 'usbdrvasm.S', '-Wl,--gc-sections',
             f'-Wl,-Map={output / (name + ".map")}', '-o', elf)
    flash, ram = export_application(toolchain, elf, flash_limit, sram_limit)
    return elf, flash, ram
