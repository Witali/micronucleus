"""Exercise actual AVR words that mix data pushes and return-frame discards."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests27 import avr_exec27 as candidate


def machine(words):
    base = 0x1B80
    artifact = dict(boot=base, body=b''.join(word.to_bytes(2, 'little') for word in words),
                    symbols={'entry': base, 'done': base + len(words) * 2},
                    obj=Path('raw-stack-fixture.o'))
    # Use the real raw-word decoder; the fixture needs no ELF disassembly.
    with patch.object(candidate, 'decode', return_value={}):
        return candidate.AVRExec(artifact)


def check():
    # RCALL/PUSH/RCALL/PUSH/POP/RET/POP/RET must restore both frames and data.
    cpu = machine([0xD001, 0xC007, 0x932F, 0xD002, 0x915F, 0x9508,
                   0x933F, 0x914F, 0x9508])
    cpu.r[18], cpu.r[19], cpu.C, cpu.Z = 0xA5, 0xB6, 1, 1
    assert cpu.run('entry', stop=('done',)) == 'stop'
    assert cpu.r[20:22] == [0xB6, 0xA5] and not cpu.stack.raw
    assert cpu.C == cpu.Z == 1

    # Two POPs discard one RCALL frame, high word-PC byte before low byte.
    cpu = machine([0xD001, 0xC003, 0x912F, 0x913F, 0xC000])
    assert cpu.run('entry', stop=('done',)) == 'stop'
    word_pc = (cpu.art['boot'] + 2) // 2
    assert cpu.r[18:20] == [word_pc >> 8, word_pc & 255] and not cpu.stack.raw

    cpu = machine([0xD001, 0xC002, 0x912F, 0x9508])
    try:
        cpu.run('entry', stop=('done',))
    except AssertionError as error:
        assert str(error) == 'Incomplete return frame'
    else:
        raise AssertionError('RET accepted a half-discarded call frame')
    print('PASS raw AVR nested data/call stack, return-PC POP order and malformed frame rejection')


if __name__ == '__main__':
    check()
