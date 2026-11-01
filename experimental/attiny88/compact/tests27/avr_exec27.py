"""Execute candidate SEC/PUSH/POP without changing the archived Pass26 model.

Calls and data share AVR stack bytes, so SETUP may discard a real return frame.
Other instructions use the preserved executor and independent raw decoder.
"""
from unittest.mock import patch
from tests import avr_exec23 as _legacy

decode = _legacy.decode


class ReturnStack:
    """Adapt legacy byte-PC calls/returns onto AVR word-PC stack bytes."""
    def __init__(self):
        self.raw = []

    def append(self, byte_pc):
        assert byte_pc % 2 == 0
        word_pc = byte_pc // 2
        self.raw.extend((word_pc & 255, word_pc >> 8))

    def pop(self):
        assert len(self.raw) >= 2, 'Incomplete return frame'
        high, low = self.raw.pop(), self.raw.pop()
        return (low | high << 8) * 2

    def __bool__(self):
        return bool(self.raw)


class AVRExec(_legacy.AVRExec):
    def __init__(self, artifact):
        with patch.object(_legacy, 'decode', decode):
            super().__init__(artifact)
        self.stack = ReturnStack()
        self.sym = self.sym.copy()
        self._special = {}
        for offset in range(0, len(artifact['body']) - 1, 2):
            word = int.from_bytes(artifact['body'][offset:offset + 2], 'little')
            operation = ('sec' if word == 0x9408 else
                         'push' if word & 0xFE0F == 0x920F else
                         'pop' if word & 0xFE0F == 0x900F else None)
            if operation is not None:
                pc = artifact['boot'] + offset
                self.sym['_candidate_special_' + str(offset)] = pc
                self._special[pc] = operation, (word >> 4) & 31
        self._special_names = tuple(name for name in self.sym
                                    if name.startswith('_candidate_special_'))

    def decode_missing(self, pc):
        from tests27.waveform_model import dec
        dec.START, dec.raw = self.art['boot'], self.art['body']
        decoder = getattr(dec.decode, '__wrapped__', dec.decode)
        instruction = decoder(pc)
        operands = instruction.operands
        if instruction.target is not None:
            relative = instruction.target - (pc + instruction.size)
            branch = ('.+' if relative >= 0 else '.-') + str(abs(relative))
            operands = (operands + ' ' if operands else '') + branch
        return instruction.op, operands, instruction.size

    def run(self, entry, stop=(), limit=200):
        count = len(self.steps)
        user_stops = {self.sym[name] for name in stop if name in self.sym}
        while True:
            remaining = limit - (len(self.steps) - count)
            assert remaining > 0, ('candidate instruction limit', entry)
            result = super().run(entry, stop=tuple(stop) + self._special_names,
                                 limit=remaining)
            if result != 'stop' or self.pc in user_stops or self.pc not in self._special:
                return result
            operation, register = self._special[self.pc]
            if operation == 'sec':
                self.C = 1
            elif operation == 'push':
                self.stack.raw.append(self.r[register])
            else:
                assert self.stack.raw, 'POP on empty stack'
                self.r[register] = self.stack.raw.pop()
            self.steps.append((self.pc, operation,
                               '' if operation == 'sec' else f'r{register}'))
            entry = self.pc + 2
