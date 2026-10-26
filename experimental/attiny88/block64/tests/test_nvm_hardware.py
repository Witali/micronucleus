"""Optional Microchip-rule NVM checks using AVR opcodes, without a board.

This is a deterministic model of selected rules from the ATtiny48/88
datasheet chapters5 and19. It is not a complete peripheral, voltage,
power-loss, interrupt-injection or electrical USB simulation.
"""
from pathlib import Path

import pytest

from avr_sim import (
    CPU, MEM_ADDR_LO, MEM_ADDR_HI, MEM_BUFFER, MEM_INDEX, MEM_PROGRESS,
    MEM_STATE, MEM_STATUS, ST_DONE, ST_WRITE_EEPROM,
    MODEL_EEPROM_PROGRAM_CYCLES, MODEL_FLASH_PROGRAM_CYCLES,
)


ROOT = Path(__file__).resolve().parents[1]


def cpu(*, fuse=True, strict=True):
    image = (ROOT / 'firmware/isp-full.bin').read_bytes()
    return CPU(image=image, strict_nvm=strict,
               selfprgen_fuse_programmed=fuse if strict else None)


def page_address(c, address=0x100):
    c.mem[MEM_ADDR_LO] = address&255
    c.mem[MEM_ADDR_HI] = address>>8


def execute(c, words):
    """Execute a short peripheral probe in otherwise unused modeled Flash."""
    start = 0x1FC0
    code = b''.join(word.to_bytes(2, 'little') for word in words)
    c.flash[start:start+len(code)] = code
    c.labels['nvm_probe_end'] = start+len(code)
    c.run_from(start, stop_at=['nvm_probe_end'], count=100, execute_ret=True)


def out(address, register=18):
    return 0xB800 | ((address&0x30)<<5) | (register<<4) | (address&15)


def ldi(register, value):
    return 0xE000 | ((value&0xF0)<<4) | ((register-16)<<4) | (value&15)


def spm(c, command, *, delay=0):
    execute(c, [ldi(18, command), out(0x37), *([0]*delay), 0x95E8])


def start_eeprom(c, address=7, value=0x5A, *, delay=0):
    c.write_io(0x21, address)
    c.write_io(0x20, value)
    # OUT EEMPE followed by SBI EEPE, as used by the real worker.
    execute(c, [ldi(21, 4), out(0x1F, 21), *([0]*delay), 0x9A00|(0x1F<<3)|1])


def eeprom_service(c):
    c.r[28], c.r[29] = 0, 1
    c.r[18] = c.mem[MEM_STATE]
    c.run_from('block_memory_service', count=100, execute_ret=True)


def test_strict_mode_requires_explicit_fuse_assumption():
    with pytest.raises(ValueError, match='SELFPRGEN'):
        CPU(strict_nvm=True)


def test_actual_flash_erase_and_page_write_obey_hardware_sequence():
    c = cpu()
    page_address(c)
    c.flash[0x100:0x140] = b'\x00'*64
    before = c.cycles
    c.run_from('block_flash_erase_only', count=100, execute_ret=True)
    assert c.flash[0x100:0x140] == b'\xff'*64
    assert c.cycles-before >= MODEL_FLASH_PROGRAM_CYCLES
    assert c.spm_oplog == [('erase', 0x100)]
    c.mem[MEM_BUFFER:MEM_BUFFER+64] = bytes(range(64))
    before = c.cycles
    c.run_from('block_commit_flash', count=1000, execute_ret=True)
    assert c.flash[0x100:0x140] == bytes(range(64))
    assert c.cycles-before >= MODEL_FLASH_PROGRAM_CYCLES
    assert [item[1] for item in c.spm_oplog if item[0] == 'load'] == list(range(0x100, 0x140, 2))
    assert c.spm_buffer == b'\xff'*64
    assert not c._spm_loaded_words
    assert c.mem[MEM_STATE] == ST_DONE and c.mem[MEM_STATUS] == 0
    assert not c.flag(7)  # Hardware-reset entry retains disabled interrupts.


def test_actual_flash_worker_has_no_effect_with_disabled_selfprgen_fuse():
    c = cpu(fuse=False)
    page_address(c)
    c.flash[0x100:0x140] = b'\x33'*64
    c.run_from('block_flash_erase_only', count=100, execute_ret=True)
    c.mem[MEM_BUFFER:MEM_BUFFER+64] = b'\xAA'*64
    c.run_from('block_commit_flash', count=1000, execute_ret=True)
    assert c.flash[0x100:0x140] == b'\x33'*64
    assert not c.spm_oplog
    assert any(event[0] == 'spm_ignored' for event in c.nvm_events)


def test_page_write_without_erase_is_rejected_instead_of_restoring_zero_bits():
    c = cpu()
    page_address(c)
    c.flash[0x100:0x140] = b'\x00'*64
    c.mem[MEM_BUFFER:MEM_BUFFER+64] = b'\xff'*64
    with pytest.raises(AssertionError, match='erased page'):
        c.run_from('block_commit_flash', count=1000, execute_ret=True)
    assert c.flash[0x100:0x140] == b'\x00'*64


@pytest.mark.parametrize('delay,accepted', [(0, True), (3, True), (4, False), (8, False)])
def test_spm_enable_expires_after_four_clocks(delay, accepted):
    c = cpu()
    c.r[30], c.r[31] = 0, 1
    c.flash[0x100:0x140] = b'\x00'*64
    spm(c, 3, delay=delay)
    assert (c.flash[0x100:0x140] == b'\xff'*64) == accepted
    assert c.read_io(0x37) == 0


def test_temporary_buffer_word_load_requires_clear_between_repeats():
    c = cpu()
    c.r[30], c.r[31] = 1, 1  # Z0 is ignored by hardware.
    c.r[0], c.r[1] = 0x12, 0x34
    spm(c, 1)
    assert c.spm_buffer[:2] == b'\x12\x34'
    with pytest.raises(AssertionError, match='Duplicate'):
        spm(c, 1)
    spm(c, 0x11)
    assert c.spm_buffer == b'\xff'*64
    spm(c, 1)
    assert c.spm_buffer[:2] == b'\x12\x34'


def test_eeprom_busy_blocks_spmcsr_and_destroys_staged_flash_words():
    c = cpu()
    c.r[30], c.r[31] = 0, 1
    c.r[0], c.r[1] = 0x12, 0x34
    spm(c, 1)
    assert c._spm_loaded_words == {0}
    start_eeprom(c)
    assert c.spm_buffer == b'\xff'*64 and not c._spm_loaded_words
    assert c.read_io(0x1F)&2
    c.flash[0x100:0x140] = b'\x00'*64
    spm(c, 3)
    assert c.flash[0x100:0x140] == b'\x00'*64
    assert any(event[0] == 'spmcsr_blocked' for event in c.nvm_events)
    with pytest.raises(AssertionError, match='EERE during EEPROM write'):
        c.write_io(0x1F, 1)


@pytest.mark.parametrize('delay,accepted', [(0, True), (2, True), (4, False), (8, False)])
def test_eeprom_master_enable_expires_after_four_clocks(delay, accepted):
    c = cpu()
    start_eeprom(c, delay=delay)
    assert bool(c.read_io(0x1F)&2) == accepted
    assert c.eeprom[7] == 0xFF
    c.advance_nvm_cycles(MODEL_EEPROM_PROGRAM_CYCLES)
    assert c.eeprom[7] == (0x5A if accepted else 0xFF)
    assert not c.read_io(0x1F)&2


def test_actual_eeprom_worker_waits_for_every_byte_and_last_completion():
    c = cpu()
    c.mem[MEM_STATE] = ST_WRITE_EEPROM
    c.mem[MEM_STATUS] = 1
    c.mem[MEM_ADDR_LO] = 62
    c.mem[MEM_PROGRESS] = 0
    c.mem[MEM_INDEX] = 2
    c.mem[MEM_BUFFER:MEM_BUFFER+2] = b'AB'
    eeprom_service(c)
    assert c.mem[MEM_PROGRESS] == 1 and c.eeprom[62:] == b'\xff\xff'
    assert c.read_io(0x1F)&2
    eeprom_service(c)
    assert c.mem[MEM_PROGRESS] == 1  # Busy must not start the second byte.
    c.advance_nvm_cycles(MODEL_EEPROM_PROGRAM_CYCLES)
    assert c.eeprom[62:] == b'A\xff'
    eeprom_service(c)
    assert c.mem[MEM_PROGRESS] == 2 and c.mem[MEM_STATE] == ST_WRITE_EEPROM
    c.advance_nvm_cycles(MODEL_EEPROM_PROGRAM_CYCLES)
    eeprom_service(c)
    assert c.eeprom[62:] == b'AB'
    assert c.mem[MEM_STATE] == ST_DONE and c.mem[MEM_STATUS] == 0
    assert c.mem[0x100] == 0  # Queue USB status only after last byte completes.
    assert c.eeprom_oplog == [(62, ord('A')), (63, ord('B'))]


def test_eeprom_read_stalls_are_additional_to_instruction_only_profile():
    strict, functional = cpu(), cpu(strict=False)
    for c in (strict, functional):
        c.eeprom[:] = bytes(range(64))
        c.set_setup(0x10, 0, 64, 1, 0xC0)
        c.run_from('block_read_setup', stop_at=['L1f22'], count=1500, execute_ret=True)
        assert c.mem[MEM_BUFFER:MEM_BUFFER+64] == bytes(range(64))
    assert strict.cycles-functional.cycles == 64*4
