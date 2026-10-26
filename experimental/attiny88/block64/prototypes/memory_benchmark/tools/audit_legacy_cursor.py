#!/usr/bin/env python3
"""Rebuild and audit the deployed legacy cursor using synthetic memory only.

The historical sources come from a pinned local Git commit. This tool neither
reads a board/private dump nor opens USB. Its NVM model implements selected
Microchip sequencing rules; it is not an electrical or power-loss test.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
REPOSITORY = PROJECT.parents[2]
COMMIT = '5a88ad5ec50e3f7950ab3e37fb2d07df57725f43'
EXPECTED_SHA256 = 'be2035139b301739837b5a214773e0a0421404450b078d40e2bf0c02aafa77c4'
BOOT, BODY_BYTES = 0x1B00, 1274
SCRATCH_START, SCRATCH_END, PAGE_BYTES = 0x1800, 0x1A00, 64
HISTORICAL_FILES = (
    'strict_usb_optimized/micronucleus_t88_optimized.S',
    'strict_usb_verified/led_config.h',
    'strict_usb_verified/led_macros.inc',
)


def git_command():
    """Resolve a managed Windows worktree's Git directory under WSL too."""
    marker = REPOSITORY / '.git'
    if marker.is_file():
        value = marker.read_text().strip()
        if not value.startswith('gitdir: '):
            raise RuntimeError('Unexpected managed worktree Git marker')
        value = value[len('gitdir: '):]
        if os.name != 'nt' and re.match(r'^[A-Za-z]:[/\\]', value):
            value = '/mnt/' + value[0].lower() + '/' + value[3:].replace('\\', '/')
        directory = Path(value)
        if not directory.is_absolute():
            directory = REPOSITORY / directory
        return ['git', '--git-dir=' + str(directory)]
    return ['git', '-C', str(REPOSITORY)]


def build_historical(output):
    """Build public historical blobs, then pin the *linked bytes*, not labels."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for relative in HISTORICAL_FILES:
        reference = COMMIT + ':experimental/attiny88/variants/' + relative
        data = subprocess.check_output(git_command() + ['show', reference])
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    source = output / HISTORICAL_FILES[0]
    include = PROJECT.parent / 'vendor/microchip/ATtiny_DFP-3.4.278/include'
    relocatable, linked = output / 'legacy.reloc.o', output / 'legacy.elf'
    rawfile = output / 'legacy.raw.bin'
    subprocess.run([
        'clang', '-target', 'avr', '-mmcu=attiny88', '-DBOOT_AT=0x1b00',
        '-DLED_MODE=NONE', '-I', str(include), '-c', '-x',
        'assembler-with-cpp', str(source), '-o', str(relocatable),
    ], check=True)
    subprocess.run([
        'avr-ld', '--entry=bootloader_start', '-Ttext=0', str(relocatable),
        '-o', str(linked),
    ], check=True)
    subprocess.run([
        'llvm-objcopy', '-O', 'binary', '-j', '.text', str(linked), str(rawfile),
    ], check=True)
    raw = rawfile.read_bytes()
    body = raw[BOOT:]
    assert raw[:BOOT] == bytes(BOOT)
    assert len(body) == BODY_BYTES
    assert hashlib.sha256(body).hexdigest() == EXPECTED_SHA256
    table = subprocess.check_output(['llvm-objdump', '-t', str(linked)], text=True)
    symbols = {
        match.group(2): int(match.group(1), 16)
        for match in re.finditer(
            r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$', table, re.M)
    }
    (output / 'legacy.bin').write_bytes(body)
    manifest = {
        'historical_commit': COMMIT, 'image_address': BOOT,
        'body_file': 'legacy.bin', 'code_bytes': len(body),
        'body_sha256': EXPECTED_SHA256, 'symbols': symbols,
        'hardware_accessed': False, 'private_memory_read': False,
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest, body


@contextmanager
def legacy_model(manifest, body):
    """Temporarily bind the existing interpreter to this exact legacy image."""
    assert manifest['historical_commit'] == COMMIT
    assert hashlib.sha256(body).hexdigest() == EXPECTED_SHA256
    sys.path.insert(0, str(PROJECT / 'tests'))
    try:
        model = importlib.import_module('avr_sim')
    finally:
        sys.path.pop(0)
    old_boot, old_symbols = model.BOOT, model.syms
    model.BOOT = BOOT
    model.syms = lambda: manifest['symbols'].copy()

    def create(*, erased_scratch=False):
        image = bytearray([0xA5] * 8192)
        image[BOOT:BOOT + len(body)] = body
        if erased_scratch:
            image[SCRATCH_START:SCRATCH_END] = b'\xff' * (SCRATCH_END - SCRATCH_START)
        return model.CPU(image=image, strict_nvm=True,
                         selfprgen_fuse_programmed=True)

    try:
        yield create
    finally:
        model.BOOT, model.syms = old_boot, old_symbols


def cursor(cpu):
    return cpu.r[4] | cpu.r[5] << 8


def command(cpu, request, value=0, index=0):
    """One accepted legacy SETUP's dispatcher, excluding USB wire behavior.

    A pending command is deliberately not guessed/retried. The caller must
    execute a queued commit before starting another command.
    """
    assert cpu.r[3] == 0, 'The proof requires no pending old command'
    cpu.set_setup(request, value, 0, index, 0x40)
    cpu.run_from('bootloader_check_set_flash_address',
                 stop_at=['usb_reply_empty', 'usb_reply_limit_length'],
                 count=150, execute_ret=True)
    return cursor(cpu)


def select_scratch(cpu, address):
    """Discard one harmless priming pair with request1/3/1, before data."""
    assert SCRATCH_START <= address < SCRATCH_END and address % PAGE_BYTES == 0
    command(cpu, 1, PAGE_BYTES, address)
    command(cpu, 3, 0x1234, 0x5678)
    command(cpu, 1, PAGE_BYTES, address)
    assert cursor(cpu) == address and cpu.r[3] == 0
    assert cpu.spm_buffer == b'\xff' * PAGE_BYTES
    assert not cpu._spm_loaded_words


def queue_page(cpu, address, data):
    assert len(data) == PAGE_BYTES and cursor(cpu) == address
    for offset in range(0, PAGE_BYTES, 4):
        command(cpu, 3, int.from_bytes(data[offset:offset + 2], 'little'),
                int.from_bytes(data[offset + 2:offset + 4], 'little'))
        assert cursor(cpu) == address + offset + 4
        assert cpu.r[3] == (0x40 if offset == PAGE_BYTES - 4 else 0)


def execute_pending(cpu):
    assert cpu.r[3] == 0x40
    cpu.run_from('bootloader_dispatch_command',
                 stop_at=['usb_control_process_received_packet'],
                 count=100, execute_ret=True)


def prove_cursor_selection(create):
    """Cover every supported idle cursor, including a previously used buffer."""
    checked = 0
    for initial in range(0, BOOT + 1, 4):
        cpu = create()
        cpu.r[4], cpu.r[5] = initial & 255, initial >> 8
        if initial:
            cpu.spm_buffer[:] = b'\x5a' * PAGE_BYTES
            cpu._spm_loaded_words = set(range(0, PAGE_BYTES, 2))
        before = bytes(cpu.flash)
        select_scratch(cpu, SCRATCH_START)
        assert bytes(cpu.flash) == before
        assert not any(event[0] in ('erase', 'write') for event in cpu.spm_oplog)
        checked += 1
    assert checked == 1729
    return checked


def prove_erased_page_writes(create):
    """Require erased targets, and prove only eight requested pages change."""
    cpu = create(erased_scratch=True)
    before = bytes(cpu.flash)
    select_scratch(cpu, SCRATCH_START)
    for address in range(SCRATCH_START, SCRATCH_END, PAGE_BYTES):
        command(cpu, 1, PAGE_BYTES, address)
        assert cursor(cpu) == address
        assert cpu.flash[address:address + PAGE_BYTES] == b'\xff' * PAGE_BYTES
        pattern = bytes((address // PAGE_BYTES + i * 71) & 255
                        for i in range(PAGE_BYTES))
        queue_page(cpu, address, pattern)
        execute_pending(cpu)
        assert cpu.flash[address:address + PAGE_BYTES] == pattern
        assert cpu.r[3] == 0 and cpu.r[1] == 0
    assert bytes(cpu.flash[:SCRATCH_START]) == before[:SCRATCH_START]
    assert bytes(cpu.flash[SCRATCH_END:]) == before[SCRATCH_END:]
    writes = [event[1] for event in cpu.spm_oplog if event[0] == 'write']
    assert writes == list(range(SCRATCH_START, SCRATCH_END, PAGE_BYTES))
    assert not any(event[0] == 'erase' for event in cpu.spm_oplog)
    return len(writes)


def audit(manifest, body):
    with legacy_model(manifest, body) as create:
        states = prove_cursor_selection(create)
        pages = prove_erased_page_writes(create)
    return {
        'historical_commit': COMMIT, 'body_sha256': EXPECTED_SHA256,
        'code_bytes': BODY_BYTES, 'idle_cursor_states_checked': states,
        'erased_scratch_pages_written': pages, 'flash_erase_events': 0,
        'non_scratch_flash_changed': False, 'hardware_accessed': False,
        'private_memory_read': False,
        'preconditions': [
            'No old pending command; zero cursor has reset/erase-cleared buffer.',
            'Every target page was read back as entirely FF before programming.',
            'Do not retry ambiguous transfers or program a non-erased page.',
        ],
        'scope': 'Actual command opcodes with synthetic memory, not USB wire delivery.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE / 'build/legacy-cursor')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = audit(*build_historical(args.output_dir))
    rendered = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered)
    print(rendered, end='')


if __name__ == '__main__':
    main()
