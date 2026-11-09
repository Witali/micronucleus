"""Build the isolated, physically bounded AVR byte-publication unit fixture."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXPECTED = '1db596fefa080b8fe016284bd0792cd132d231ba7d55c33fbf1de63f0c4504aa'


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def build(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    run(sys.executable, str(HERE / 'generate.py'), '--output-dir', str(output))
    run('clang', '-target', 'avr', '-mmcu=attiny88', '-DBOOT_AT=0',
        '-x', 'assembler-with-cpp', '-c', str(output / 'publication.S'),
        '-o', str(output / 'publication.o'))
    run('avr-ld', '-m', 'avr25', '--defsym=__TEXT_REGION_LENGTH__=0x2000',
        '-Ttext=0', '-e', 'bootloader_start', '-o', str(output / 'publication.elf'),
        str(output / 'publication.o'))
    assert 'R_AVR_' not in run('llvm-objdump', '-r', str(output / 'publication.elf'))
    run('llvm-objcopy', '-O', 'binary', '-j', '.text',
        str(output / 'publication.elf'), str(output / 'publication.bin'))
    body = (output / 'publication.bin').read_bytes()
    assert len(body) == 4328 and len(body) <= 8192
    digest = hashlib.sha256(body).hexdigest()
    assert digest == EXPECTED, ('Immutable fixture changed', digest, EXPECTED)
    symbols = {}
    for row in run('llvm-nm', '-n', str(output / 'publication.elf')).splitlines():
        fields = row.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
    hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
              for name in ('publication.S', 'manifest.json')}
    art = dict(boot=0, size=len(body), sha256=digest, obj=str(output / 'publication.elf'),
               bin=str(output / 'publication.bin'), symbols=symbols, source_hashes=hashes)
    (output / 'artifact.json').write_text(json.dumps(art, indent=2) + '\n')
    return art


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE / 'build')
    art = build(parser.parse_args().output_dir)
    print(json.dumps({k: v for k, v in art.items() if k != 'symbols'}, indent=2))
