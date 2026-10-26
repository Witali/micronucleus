#!/usr/bin/env python3
"""Build a separately selected, scratch-limited NVM benchmark application.

This tool never programs hardware. It reuses the frozen streaming V2 USB
application wrapper, then enables the existing NVM engine with extra access
checks. The ordinary streaming builder remains read-only and unchanged.

Protocol stays Block64 v3.3. GET_STATUS is eight bytes with feature bit 0x80
and app-size metadata 0x1FFC, which describes the full 8 KiB READ limit to the
existing host. Flash mutation permission is independently limited to the
eight aligned 64-byte pages in [0x1800,0x1A00). EEPROM WRITE stays within its
64 bytes; writing FF provides erase/write behavior. RUN and inactivity exit
are disabled. The manifest records these restrictions; it is not an unlock.
"""
from contextlib import redirect_stdout
from pathlib import Path
import argparse
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
STREAMING = BASE.parent / 'streaming_crc16'
ORIGIN = 0x0800
FLASH_START, FLASH_END = 0x1800, 0x1A00
FLASH_READ_END, EEPROM_END = 0x2000, 64
FEATURE_MASK = 0x80
FROZEN_RECEIVER = 'fcc0ad6f463dd0e133808065e8db3d1aa2e4a1762158666dadfc2231205dbd2c'

sys.path.insert(0, str(STREAMING / 'tools'))
SPEC = importlib.util.spec_from_file_location('benchmark_readonly_builder', STREAMING / 'tools/build.py')
READONLY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READONLY)


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError(f'Expected one source anchor: {old.splitlines()[0]}')
    return source.replace(old, new)


def guarded_source():
    main = (PROJECT / 'source/micronucleus_t88_block64.S').read_text()
    main = replace_once(main, '    brne    L1eac\n', 'prototype_disabled_autoexit:\n    nop\n')
    main = replace_once(main, 'block_run:\n', 'block_run:\n    rjmp    block_reject\n')
    metadata = '((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff)'
    main = replace_once(main, metadata, '0x1f, 0xfc')
    main = replace_once(main, 'BLOCK64_PROTO_MARKER, 0x03  /* six metadata bytes;',
                        'BLOCK64_PROTO_MARKER, 0x83  /* six metadata bytes;')
    bound = '''#if (BOOT_AT & 0xff) != 64
    ldi     r20, (BOOT_AT & 0xff)
#endif
    ldi     r21, (BOOT_AT >> 8)'''
    main = replace_once(main, bound, '    ldi     r20, 0\n    ldi     r21, 0x20')
    main = replace_once(main, 'block_valid_range:\n',
                        '    rcall   benchmark_validate_access\n'
                        '    brcc    block_invalid_range\nblock_valid_range:\n')
    page = '''block_load_page_z:
    ldd     r30, Y+49
    andi    r30, 0xc0
    ldd     r31, Y+50
    ret'''
    guarded_page = '''block_load_page_z:
    ldd     r30, Y+49
    andi    r30, 0xc0
    ldd     r31, Y+50
    rjmp    benchmark_validate_spm_address'''
    main = replace_once(main, page, guarded_page)
    eeprom = '    out     T88_IO_EEARL, r20         /* EEARL */'
    main = replace_once(main, eeprom,
                        '    cpi     r20, 64\n'
                        '    brlo    benchmark_eeprom_address_ok\n'
                        '    rjmp    benchmark_nvm_fault\n'
                        'benchmark_eeprom_address_ok:\n' + eeprom)
    main = '#define BOOT_AT 0x0800\n#define T88_ASSUME_RESET_STACK_INIT 0\n' + main
    main += '\n#include "benchmark_protection.inc"\nprototype_code_end:\n'
    main += '\n.org 0x1600\n' + READONLY.render_assembly()
    return main


def build(output):
    sampler = STREAMING / 'source/streaming_rx_v2.inc'
    if hashlib.sha256(sampler.read_bytes()).hexdigest() != FROZEN_RECEIVER:
        raise RuntimeError('The benchmark requires the validated frozen V2 receiver')
    # Reuse its generated PHY/classifier includes, without changing its tool
    # or the source used by the default read-only application build.
    with redirect_stdout(io.StringIO()):
        READONLY.build('streaming-v2', output)
    shutil.copyfile(BASE / 'source/benchmark_protection.inc', output / 'benchmark_protection.inc')
    source = output / 'application.S'
    source.write_text(guarded_source(), newline='\n')
    obj, rawfile = output / 'application.o', output / 'application.raw.bin'
    READONLY.assemble(source, obj, rawfile)
    report = subprocess.check_output(['llvm-objdump', '-t', str(obj)], text=True)
    symbols = {m.group(2): int(m.group(1), 16) for m in
               re.finditer(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$', report, re.M)}
    raw = rawfile.read_bytes()
    assert raw[:ORIGIN] == bytes(ORIGIN)
    assert symbols['prototype_code_end'] <= 0x1600
    assert symbols['stream_crc_table_low'] == 0x1600
    assert symbols['stream_crc_table_high'] == 0x1700
    assert len(raw) == FLASH_START
    body = raw[ORIGIN:]
    (output / 'application.bin').write_bytes(body)
    image = bytearray(b'\xff' * FLASH_READ_END)
    image[ORIGIN:len(raw)] = body
    image[:2] = (0xC03F).to_bytes(2, 'little')
    image[0x80:0x82] = (0xC000 | ((ORIGIN - 0x82) // 2)).to_bytes(2, 'little')
    (output / 'application-full.bin').write_bytes(image)
    lines = [READONLY.record(0, image[:2]), READONLY.record(0x80, image[0x80:0x82])]
    lines += [READONLY.record(a, image[a:min(a + 16, len(raw))]) for a in range(ORIGIN, len(raw), 16)]
    (output / 'application.hex').write_text('\n'.join(lines + [READONLY.record(0, b'', 1)]) + '\n')
    (output / 'symbols.txt').write_text('\n'.join(f'{name} 0x{at:04X}' for name, at in symbols.items()) + '\n')
    manifest = json.loads((output / 'manifest.json').read_text())
    manifest.update({
        'purpose': 'guarded-memory-benchmark', 'receiver': 'streaming-v2', 'symbols': symbols,
        'body_bytes': len(body), 'executable_end': symbols['prototype_code_end'],
        'sha256_body': hashlib.sha256(body).hexdigest(),
        'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.inc'))},
        'application_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'mutation_requests_enabled': True, 'spm_enabled': True, 'eeprom_programming_enabled': True,
        'flash_mutation_start': FLASH_START, 'flash_mutation_end_exclusive': FLASH_END,
        'flash_mutation_page_bytes': 64, 'flash_mutation_pages': 8,
        'eeprom_mutation_start': 0, 'eeprom_mutation_end_exclusive': EEPROM_END,
        'run_request_enabled': False, 'inactivity_application_jump_enabled': False,
        'benchmark_feature_mask': FEATURE_MASK, 'status_features': 0x83,
        'status_app_size_field': 0x1FFC, 'diagnostic_flash_read_limit': FLASH_READ_END,
        'internal_nvm_address_fault': 'stop-before-trigger-until-reset',
        'physical_device_programmed': False,
    })
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({key: value for key, value in manifest.items() if key != 'symbols'}, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE / 'build/guarded-v2')
    args = parser.parse_args()
    build(args.output_dir)
