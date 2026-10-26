#!/usr/bin/env python3
"""Assemble and measure isolated CRC candidates; never build or flash USB code.

The 32-byte nibble table, separate 16-byte parity table and AVR-LibC formula
are checked by interpreting their actual linked AVR opcodes. Reported body
cycles exclude RET/RCALL and distinguish a preloaded table page from setup.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import random
import re
import shutil
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
sys.path.insert(0, str(PROJECT / 'tools'))
from avr_build import assemble
from crc_nibble import render_assembly, render_folded_assembly, TABLE_LOW, TABLE_HIGH, FOLDED_PARITY_TABLE

SPEC = importlib.util.spec_from_file_location('nibble_opcode_decoder', PROJECT / 'tests/avr_decoder.py')
DECODER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DECODER
SPEC.loader.exec_module(DECODER)

ORIGIN = 0x0800
TABLE_ORIGIN = 0x1000
FOLD_ORIGIN = 0x1100
CURRENT_PIPELINE_CLOCKS = 11
ALLOWED = {'ldi', 'mov', 'swap', 'eor', 'andi', 'ori', 'lsr', 'ror', 'lpm', 'ret'}


def bit_reference(crc, value):
    crc ^= value
    for _ in range(8):
        crc = (crc >> 1) ^ (0xa001 if crc & 1 else 0)
    return crc


def instructions(raw, first, last):
    DECODER.START, DECODER.raw = 0, raw
    result = []
    while first < last:
        instruction = DECODER.decode(first)
        assert not instruction.unknown and instruction.op in ALLOWED, instruction
        result.append(instruction)
        first += instruction.size
    assert first == last and result[-1].op == 'ret'
    return result


def clocks(program):
    return sum(3 if op.op == 'lpm' else 4 if op.op == 'ret' else 1 for op in program)


def execute(program, flash, crc, value, page):
    """Small straight-line executor, decoded once from the real linked image.

    Only LSR/ROR consume C in these formulas. Other used operations preserve
    it; no branch depends on the remaining SREG bits. Unknown ops fail closed.
    """
    registers = [(index * 19 + 7) & 255 for index in range(32)]
    registers[1] = 0
    registers[20], registers[24], registers[25], registers[31] = value, crc & 255, crc >> 8, page
    original = registers.copy()
    carry = crc & 1
    for instruction in program:
        op = instruction.op
        operands = [part.strip() for part in instruction.operands.split(',')]
        if op == 'ret':
            break
        destination = int(operands[0][1:])
        if op == 'ldi':
            registers[destination] = int(operands[1], 0)
        elif op == 'mov':
            registers[destination] = registers[int(operands[1][1:])]
        elif op == 'swap':
            old = registers[destination]
            registers[destination] = (old >> 4) | ((old & 15) << 4)
        elif op == 'eor':
            registers[destination] ^= registers[int(operands[1][1:])]
        elif op == 'andi':
            registers[destination] &= int(operands[1], 0)
        elif op == 'ori':
            registers[destination] |= int(operands[1], 0)
        elif op in ('lsr', 'ror'):
            old = registers[destination]
            registers[destination] = (old >> 1) | ((carry << 7) if op == 'ror' else 0)
            carry = old & 1
        elif op == 'lpm':
            assert operands[1] == 'Z'
            address = registers[30] | registers[31] << 8
            registers[destination] = flash[address]
        else:
            raise AssertionError(op)
    scratch = {18, 19, 24, 25, 30, 31}
    assert all(registers[index] == original[index] for index in range(32) if index not in scratch)
    return registers[24] | registers[25] << 8


def vectors():
    # Every CRC state with byte 00; every possible input at sixteen state
    # boundaries; additional reproducible state/input pairs. The companion
    # generator separately proves the nibble recurrence over all 16M pairs.
    for crc in range(65536):
        yield crc, 0
    boundaries = (0, 1, 7, 8, 15, 16, 0x7f, 0x80, 0xff, 0x100,
                  0x7fff, 0x8000, 0xa001, 0xb001, 0xfe54, 0xffff)
    for crc in boundaries:
        for value in range(256):
            yield crc, value
    randomizer = random.Random(0x32c16)
    for _ in range(4096):
        yield randomizer.randrange(65536), randomizer.randrange(256)


def measure(output):
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE / 'source/crc_nibble_update.inc', output / 'crc_nibble_update.inc')
    source = output / 'candidates.S'
    source.write_text('.section .text\n.org 0x0800\n.global bootloader_start\n'
                      'bootloader_start:\n#include "crc_nibble_update.inc"\n'
                      'crc_candidates_code_end:\n.org 0x1000\n' + render_assembly() +
                      '\n.org 0x1100\n' + render_folded_assembly(), newline='\n')
    obj, binary = output / 'candidates.o', output / 'candidates.raw.bin'
    assemble(source, obj, binary)
    raw = binary.read_bytes()
    text = subprocess.check_output(['llvm-objdump', '-t', str(obj)], text=True)
    symbols = {match.group(2): int(match.group(1), 16) for match in
               re.finditer(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$', text, re.M)}
    assert symbols['crc_nibble_table_low'] == TABLE_ORIGIN
    assert symbols['crc_nibble_table_high'] == TABLE_ORIGIN + 16
    assert symbols['crc_fold_table'] == FOLD_ORIGIN
    assert raw[TABLE_ORIGIN:TABLE_ORIGIN + 32] == TABLE_LOW + TABLE_HIGH
    assert raw[FOLD_ORIGIN:FOLD_ORIGIN + 16] == FOLDED_PARITY_TABLE
    rows = []
    definitions = [('crc_nibble_update', 32, TABLE_ORIGIN >> 8),
                   ('crc_fold_update', 16, FOLD_ORIGIN >> 8),
                   ('crc_avrlibc_update', 0, 0)]
    for name, table_bytes, page in definitions:
        program = instructions(raw, symbols[name], symbols[name + '_end'])
        body_start = symbols.get(name + '_preloaded', symbols[name])
        body = instructions(raw, body_start, symbols[name + '_end'])
        count = 0
        for crc, value in vectors():
            expected = bit_reference(crc, value)
            actual = execute(program, raw, crc, value, 0x79)
            assert actual == expected, (name, hex(crc), hex(value), hex(actual), hex(expected))
            if name != 'crc_avrlibc_update':
                assert execute(body, raw, crc, value, page) == expected
            count += 1
        # Validate complete incoming payload plus complemented wire CRC on
        # actual opcodes, independently from the table generator's tests.
        payloads = [bytes([value]) * size for size in range(9) for value in (0, 255, 0x55, 0xaa)]
        for payload in payloads:
            crc = 0xffff
            for value in payload:
                crc = execute(program, raw, crc, value, 0x79)
            trailer = ((~crc) & 0xffff).to_bytes(2, 'little')
            for value in trailer:
                crc = execute(program, raw, crc, value, 0x79)
            assert crc == 0xb001
        inline_clocks = clocks(body) - 4
        rows.append({
            'name': name, 'table_data_bytes': table_bytes,
            'code_bytes_including_setup_and_ret': symbols[name + '_end'] - symbols[name],
            'inline_code_bytes_preloaded_page': symbols[name + '_return'] - body_start,
            'inline_clocks_preloaded_page': inline_clocks,
            'inline_clocks_including_page_setup': clocks(program) - 4,
            'function_clocks_including_ret': clocks(program),
            'call_clocks_including_rcall_ret': clocks(program) + 3,
            'lpm_reads_per_byte': sum(item.op == 'lpm' for item in program),
            'opcode_state_byte_vectors': count, 'opcode_wire_residual_vectors': len(payloads),
            'extra_inline_clocks_vs_current_pipeline': inline_clocks - CURRENT_PIPELINE_CLOCKS,
        })
    result = {
        'result': 'PASS', 'purpose': 'isolated CRC arithmetic and cycle feasibility',
        'physical_device_programmed': False, 'usb_receiver_modified': False,
        'source_sha256': hashlib.sha256((output / 'crc_nibble_update.inc').read_bytes()).hexdigest(),
        'linked_code_sha256': hashlib.sha256(raw[ORIGIN:symbols['crc_candidates_code_end']]).hexdigest(),
        'requested_table_sha256': hashlib.sha256(TABLE_LOW + TABLE_HIGH).hexdigest(),
        'favorable_table_placement': 'page offsets 00/10; folded table offset 00 on another page',
        'alignment_padding_included_in_table_bytes': False,
        'current_usb_byte_period_clocks': [85, 86],
        'current_streaming_crc_inline_clocks': CURRENT_PIPELINE_CLOCKS,
        'ret_clocks': 4, 'rcall_clocks': 3, 'candidates': rows,
        'integration_limit': 'No sampling schedule or EOP/ACK path is changed or proved by this measurement.',
    }
    (output / 'measurement.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'symbols.json').write_text(json.dumps(symbols, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE / 'build/crc-nibble')
    args = parser.parse_args()
    measure(args.output_dir)
