"""Validate empty DATA before ACK using actual post-decode AVR paths.

These tests cover the bounded zero-payload path, not nonempty DATA CRC or
electrical receive timing. The independent bus timing suite measures SOP.
"""
from pathlib import Path
import random

import pytest

import avr_sim
from avr_sim import BOOT, CPU


ROOT = Path(__file__).resolve().parents[1]
DATA1 = 0x4B
OUT = 0xE1
RX_LENGTH = 0x0112
RX_TOKEN = 0x010D
CURRENT_TOKEN = 0x0114


@pytest.fixture(scope='module')
def image_and_symbols():
    raw = (ROOT / 'build/block64.full.bin').read_bytes()
    image = bytearray(b'\xff' * 8192)
    image[BOOT:len(raw)] = raw[BOOT:]
    return bytes(image), avr_sim.syms()


@pytest.fixture
def make_cpu(image_and_symbols, monkeypatch):
    image, labels = image_and_symbols
    monkeypatch.setattr(avr_sim, 'syms', lambda: dict(labels))

    def make(*, length=3, pid=DATA1, token=OUT, crc=(0, 0), busy=False):
        cpu = CPU(image=image)
        cpu.r[28:30] = [0x16, 1]
        cpu.r[30:32] = [0, 1]
        cpu.r[16] = pid
        cpu.r[19] = length
        cpu.mem[RX_LENGTH] = 11 if busy else 0
        cpu.mem[RX_TOKEN] = 0xA5
        cpu.mem[CURRENT_TOKEN] = token
        cpu.mem[0x0116:0x0119] = bytes([pid, *crc])
        cpu.mem[0x0130:0x0180] = bytes((n * 19 + 7) & 255 for n in range(80))
        return cpu

    return make


def classify(cpu):
    cpu.run_from('L1bf6', stop_at=['L1c4c', 'L1c48', 'L1be8'],
                 count=100, execute_ret=True)
    return next(name for name in ['L1c4c', 'L1c48', 'L1be8']
                if cpu.pc == cpu.labels[name])


def assert_dropped_without_application_effect(cpu):
    before_context = bytes(cpu.mem[0x0100:0x0114])
    before_memory = bytes(cpu.mem[0x0130:0x0180])
    before_flash = bytes(cpu.flash)
    before_eeprom = bytes(cpu.eeprom)
    assert classify(cpu) == 'L1be8'
    assert bytes(cpu.mem[0x0100:0x0114]) == before_context
    assert bytes(cpu.mem[0x0130:0x0180]) == before_memory
    assert bytes(cpu.flash) == before_flash
    assert bytes(cpu.eeprom) == before_eeprom
    assert not cpu.spm_oplog and not cpu.eeprom_oplog
    assert cpu.r[28:32] == [0x16, 1, 0, 1]


def test_valid_empty_data1_out_is_published_before_ack(make_cpu):
    cpu = make_cpu()
    before_memory = bytes(cpu.mem[0x0130:0x0180])
    assert classify(cpu) == 'L1c4c'
    assert cpu.mem[RX_LENGTH] == 3
    assert cpu.mem[RX_TOKEN] == OUT
    assert cpu.mem[0x0116:0x0119] == bytes([DATA1, 0, 0])
    assert bytes(cpu.mem[0x0130:0x0180]) == before_memory
    assert not cpu.spm_oplog and not cpu.eeprom_oplog


@pytest.mark.parametrize('length', [0, 1, 2])
def test_truncated_empty_data_has_no_ack(make_cpu, length):
    assert_dropped_without_application_effect(make_cpu(length=length))


@pytest.mark.parametrize('pid', [0xC3, 0, 0xD2])
def test_empty_status_requires_data1(make_cpu, pid):
    # Enter the real DATA classifier directly to test the helper's PID guard.
    assert_dropped_without_application_effect(make_cpu(pid=pid))


@pytest.mark.parametrize('token', [0, 0x2D, 0x69, 0x55])
def test_empty_status_requires_out_token(make_cpu, token):
    assert_dropped_without_application_effect(make_cpu(token=token))


def test_every_nonzero_crc_byte_is_rejected(make_cpu):
    for value in range(1, 256):
        assert_dropped_without_application_effect(make_cpu(crc=(value, 0)))
        assert_dropped_without_application_effect(make_cpu(crc=(0, value)))
    rng = random.Random(0xE0C0)
    for _ in range(128):
        crc = (rng.randrange(1, 256), rng.randrange(1, 256))
        assert_dropped_without_application_effect(make_cpu(crc=crc))


def test_busy_receive_buffer_is_not_overwritten(make_cpu):
    cpu = make_cpu(busy=True)
    before = bytes(cpu.mem[0x0100:0x0114])
    assert classify(cpu) == 'L1c48'
    assert bytes(cpu.mem[0x0100:0x0114]) == before


def test_empty_helper_valid_path_cost_is_eighteen_clocks(make_cpu):
    cpu = make_cpu()
    cpu.r[18] = OUT
    cpu.r[17] = 0
    cpu.run_from('usb_rx_empty_data', stop_at=['L1c4c'],
                 count=30, execute_ret=True)
    assert cpu.pc == cpu.labels['L1c4c']
    assert cpu.cycles == 18
