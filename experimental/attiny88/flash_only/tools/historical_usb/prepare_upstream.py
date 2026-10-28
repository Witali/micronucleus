#!/usr/bin/env python3
"""Prepare the pinned public v2.6 no-LED artifact under ignored build output.

Uses existing make/AVR tools only. Never invokes a programmer, fuse, upgrade,
installation or package-manager target. An explicit download or local public
archive is required; all source/archive/body hashes are checked.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'build/historical_usb'
SOURCE_URL = 'https://github.com/micronucleus/micronucleus/archive/refs/tags/v2.6.zip'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


def extract_symbols(elf):
    """Read public code labels and normalize AVR-tagged SRAM symbol addresses."""
    symbols = {}
    for row in command(['avr-objdump', '-t', str(elf)]).splitlines():
        fields = row.split()
        section = next((i for i, field in enumerate(fields)
                        if field in ('.text', '.bss', '.data', '*ABS*')), None)
        if section is None or section + 2 >= len(fields):
            continue
        value = int(fields[0], 16)
        if fields[section] in ('.bss', '.data') and value >= 0x800000:
            value -= 0x800000
        symbols[fields[-1]] = value
    return symbols


def main():
    """Verify public source, build only the no-LED ELF and pin its raw body."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--archive', type=Path, help='Previously downloaded public v2.6 ZIP')
    source.add_argument('--download', action='store_true', help='Download the pinned official tag ZIP')
    parser.add_argument('--output-dir', type=Path, default=BASE / 'upstream26')
    args = parser.parse_args()
    expected = json.loads((HERE / 'upstream26_provenance.json').read_text())
    output = args.output_dir.resolve()
    if not output.is_relative_to(BASE.resolve()):
        raise ValueError('Preparation output must stay under build/historical_usb')
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Choose a new empty preparation directory; existing output is not overwritten')
    for executable in ('make', 'avr-gcc', 'avr-objdump', 'avr-objcopy'):
        if not shutil.which(executable):
            raise RuntimeError(f'Required existing tool is missing: {executable}')
    output.mkdir(parents=True, exist_ok=True)
    archive = args.archive
    if args.download:
        archive = output / 'upstream-v2.6.zip'
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
            archive.write_bytes(response.read(16 * 1024 * 1024))
    if digest(archive) != expected['zip_sha256']:
        raise ValueError('Official archive SHA256 differs from the audited public source')
    destination = output / 'source'
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or ':' in str(path) or '\\' in str(path) or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Unsafe archive path or symlink')
        zipped.extractall(destination)
    tree = destination / 'micronucleus-2.6'
    source_hashes = {}
    for row in expected['files']:
        path = tree / row['file']
        if digest(path) != row['tag_sha256']:
            raise ValueError('Pinned source mismatch: ' + row['file'])
        source_hashes[row['file']] = digest(path)
    config = tree / 'firmware/configuration/t88_default/bootloaderconfig.h'
    text, count = re.subn(r'(?m)^#define[ \t]+LED_MODE[ \t]+ACTIVE_HIGH[ \t]*$',
                          '#define LED_MODE    NONE', config.read_text())
    if count != 1:
        raise ValueError('Expected exactly one original LED definition')
    config.write_text(text, encoding='utf-8')
    # Only the inspected main.bin dependency graph is executed. main.bin is
    # an ELF despite its extension; no flash/fuse/upgrade target is called.
    command(['make', 'CONFIG=t88_default', 'main.bin'], tree / 'firmware')
    elf = tree / 'firmware/main.bin'
    body = output / 'upstream26-noled.body.bin'
    command(['avr-objcopy', '-O', 'binary', '-j', '.text', str(elf), str(body)])
    sections = {}
    for row in command(['avr-objdump', '-h', str(elf)]).splitlines():
        fields = row.split()
        if len(fields) > 2 and fields[1] in ('.text', '.data', '.bss'):
            sections[fields[1]] = int(fields[2], 16)
    if sections != {'.text': 1332, '.data': 0, '.bss': 44}:
        raise ValueError('Official artifact section geometry differs from the audited build')
    if len(body.read_bytes()) != expected['body_bytes'] or digest(body) != expected['body_sha256']:
        raise ValueError('Compiled body differs from the audited AVR-GCC 7.3.0 image; do not substitute it')
    metadata = dict(boot=expected['boot'], size=expected['body_bytes'], sha256=expected['body_sha256'],
                    obj=elf.relative_to(output).as_posix(), bin=body.name, symbols=extract_symbols(elf), sections=sections,
                    provenance=dict(release_tag=expected['release_tag'], release_commit=expected['release_commit'],
                        comparison_export_pin=expected['pinned'], archive_sha256=expected['zip_sha256'],
                        original_source_sha256=source_hashes,
                        no_led_config_sha256=digest(config),
                        avr_gcc=command(['avr-gcc', '--version']).splitlines()[0],
                        changes='LED_MODE ACTIVE_HIGH -> NONE only'))
    artifact = output / 'artifact.json'
    artifact.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print('Prepared pinned offline artifact:', artifact)


if __name__ == '__main__':
    main()
