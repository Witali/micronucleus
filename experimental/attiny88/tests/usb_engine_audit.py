"""Whitelist the optimized engine against the corrected, deployed USB body.

ATtiny48/88 datasheet, register summary notes and instruction summary:
https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf (pages 279-281).
SBI PCIFR,PCIF2 affects only that W1C bit. LDI+OUT and SBI each take two
cycles; STS and STD each take two cycles. No sampling/output rewrite is allowed.
"""
from collections import deque
import re

import avr_decoder as decoder

SKIPS = {'sbic', 'sbis', 'sbrc', 'sbrs', 'cpse'}


def operand(instruction):
    return re.sub(r'\s+', '', instruction.operands).lower()


def decode_engine(body, base, symbols):
    decoder.START, decoder.raw = base, body
    start, end = symbols['USB_handler'], symbols['flash_buffer_append_word']
    instructions = []
    pc = start
    while pc < end:
        instruction = decoder.decode(pc)
        assert not instruction.unknown, ('Unknown USB opcode', hex(pc))
        instructions.append(instruction)
        pc += instruction.size
    assert pc == end, 'USB engine ends inside an instruction'
    return instructions


def successors(instruction, by_address):
    pc = instruction.address + instruction.size
    if instruction.op in {'ret', 'reti'}:
        return []
    if instruction.op == 'rjmp':
        return [instruction.target]
    if instruction.op in {'brbc', 'brbs'}:
        return [pc, instruction.target]
    if instruction.op in SKIPS:
        return [pc, pc + by_address[pc].size]
    return [pc]


def check_z_pointer(instructions, symbols):
    by_address = {item.address: item for item in instructions}
    pending = deque([(symbols['USB_handler'], None, None)])
    seen, stores = set(), set()
    while pending:
        pc, low, high = pending.popleft()
        if (pc, low, high) in seen:
            continue
        seen.add((pc, low, high))
        if pc == symbols['usb_rx_store_token']:
            stores.add((low, high))
            continue
        assert pc in by_address, ('USB control flow leaves the engine', hex(pc))
        instruction = by_address[pc]
        args = operand(instruction).split(',')
        if instruction.op == 'ldi':
            if args[0] == 'r30':
                low = int(args[1], 0)
            if args[0] == 'r31':
                high = int(args[1], 0)
        elif instruction.op not in {'cp', 'cpc', 'cpi', 'push', 'sbrc', 'sbrs'}:
            if args[0] == 'r30':
                low = None
            if args[0] == 'r31' or (args[0] == 'r30' and instruction.op in {'movw', 'adiw', 'sbiw'}):
                high = None
        if any(value in {'z+', '-z'} for value in args):
            low = high = None
        for following in successors(instruction, by_address):
            pending.append((following, low, high))
    assert stores == {(0, 1)}, ('Token store requires Z == 0x0100 on every path', stores)


def check_r17_liveness(instructions, symbols):
    by_address = {item.address: item for item in instructions}
    for name, offset in [('usb_rx_overflow', 0), ('usb_rx_end_packet', 8), ('usb_tx_finish_eop', 0)]:
        pending = deque([symbols[name] + offset + 2])  # First opcode after SBI.
        seen, writes = set(), set()
        while pending:
            pc = pending.popleft()
            if pc in seen:
                continue
            seen.add(pc)
            assert pc in by_address, ('USB control flow leaves the engine', hex(pc))
            instruction = by_address[pc]
            args = operand(instruction).split(',')
            writes_r17 = args[0] == 'r17' and instruction.op in {'ldi', 'ldd', 'lds', 'in', 'pop', 'mov'}
            if writes_r17:
                # MOV R17,R17 would read the removed value.
                assert 'r17' not in args[1:], ('R17 is read before overwrite', name, hex(pc))
                writes.add(pc)
                continue
            assert 'r17' not in re.findall(r'r\d+', operand(instruction)), (
                'R17 is read after its removed initialization', name, hex(pc))
            pending.extend(successors(instruction, by_address))
        assert writes, ('No overwrite found after removed R17 initialization', name)


def audit_usb_engine(reference, reference_base, reference_symbols, body, base, symbols):
    original = decode_engine(reference, reference_base, reference_symbols)
    optimized = decode_engine(body, base, symbols)
    assert sum(item.size for item in original) == 516, 'Unexpected deployed engine'
    assert sum(item.size for item in optimized) == 508, 'Unexpected optimized engine'
    expected, old_indices, removed, changes = [], {}, set(), []
    position = 0
    while position < len(original):
        instruction = original[position]
        old_indices[instruction.address] = len(expected)
        if (instruction.op == 'ldi' and operand(instruction) == 'r17,0x04'
                and original[position + 1].op == 'out'
                and operand(original[position + 1]) == '0x1b,r17'):
            removed.add(original[position + 1].address)
            changes.append(('PCIFR', instruction.address, position))
            expected.append(('sbi', '0x1b,2', None))
            position += 2
            continue
        if instruction.op == 'sts' and operand(instruction) == '0x0114,r16':
            changes.append(('SRAM', instruction.address, position))
            expected.append(('std', 'z+20,r16', None))
        else:
            expected.append((instruction.op, operand(instruction), instruction.target))
        position += 1
    assert [(kind, address) for kind, address, _ in changes] == [
        ('PCIFR', reference_symbols['usb_rx_overflow']),
        ('PCIFR', reference_symbols['usb_rx_end_packet'] + 8),
        ('SRAM', reference_symbols['usb_rx_store_token']),
        ('PCIFR', reference_symbols['usb_tx_finish_eop']),
    ], 'Unexpected USB substitutions'
    for instruction in original:
        assert instruction.target not in removed, 'Branch enters a removed OUT'
    for _, _, index in changes:
        assert original[index - 1].op not in SKIPS, 'Rewrite changes skip timing/semantics'
    assert len(expected) == len(optimized), 'USB instruction count changed'
    new_indices = {item.address: index for index, item in enumerate(optimized)}
    for (op, args, target), actual in zip(expected, optimized):
        assert (actual.op, operand(actual)) == (op, args), ('Unexpected USB opcode', hex(actual.address))
        if target is None:
            assert actual.target is None
        else:
            assert target in old_indices and actual.target in new_indices, 'USB branch leaves engine'
            assert old_indices[target] == new_indices[actual.target], 'USB branch changed logical target'
    check_z_pointer(optimized, symbols)
    check_r17_liveness(optimized, symbols)
