"""Legacy opcode executor implements SWAP without changing modeled flags.

AVR Instruction Set Manual DS40002198A: SWAP exchanges the two nibbles;
SREG is unaffected. The timed backend's one-clock SWAP fixture is separate.
"""
from tests35 import ep0_model as h
from tests.avr_exec import AVRExec


def test():
    original = h.build()
    art = dict(original, symbols=original['symbols'].copy())
    # Exercise the emitted pending-command SWAP R25, not an invented opcode.
    pc = next(art['boot'] + offset for offset in range(0, len(art['body']), 2)
              if int.from_bytes(art['body'][offset:offset+2], 'little')
              == (0x9402 | (25 << 4)))
    art['symbols'].update(swap_probe=pc, swap_probe_end=pc+2)
    cpu = AVRExec(art)
    cases = 0
    for value in range(256):
        for carry in (0, 1):
            for zero in (0, 1):
                cpu.r = [(index * 37 + 11) % 256 for index in range(32)]
                cpu.r[25] = value
                expected = cpu.r.copy()
                expected[25] = (value % 16) * 16 + value // 16
                cpu.C, cpu.Z = carry, zero
                assert cpu.run('swap_probe', stop=('swap_probe_end',), limit=2) == 'stop'
                assert cpu.r == expected and (cpu.C, cpu.Z) == (carry, zero)
                assert not cpu.ram and not cpu.io and not cpu.spms
                cases += 1
    print('PASS legacy SWAP operands, modeled flags and unrelated state:', cases)


if __name__ == '__main__':
    test()
