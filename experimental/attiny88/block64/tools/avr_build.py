"""Resolve AVR relocations before extracting a firmware or reference image."""
from pathlib import Path
import subprocess


def assemble(source: Path, linked: Path, binary: Path) -> None:
    """Keep the historical .o output name, but store a fully linked ELF there."""
    relocatable = linked.with_name(linked.stem + '.reloc.o')
    subprocess.run([
        'clang', '-target', 'avr', '-mmcu=attiny88', '-c',
        '-x', 'assembler-with-cpp', str(source), '-o', str(relocatable),
    ], check=True)
    subprocess.run([
        'avr-ld', '-m', 'avr25', '-Ttext=0', '-e', 'bootloader_start',
        '-o', str(linked), str(relocatable),
    ], check=True)
    report = subprocess.check_output(['llvm-objdump', '-r', str(linked)], text=True)
    if 'R_AVR_' in report:
        raise RuntimeError('Unresolved AVR relocations remain after linking')
    subprocess.run([
        'llvm-objcopy', '-O', 'binary', '-j', '.text', str(linked), str(binary),
    ], check=True)
