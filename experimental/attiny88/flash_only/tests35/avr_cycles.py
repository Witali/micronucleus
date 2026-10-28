"""ATtiny88 AVRe instruction cycles, independent of the legacy timing fallback.

References: ATtiny48/88 doc8008H, section 25; DS40002198A, section 4.
Flash erase/program CPU stalls are separate from the four-cycle SPM opcode.
Unknown operations fail instead of inheriting an assumed one-cycle duration.
"""

ONE = frozenset(('nop', 'wdr', 'ldi', 'mov', 'movw', 'in', 'out',
                 'cpi', 'cp', 'cpc', 'subi', 'sbci', 'sub', 'sbc',
                 'add', 'adc', 'andi', 'ori', 'and', 'or', 'eor',
                 'inc', 'dec', 'com', 'neg', 'swap', 'lsr', 'asr', 'ror',
                 'bst', 'bld', 'bset', 'bclr', 'sec', 'cli', 'sei'))
TWO = frozenset(('rjmp', 'ijmp', 'sbi', 'cbi', 'push', 'pop', 'lds', 'sts',
                 'ld', 'st', 'ldd', 'std', 'adiw', 'sbiw'))
THREE = frozenset(('rcall', 'icall', 'lpm'))
FOUR = frozenset(('ret', 'reti', 'spm'))
SKIPS = frozenset(('cpse', 'sbic', 'sbis', 'sbrc', 'sbrs'))


def cycles(ins, flags, after_pc, next_size=None):
    """Use the prior branch condition, including a target at the next word."""
    op = ins.op
    if op in ('brbs', 'brbc'):
        bit = int(ins.operands.split(',')[0])
        taken = bool(flags & (1 << bit)) == (op == 'brbs')
        expected_pc = ins.target if taken else ins.address+ins.size
        if after_pc != expected_pc:
            raise AssertionError(('branch outcome', op, after_pc, expected_pc))
        return 2 if taken else 1
    if op in SKIPS:
        skipped = after_pc-ins.address-ins.size
        if not skipped:
            return 1
        if skipped not in (2, 4) or skipped != next_size:
            raise AssertionError(('skip width', op, skipped, next_size))
        return 2 if skipped == 2 else 3
    for group, count in ((ONE, 1), (TWO, 2), (THREE, 3), (FOUR, 4)):
        if op in group:
            return count
    raise NotImplementedError(('ATtiny88 cycle count', op))
