"""EP0 token CRC5 cache against independent eleven-bit USB token encoding.

USB 2.0 section 8.3.5.1 covers ADDR+ENDP with polynomial x^5+x^2+1.
Tests execute real helper, SET_ADDRESS, ACK and token-classification opcodes;
they do not establish electrical USB or receive-waveform compliance.
"""
from pathlib import Path

import pytest

import avr_sim
from avr_sim import BOOT, CPU


ROOT = Path(__file__).resolve().parents[1]
CACHE = 0x012E
DEVICE_ADDRESS = 3


def token(address, endpoint=0, pid=0x69):
    """Feed each input bit independently; do not use the firmware's folding."""
    message = address | (endpoint << 7)
    remainder = 0x1F
    for bit in range(11):
        feedback = ((message >> bit) ^ remainder) & 1
        remainder >>= 1
        if feedback:
            remainder ^= 0x14
    encoded = message | ((remainder ^ 0x1F) << 11)
    return bytes([pid, encoded & 255, encoded >> 8])


def crc16(payload):
    crc = 0xFFFF
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return ((~crc) & 0xFFFF).to_bytes(2, 'little')


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

    def make():
        cpu = CPU(image=image)
        cpu.run_from('startup', stop_at=['main'], count=1000)
        cpu.mem[0x0100] = 0xFF
        cpu.mem[0x010F] = 0x5A
        return cpu

    return make


def context(cpu):
    cpu.r[28:30] = [0, 1]
    cpu.r[30:32] = [0, 1]


def classify(cpu, frame):
    cpu.mem[0x0116:0x0116 + len(frame)] = frame
    end = 0x0116 + len(frame)
    cpu.r[28:30] = [end & 255, end >> 8]
    cpu.r[30:32] = [0, 1]
    cpu.r[19] = 11 - len(frame)
    cpu.run_from('L1baa', stop_at=['L1be8'], count=5000, execute_ret=True)


def setup(cpu, request, *, address=0, kind=0xC0, length=8):
    cpu.set_setup(request, address, length, 0, kind)
    cpu.mem[0x011F:0x0121] = crc16(cpu.mem[0x0117:0x011F])
    cpu.mem[0x0112] = 11
    cpu.mem[0x010D] = 0x2D
    context(cpu)
    cpu.run_from('L1d9c', stop_at=['L1e64'], count=3000, execute_ret=True)


def transmit(cpu):
    context(cpu)
    cpu.mem[0x0112] = 0
    cpu.run_from('L1c14', stop_at=['L1be8'], count=5000, execute_ret=True)


def active_address(cpu, address):
    cpu.mem[0x010C] = address << 1
    cpu.mem[0x0113] = address
    cpu.mem[CACHE] = token(address)[2]


def test_startup_initializes_address_zero_token_crc5(make_cpu):
    cpu = make_cpu()
    assert token(0) == b'\x69\x00\x10'
    assert cpu.mem[0x010C] == 0 and cpu.mem[CACHE] == 0x10


def test_crc5_helper_all_addresses_preserves_call_contract_and_takes_80_cycles(make_cpu):
    cpu = make_cpu()
    assert cpu.labels['usb_token_crc5_end'] - cpu.labels['usb_update_token_crc5'] == 32
    for address in range(128):
        for flags in [0, 0xFF, 0x55, 0xAA]:
            cpu.r[:] = [(index * 19 + address) & 255 for index in range(32)]
            cpu.r[18] = address << 1
            cpu.r[28:30] = [0xA5, 0x5A]
            cpu.r[30:32] = [0, 1]
            before_registers = list(cpu.r)
            before_memory = bytearray(cpu.mem)
            before_memory[CACHE] = token(address)[2]
            cpu.sreg = flags
            cpu.cycles = 0
            cpu.run_from('usb_update_token_crc5', count=200, execute_ret=True)
            assert cpu.cycles == 80
            assert cpu.mem == before_memory
            for register in set(range(32)) - {18, 22, 23}:
                assert cpu.r[register] == before_registers[register]
            assert not cpu.stack and not cpu.spm_oplog and not cpu.eeprom_oplog


@pytest.mark.parametrize('address', range(128))
@pytest.mark.parametrize('pid', [0x69, 0xE1, 0x2D])
def test_token_classifier_accepts_only_the_correct_crc5_for_each_address(make_cpu, address, pid):
    cpu = make_cpu()
    active_address(cpu, address)
    cpu.flash[0x0200] = 0xA5
    cpu.mem[0x0100] = 1
    cpu.mem[0x0101] = 0xC3
    cpu.mem[0x0110:0x0112] = b'\x00\x02'
    context(cpu)
    cpu.run_from('L1dfc', stop_at=['L1e64'], count=2500, execute_ret=True)
    writes = []
    original_write = cpu.write_io

    def write_io(port, value):
        if port in (0x0A, 0x0B):
            writes.append((port, value))
        original_write(port, value)

    cpu.write_io = write_io
    expected = token(address, pid=pid)
    for checksum in range(32):
        writes.clear()
        classify(cpu, bytes([pid, address, checksum << 3]))
        correct = checksum << 3 == expected[2]
        assert bool(writes) == (correct and pid == 0x69)
        if pid != 0x69:
            assert cpu.mem[0x0114] == (pid if correct else 0)
    for endpoint in [1, 2, 7, 8, 15]:
        writes.clear()
        classify(cpu, token(address, endpoint, pid))
        assert not writes
        if pid != 0x69:
            assert cpu.mem[0x0114] == 0
    assert cpu.mem[CACHE] == expected[2]


@pytest.mark.parametrize('address', range(128))
def test_set_address_updates_token_crc_only_after_matching_status_ack(make_cpu, address):
    cpu = make_cpu()
    active_address(cpu, DEVICE_ADDRESS)
    setup(cpu, 5, kind=0x00, address=address, length=0)
    transmit(cpu)
    assert cpu.mem[0x010C] == DEVICE_ADDRESS << 1
    assert cpu.mem[CACHE] == token(DEVICE_ADDRESS)[2]
    classify(cpu, b'\xD2')
    assert cpu.mem[0x010C] == address << 1
    assert cpu.mem[CACHE] == token(address)[2]


@pytest.mark.parametrize('address', range(128))
def test_new_setup_cancels_pending_address_and_preserves_cached_crc(make_cpu, address):
    cpu = make_cpu()
    active_address(cpu, DEVICE_ADDRESS)
    setup(cpu, 5, kind=0x00, address=address, length=0)
    transmit(cpu)
    setup(cpu, 0x12)
    classify(cpu, b'\xD2')  # Late ACK before the new IN has no owner.
    assert cpu.mem[0x010C] == DEVICE_ADDRESS << 1
    assert cpu.mem[CACHE] == token(DEVICE_ADDRESS)[2]
    transmit(cpu)
    classify(cpu, b'\xD2')
    assert cpu.mem[0x010C] == DEVICE_ADDRESS << 1
    assert cpu.mem[CACHE] == token(DEVICE_ADDRESS)[2]
