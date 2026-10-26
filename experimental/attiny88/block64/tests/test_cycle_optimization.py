"""Pass13 cycle-focused and boundary tests for the real assembled AVR words.

Cycles modeled from the AVR instruction set (not wall-clock SPM erase/write time
and not a physical USB bus). These are intended as regression ceilings.
"""
from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
from avr_sim import CPU, MEM_ADDR_LO, MEM_ADDR_HI, MEM_BUFFER, MEM_STATE, MEM_PROGRESS, MEM_INDEX, ST_WRITE_EEPROM

@pytest.fixture(scope='module')
def firmware():
    return (ROOT/'firmware/ISP_FULL_8192_1980_PASS13.bin').read_bytes()


def test_idle_dispatch_cycles_and_state(firmware):
    for state in (0,1,2,4,6,7):
        cpu = CPU(image=firmware)
        cpu.mem[MEM_STATE] = state
        cpu.run_from('L1d5e', stop_at=['L1d9c'], execute_ret=True, count=180)
        assert cpu.pc == cpu.labels['L1d9c']
        assert cpu.mem[MEM_STATE] == state
        if state in (0,1,2):
            assert cpu.cycles <= 8, (state,cpu.cycles)
    cpu = CPU(image=firmware)
    cpu.mem[MEM_STATE] = 3
    cpu.mem[0x010f] = 0x5a
    cpu.run_from('L1d5e', stop_at=['L1eac'], execute_ret=True, count=180)
    assert cpu.pc == cpu.labels['L1eac']


def test_eeprom_read_64_cycle_budget(firmware):
    data = bytes((v*31+17)&255 for v in range(64))
    cpu = CPU(image=firmware, EEPROM=data)
    cpu.set_setup(0x10,0,64,1,0xc0)
    cpu.run_from('block_read_setup', stop_at=['L1f22','block_reject'],count=3000,execute_ret=True)
    assert bytes(cpu.mem[MEM_BUFFER:MEM_BUFFER+64]) == data
    assert cpu.cycles <= 636, cpu.cycles


def test_eeprom_write_64_cycle_budget(firmware):
    cpu = CPU(image=firmware)
    cpu.mem[MEM_ADDR_LO] = 0
    cpu.mem[MEM_PROGRESS] = 0
    cpu.mem[MEM_INDEX] = 64
    cpu.mem[MEM_STATE] = ST_WRITE_EEPROM
    cpu.mem[MEM_BUFFER:MEM_BUFFER+64] = bytes(range(64))
    for i in range(64):
        cpu.run_from('block_step_eeprom', execute_ret=False, count=100)
        assert cpu.mem[MEM_PROGRESS] == i+1
    assert cpu.eeprom == bytes(range(64))
    assert cpu.cycles <= 1856, cpu.cycles


def test_flash_word_loading_no_16bit_overflow_dependency(firmware):
    # Exercises every address low-byte (0x00,0x40,0x80,0xC0), including
    # ZL=0xFE -> 0x00 at the final fill operation, before Z is reloaded.
    for page in range(0,0x1980,64):
        data = bytes(((page//64)*7 +i*11)&255 for i in range(64))
        cpu = CPU(image=firmware)
        cpu.r[28],cpu.r[29] = 0,1
        cpu.mem[MEM_ADDR_LO],cpu.mem[MEM_ADDR_HI] = page&255,page>>8
        cpu.mem[MEM_BUFFER:MEM_BUFFER+64] = data
        cpu.run_from('block_commit_flash', count=1500, execute_ret=True)
        expected = bytearray(data)
        if page == 0:
            reset = 0xC000|(((0x1980//2)-1)&0xFFF)
            expected[:2]=reset.to_bytes(2,'little')
        assert cpu.flash[page:page+64]==expected, hex(page)
        loads=[rec for rec in cpu.spm_oplog if rec[0]=='load']
        assert [rec[1] for rec in loads] == [page+i for i in range(0,64,2)],hex(page)
        assert ('write',page) in cpu.spm_oplog
        if page==0x18c0:
            assert cpu.cycles <= 468, cpu.cycles


def test_eeprom_eecr_write_strobes_are_equivalent(firmware):
    # During EERE, the current EEPROM mode is reset's standard EEPM=00
    # and busy EEPE=0. OUT EECR, 1 strobes EERE just like SBI EECR,EERE.
    cpu=CPU(image=firmware, EEPROM=bytes(range(64)))
    cpu.set_setup(0x10,63,1,1,0xc0)
    cpu.run_from('block_read_setup', stop_at=['L1f22','block_reject'], count=1000, execute_ret=True)
    assert cpu.mem[MEM_BUFFER]==63
    assert cpu.io[0x1f]&1==0  # EERE is self-clearing


def test_vusb_phy_module_unchanged_from_pass12():
    ref=ROOT/'reference/Pass12_vusb_phy.inc'
    now=ROOT/'source/vusb_phy.inc'
    assert ref.read_bytes()==now.read_bytes()
