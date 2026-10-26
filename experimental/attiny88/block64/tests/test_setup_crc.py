"""Post-decode SETUP CRC gate; this does not establish PHY ACK correctness."""
from pathlib import Path

import pytest

from avr_sim import (
    BOOT, CPU, MEM_STATE, MEM_STATUS, ST_FLASH_WAIT_PREP,
    ST_IDLE, ST_RECEIVE, ST_RUN, ST_SPM_WAIT_SENT,
)

ROOT = Path(__file__).resolve().parents[1]


def crc16(payload):
    crc = 0xFFFF
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return ((~crc) & 0xFFFF).to_bytes(2, "little")


CASES = [
    # type, request, value, index, wLength, reply length, state, pointer
    (0xC0, 0x10, 0x0100, 0, 8, 8, ST_IDLE, 0x0100),
    (0xC0, 0x10, 3, 1, 8, 8, ST_IDLE, 0x8140),
    (0xC0, 0x12, 0, 0, 8, 8, ST_IDLE, 0x8138),
    (0x40, 0x11, 0x0100, 0, 64, 0xFF, ST_RECEIVE, None),
    (0x40, 0x11, 5, 1, 7, 0xFF, ST_RECEIVE, None),
    (0x40, 0x14, 0x0100, 0, 0, 0, ST_FLASH_WAIT_PREP, None),
    (0x40, 0x13, 0, 0, 0, 0, ST_RUN, None),
    (0x80, 6, 0x0100, 0, 18, 18, ST_IDLE, BOOT + 0x1A),
    (0x80, 8, 0, 0, 1, 1, ST_IDLE, 0x810A),
    (0x00, 5, 17, 0, 0, 0, ST_IDLE, 0x810A),
    (0x00, 9, 1, 0, 0, 0, ST_IDLE, 0x810A),
    (0x80, 0, 0, 0, 2, 2, ST_IDLE, 0x810A),
    (0x81, 10, 0, 0, 1, 1, ST_IDLE, 0x810A),
]


def new_cpu():
    raw = (ROOT / "build/block64.full.bin").read_bytes()
    image = bytearray(b"\xff" * 8192)
    image[BOOT:len(raw)] = raw[BOOT:]
    cpu = CPU(image=bytes(image), EEPROM=bytes(range(64)))
    cpu.run_from("startup", stop_at=["main"], count=1000)
    cpu.mem[0x0100] = 0xFF
    cpu.mem[0x0101] = 0xC3
    cpu.mem[0x010F] = 0x5A
    return cpu


def stage_setup(cpu, case, corrupt_byte=None):
    typ, request, value, index, length = case[:5]
    cpu.set_setup(request, value, length, index, typ)
    payload = bytes(cpu.mem[0x0117:0x011F])
    frame = bytearray(payload + crc16(payload))
    if corrupt_byte is not None:
        frame[corrupt_byte] ^= 1
        assert bytes(frame[8:]) != crc16(frame[:8])
    cpu.mem[0x0116] = 0xC3  # SETUP always has a DATA0 payload packet
    cpu.mem[0x0117:0x0121] = frame
    cpu.mem[0x0112] = 11
    cpu.mem[0x010D] = 0x2D


def dispatch(cpu):
    cpu.r[28:30] = [0, 1]
    cpu.run_from("L1d9c", stop_at=["L1dfc"], count=2500, execute_ret=True)
    assert cpu.pc == cpu.labels["L1dfc"]
    assert not cpu.stack
    assert cpu.mem[0x0112] == 0


@pytest.mark.parametrize("case", CASES)
def test_valid_setup_crc_preserves_standard_and_vendor_routing(case):
    cpu = new_cpu()
    stage_setup(cpu, case)
    dispatch(cpu)
    assert cpu.mem[0x0100] == case[5]
    assert cpu.mem[MEM_STATE] == case[6]
    if case[7] is not None:
        assert int.from_bytes(cpu.mem[0x0110:0x0112], "little") == case[7]
    if case[1] == 0x11:
        assert cpu.mem[0x0133] == case[4]
        assert cpu.mem[0x0137] == 0x4B
    if case[:2] == (0, 5):
        assert cpu.mem[0x0113] == 17
    if case[:2] == (0, 9):
        assert cpu.mem[0x0115] == 1
    if case[:2] == (0xC0, 0x10) and case[3] == 1:
        assert cpu.mem[0x0140:0x0148] == bytes(range(3, 11))
    assert not cpu.spm_oplog
    assert not cpu.eeprom_oplog


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("corrupt_byte", range(10))
@pytest.mark.parametrize("state", [ST_IDLE, ST_RECEIVE, ST_SPM_WAIT_SENT])
def test_corrupt_setup_or_trailer_byte_only_releases_receive_buffer(case, corrupt_byte, state):
    cpu = new_cpu()
    cpu.mem[0x0100:0x0112] = bytes((i * 13 + 7) & 0xFF for i in range(18))
    cpu.mem[0x0130:0x0180] = bytes((i * 17 + 11) & 0xFF for i in range(80))
    cpu.mem[MEM_STATE] = state
    cpu.mem[MEM_STATUS] = 0xA5
    cpu.r[7] = 0xB7  # bad SETUP must not extend inactivity timeout either
    stage_setup(cpu, case, corrupt_byte)
    before_context = bytes(cpu.mem[0x0100:0x0112])
    before_flags = bytes(cpu.mem[0x0113:0x0116])
    before_memory_state = bytes(cpu.mem[0x0130:0x0180])
    before_flash = bytes(cpu.flash)
    before_eeprom = bytes(cpu.eeprom)
    dispatch(cpu)
    assert bytes(cpu.mem[0x0100:0x0112]) == before_context
    assert bytes(cpu.mem[0x0113:0x0116]) == before_flags
    assert bytes(cpu.mem[0x0130:0x0180]) == before_memory_state
    assert cpu.r[7] == 0xB7
    assert bytes(cpu.flash) == before_flash
    assert bytes(cpu.eeprom) == before_eeprom
    assert not cpu.spm_oplog
    assert not cpu.eeprom_oplog
