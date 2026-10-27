"""Candidate executor extension without changing the archived Pass26 models.

SEC is executed at its actual emitted address. All other operations use the
preserved non-bitstream executor; no USB handler is mocked by this class.
"""
from unittest.mock import patch
from tests import avr_exec23 as _legacy

decode = _legacy.decode


class AVRExec(_legacy.AVRExec):
    def __init__(self, artifact):
        with patch.object(_legacy, 'decode', decode):
            super().__init__(artifact)
        self.sym = self.sym.copy()
        self._sec_names = []
        for offset in range(0, len(artifact['body']) - 1, 2):
            if artifact['body'][offset:offset + 2] == b'\x08\x94':
                name = '_candidate_sec_' + str(offset)
                self.sym[name] = artifact['boot'] + offset
                self._sec_names.append(name)

    def decode_missing(self, pc):
        # LLVM sometimes groups unrelated legal words into <unknown>. The
        # independent raw decoder preserves their actual word boundaries.
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
        sec_addresses = {self.sym[name] for name in self._sec_names}
        while True:
            remaining = limit - (len(self.steps) - count)
            assert remaining > 0, ('candidate instruction limit', entry)
            result = super().run(entry, stop=tuple(stop) + tuple(self._sec_names),
                                 limit=remaining)
            if result != 'stop' or self.pc not in sec_addresses:
                return result
            self.steps.append((self.pc, 'sec', ''))
            self.C = 1
            entry = self.pc + 2
