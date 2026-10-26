"""NEG opcode against independent Microchip SREG formulas.

AVR Instruction Set Manual DS40002198B, section 6.80: NEG changes
H/S/V/N/Z/C, preserves I/T, and takes one clock. No hardware is accessed.
"""
import pytest

from avr_sim import BOOT, CPU


@pytest.mark.parametrize('register', [0, 15, 19, 31])
def test_neg_all_values_and_all_initial_sreg_bits(register):
    cpu = CPU()
    # Execute the encoded instruction, not the arithmetic helper directly.
    opcode = 0x9401 | (register << 4)
    cpu.flash[BOOT:BOOT + 2] = opcode.to_bytes(2, 'little')
    cpu.labels['neg_end'] = BOOT + 2
    untouched = [(index * 19 + 7) & 255 for index in range(32)]
    for value in range(256):
        result = (-value) & 255
        negative = result >> 7
        overflow = int(result == 0x80)
        expected_flags = (
            (int(bool((result | value) & 8)) << 5)
            | ((negative ^ overflow) << 4)
            | (overflow << 3)
            | (negative << 2)
            | (int(result == 0) << 1)
            | int(result != 0)
        )
        expected_registers = list(untouched)
        expected_registers[register] = result
        for initial_sreg in range(256):
            cpu.r[:] = untouched
            cpu.r[register] = value
            cpu.sreg = initial_sreg
            cpu.cycles = 0
            cpu.ops = 0
            cpu.run_from(BOOT, stop_at=['neg_end'], count=2)
            assert cpu.r == expected_registers
            assert cpu.sreg == (initial_sreg & 0xC0) | expected_flags
            assert cpu.cycles == 1 and cpu.ops == 1
    assert not cpu.stack and not cpu.spm_oplog and not cpu.eeprom_oplog
