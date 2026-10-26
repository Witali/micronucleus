"""ACK ownership through actual post-decode receive and IN transmit opcodes.

These tests inject sampler output, not an electrical USB waveform. They
exercise the classifier, NRZI TX/EOP path, packetizer and memory interlock;
they do not call an ACK-completion helper directly.
"""
from pathlib import Path

import pytest

from avr_sim import BOOT, CPU, MEM_STATE, ST_DONE, ST_FLASH_WAIT_PREP, ST_WRITE_EEPROM


ROOT = Path(__file__).resolve().parents[1]
ACK = 0xD2
NAK = 0x5A
DATA0 = 0xC3
DATA1 = 0x4B
DEVICE_ADDRESS = 3
PAGE = 0x0200


@pytest.fixture
def cpu():
    raw = (ROOT / 'build/block64.full.bin').read_bytes()
    image = bytearray(b'\xff' * 8192)
    image[BOOT:len(raw)] = raw[BOOT:]
    instance = CPU(image=bytes(image))
    instance.run_from('startup', stop_at=['main'], count=1000)
    instance.mem[0x010C] = DEVICE_ADDRESS << 1
    instance.mem[0x0113] = DEVICE_ADDRESS
    instance.mem[0x010F] = NAK
    instance.mem[0x0100] = 0xFF
    return instance


def context(cpu):
    cpu.r[28:30] = [0, 1]
    cpu.r[30:32] = [0, 1]


def prepare(cpu):
    context(cpu)
    cpu.run_from('L1dfc', stop_at=['L1e64'], count=2500, execute_ret=True)


def queued(cpu):
    length = cpu.mem[0x010F]
    assert 4 <= length <= 12, 'No DATA packet queued'
    return length, bytes(cpu.mem[0x0101:0x0101 + length - 1])


def transmit(cpu):
    """Run a real IN DATA transmission without synthesizing its host ACK."""
    context(cpu)
    cpu.mem[0x0112] = 0
    cpu.run_from('L1c14', stop_at=['L1be8'], count=5000, execute_ret=True)
    assert not cpu.stack


def expire_ack_wait(cpu):
    """Run the real no-SOP timeout, stopping before wrapper stack restoration."""
    cpu.io[0x1B] = 0
    cpu.run_from('L1be8', stop_at=['usb_handler_pop_packet_register'],
                 count=1000, execute_ret=True)
    assert not cpu.stack


def classify(cpu, frame):
    """Enter immediately after RX byte sampling and length recovery inputs."""
    assert 0 <= len(frame) <= 11
    cpu.mem[0x0116:0x0116 + len(frame)] = frame
    address = 0x0116 + len(frame)
    cpu.r[28:30] = [address & 255, address >> 8]
    cpu.r[30:32] = [0, 1]
    cpu.r[19] = 11 - len(frame)
    cpu.run_from('L1baa', stop_at=['L1be8'], count=5000, execute_ret=True)
    assert not cpu.stack


def token(pid, address=DEVICE_ADDRESS, endpoint=0):
    """Encode a token with an independently calculated USB CRC5."""
    bits = address | (endpoint << 7)
    value, crc = bits, 0x1F
    for _ in range(11):
        feedback = (value ^ crc) & 1
        value >>= 1
        crc >>= 1
        if feedback:
            crc ^= 0x14
    encoded = bits | ((crc ^ 0x1F) << 11)
    return bytes([pid, encoded & 255, encoded >> 8])


def crc16(payload):
    result = 0xFFFF
    for byte in payload:
        result ^= byte
        for _ in range(8):
            result = (result >> 1) ^ (0xA001 if result & 1 else 0)
    return ((~result) & 0xFFFF).to_bytes(2, 'little')


def read_reply(cpu, size=16, memory='flash'):
    original = bytes((index * 37 + 11) & 255 for index in range(size))
    if memory == 'flash':
        cpu.flash[PAGE:PAGE + size] = original
        pointer = PAGE
    else:
        cpu.mem[0x0140:0x0140 + size] = original
        pointer = 0x8140
    cpu.mem[0x0100] = size
    cpu.mem[0x0101] = DATA0
    cpu.mem[0x0110:0x0112] = pointer.to_bytes(2, 'little')
    prepare(cpu)
    return original


@pytest.mark.parametrize('memory', ['flash', 'sram'])
@pytest.mark.parametrize('length', [1, 7, 8, 9, 16, 63, 64])
def test_repeated_in_without_ack_keeps_identical_packet(cpu, memory, length):
    original = read_reply(cpu, length, memory)
    first = queued(cpu)
    assert first[1][0] == DATA1
    assert first[1][1:-2] == original[:8]
    for _ in range(3):
        transmit(cpu)
        prepare(cpu)
        assert queued(cpu) == first
    assert not cpu.spm_oplog


@pytest.mark.parametrize('memory', ['flash', 'sram'])
def test_ack_advances_once_and_duplicate_ack_cannot_consume_next_packet(cpu, memory):
    original = read_reply(cpu, 24, memory)
    first = queued(cpu)
    # Stray ACK before transmission is not associated with any DATA packet.
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    assert queued(cpu) == first

    transmit(cpu)
    classify(cpu, bytes([ACK]))
    # A second ACK before another IN transmission has no owner.
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    second = queued(cpu)
    assert second[1][0] == DATA0
    assert second[1][1:-2] == original[8:16]
    assert second != first

    classify(cpu, bytes([ACK]))
    prepare(cpu)
    assert queued(cpu) == second
    transmit(cpu)
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    third = queued(cpu)
    assert third[1][0] == DATA1
    assert third[1][1:-2] == original[16:24]


@pytest.mark.parametrize('memory', ['flash', 'sram'])
def test_ack_after_actual_handshake_timeout_is_ignored(cpu, memory):
    original = read_reply(cpu, 16, memory)
    first = queued(cpu)
    transmit(cpu)
    expire_ack_wait(cpu)
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    assert queued(cpu) == first
    transmit(cpu)
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    assert queued(cpu)[1][1:-2] == original[8:16]


def dispatch_received(cpu):
    context(cpu)
    cpu.run_from('L1d9c', stop_at=['L1e64'], count=3000, execute_ret=True)


def test_valid_read_status_out_completes_even_when_last_in_ack_was_lost(cpu):
    read_reply(cpu, 8)
    transmit(cpu)
    classify(cpu, token(0xE1))
    classify(cpu, bytes([DATA1, 0, 0]))
    assert cpu.mem[0x0112] == 3
    dispatch_received(cpu)
    assert cpu.mem[0x010F] == NAK and cpu.mem[0x0100] == 0xFF
    assert not cpu.spm_oplog

    # Repeated status after a lost device ACK remains harmless and valid.
    classify(cpu, token(0xE1))
    classify(cpu, bytes([DATA1, 0, 0]))
    dispatch_received(cpu)
    assert cpu.mem[0x010F] == NAK and cpu.mem[0x0100] == 0xFF
    assert not cpu.spm_oplog


@pytest.mark.parametrize('frame', [bytes([DATA1]), bytes([DATA1, 0]),
                                  bytes([DATA1, 1, 0]), bytes([DATA1, 0, 1]),
                                  bytes([DATA1, 1, 1]), bytes([DATA0, 0, 0])])
def test_invalid_read_status_out_cannot_complete_lost_ack_transfer(cpu, frame):
    read_reply(cpu, 8)
    first = queued(cpu)
    transmit(cpu)
    classify(cpu, token(0xE1))
    classify(cpu, frame)
    assert cpu.mem[0x0112] == 0
    dispatch_received(cpu)
    assert queued(cpu) == first
    assert not cpu.spm_oplog


@pytest.mark.parametrize('frame', [b''] + [bytes([ACK]) + b'\x00' * count for count in range(1, 11)]
                         + [bytes([value]) for value in
                            [0x00, 0x12, 0x52, 0x92, 0xF2, 0x5A, 0x1E,
                             DATA0, DATA1, 0x69, 0xE1, 0x2D]])
def test_malformed_or_non_ack_handshake_cannot_advance_in(cpu, frame):
    read_reply(cpu)
    first = queued(cpu)
    transmit(cpu)
    cpu.mem[0x0116] = ACK  # A zero-byte frame must not reuse a stale PID.
    classify(cpu, frame)
    # Even a later correctly encoded ACK is stale after an intervening packet.
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    assert queued(cpu) == first


@pytest.mark.parametrize('pid', [0x69, 0xE1, 0x2D])
@pytest.mark.parametrize('address', [0, 1, 4, 127])
def test_foreign_token_disarms_late_ack(cpu, pid, address):
    read_reply(cpu)
    first = queued(cpu)
    transmit(cpu)
    classify(cpu, token(pid, address=address))
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    assert queued(cpu) == first


@pytest.mark.parametrize('endpoint', [1, 2, 7, 8, 15])
def test_nonzero_endpoint_in_does_not_rearm_ep0_ack_window(cpu, endpoint):
    read_reply(cpu)
    first = queued(cpu)
    transmit(cpu)
    classify(cpu, token(0x69, endpoint=endpoint))
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    assert queued(cpu) == first


def begin_erase(cpu):
    cpu.flash[PAGE:PAGE + 64] = b'\x55' * 64
    cpu.set_setup(0x14, PAGE, 0, 0, 0x40)
    cpu.run_from('block_erase_setup', stop_at=['L1df8'], count=800, execute_ret=True)
    assert cpu.mem[MEM_STATE] == ST_FLASH_WAIT_PREP
    prepare(cpu)
    assert queued(cpu)[0] == 4


def quiet(cpu):
    context(cpu)
    cpu.run_from('block_spm_after_quiet', count=2000, execute_ret=True)


def setup(cpu, request, *, kind=0xC0, address=0, index=0, length=8):
    cpu.set_setup(request, address, length, index, kind)
    payload = bytes(cpu.mem[0x0117:0x011F])
    cpu.mem[0x011F:0x0121] = crc16(payload)
    cpu.mem[0x0112] = 11
    cpu.mem[0x010D] = 0x2D
    context(cpu)
    cpu.run_from('L1d9c', stop_at=['L1e64'], count=3000, execute_ret=True)


def test_flash_erase_waits_for_its_status_zlp_ack(cpu):
    begin_erase(cpu)
    quiet(cpu)
    assert not cpu.spm_oplog
    first = queued(cpu)
    for _ in range(2):
        transmit(cpu)
        quiet(cpu)
        prepare(cpu)
        assert queued(cpu) == first
        assert not cpu.spm_oplog

    classify(cpu, bytes([ACK]))
    quiet(cpu)
    assert cpu.flash[PAGE:PAGE + 64] == b'\xff' * 64
    assert cpu.spm_oplog == [('erase', PAGE)]
    assert cpu.mem[MEM_STATE] == ST_DONE
    quiet(cpu)
    assert cpu.spm_oplog == [('erase', PAGE)]


def test_full_flash_write_waits_for_its_status_zlp_ack(cpu):
    payload = bytes((index * 17 + 5) & 255 for index in range(64))
    cpu.flash[PAGE:PAGE + 64] = b'\xff' * 64
    setup(cpu, 0x11, kind=0x40, address=PAGE, length=64)
    pid = DATA1
    for offset in range(0, 64, 8):
        part = payload[offset:offset + 8]
        cpu.mem[0x010D] = 0xE1
        cpu.mem[0x0116] = pid
        cpu.mem[0x0117:0x011F] = part
        cpu.mem[0x011F:0x0121] = crc16(part)
        context(cpu)
        cpu.r[24] = 8
        cpu.run_from('block_out_packet', stop_at=['L1df8'], count=2500, execute_ret=True)
        cpu.run_from('L1df8', stop_at=['L1dfc'], count=10)
        pid ^= 0x88
    assert cpu.mem[MEM_STATE] == ST_FLASH_WAIT_PREP
    prepare(cpu)
    assert queued(cpu)[0] == 4
    transmit(cpu)
    quiet(cpu)
    assert not cpu.spm_oplog
    assert cpu.flash[PAGE:PAGE + 64] == b'\xff' * 64
    classify(cpu, bytes([ACK]))
    quiet(cpu)
    assert cpu.flash[PAGE:PAGE + 64] == payload
    assert [event for event in cpu.spm_oplog if event[0] == 'write'] == [('write', PAGE)]
    assert not any(event[0] == 'erase' for event in cpu.spm_oplog)
    assert cpu.mem[MEM_STATE] == ST_DONE
    completed = list(cpu.spm_oplog)
    quiet(cpu)
    assert cpu.spm_oplog == completed


@pytest.mark.parametrize('length', [0, 8])
def test_new_status_setup_cannot_complete_the_old_erase(cpu, length):
    begin_erase(cpu)
    transmit(cpu)
    setup(cpu, 0x12, length=length)
    # This ACK may be a delayed ACK for the aborted mutation; no new DATA
    # transmission has occurred, so it cannot complete the new status reply.
    classify(cpu, bytes([ACK]))
    quiet(cpu)
    assert not cpu.spm_oplog
    if 4 <= cpu.mem[0x010F] <= 12:
        transmit(cpu)
        classify(cpu, bytes([ACK]))
    quiet(cpu)
    assert not cpu.spm_oplog
    assert cpu.flash[PAGE:PAGE + 64] == b'\x55' * 64


def test_acknowledged_erase_survives_a_new_setup_and_runs_once(cpu):
    begin_erase(cpu)
    transmit(cpu)
    classify(cpu, bytes([ACK]))
    setup(cpu, 0x12)
    quiet(cpu)
    assert cpu.flash[PAGE:PAGE + 64] == b'\xff' * 64
    assert cpu.spm_oplog == [('erase', PAGE)]
    quiet(cpu)
    assert cpu.spm_oplog == [('erase', PAGE)]


def test_new_mutating_setup_replaces_only_unacknowledged_erase(cpu):
    begin_erase(cpu)
    transmit(cpu)
    target = PAGE + 64
    cpu.flash[target:target + 64] = b'\x66' * 64
    setup(cpu, 0x14, kind=0x40, address=target, length=0)
    classify(cpu, bytes([ACK]))
    quiet(cpu)
    assert not cpu.spm_oplog
    transmit(cpu)
    classify(cpu, bytes([ACK]))
    quiet(cpu)
    assert cpu.flash[PAGE:PAGE + 64] == b'\x55' * 64
    assert cpu.flash[target:target + 64] == b'\xff' * 64
    assert cpu.spm_oplog == [('erase', target)]


@pytest.mark.parametrize('address', [0, 17, 127])
def test_set_address_commits_only_after_its_status_ack(cpu, address):
    setup(cpu, 5, kind=0x00, address=address, length=0)
    packet = queued(cpu)
    assert packet[0] == 4
    assert cpu.mem[0x010C] == DEVICE_ADDRESS << 1
    for _ in range(2):
        transmit(cpu)
        prepare(cpu)
        assert queued(cpu) == packet
        assert cpu.mem[0x010C] == DEVICE_ADDRESS << 1
    classify(cpu, bytes([ACK]))
    assert cpu.mem[0x010C] == address << 1


@pytest.mark.parametrize('pending', [0, 17, 127])
@pytest.mark.parametrize('length', [0, 8])
def test_new_setup_cancels_unacknowledged_set_address(cpu, pending, length):
    setup(cpu, 5, kind=0x00, address=pending, length=0)
    transmit(cpu)
    setup(cpu, 0x12, length=length)
    classify(cpu, bytes([ACK]))
    assert cpu.mem[0x010C] == DEVICE_ADDRESS << 1
    transmit(cpu)
    classify(cpu, bytes([ACK]))
    assert cpu.mem[0x010C] == DEVICE_ADDRESS << 1


def run_service(cpu):
    context(cpu)
    cpu.r[18] = cpu.mem[MEM_STATE]
    cpu.run_from('block_memory_service', stop_at=['L1eac'], count=300, execute_ret=True)
    return cpu.pc == cpu.labels['L1eac']


def test_run_handover_waits_for_its_status_ack(cpu):
    setup(cpu, 0x13, kind=0x40, length=0)
    transmit(cpu)
    assert not run_service(cpu)
    classify(cpu, bytes([ACK]))
    assert run_service(cpu)


def test_new_setup_cancels_unacknowledged_run(cpu):
    setup(cpu, 0x13, kind=0x40, length=0)
    transmit(cpu)
    setup(cpu, 0x12)
    classify(cpu, bytes([ACK]))
    assert not run_service(cpu)
    transmit(cpu)
    classify(cpu, bytes([ACK]))
    assert not run_service(cpu)


def test_new_setup_detaches_an_active_eeprom_write_status(cpu):
    setup(cpu, 0x11, kind=0x40, address=62, index=1, length=2)
    cpu.mem[0x0116] = DATA1
    cpu.mem[0x0117:0x0119] = b'AB'
    cpu.mem[0x0119:0x011B] = crc16(b'AB')
    context(cpu)
    cpu.r[24] = 2
    cpu.run_from('block_out_packet', stop_at=['L1df8'], count=2500, execute_ret=True)
    cpu.run_from('L1df8', stop_at=['L1dfc'], count=10)
    assert cpu.mem[MEM_STATE] == ST_WRITE_EEPROM
    assert not run_service(cpu)
    assert cpu.eeprom[62:64] == b'A\xff'

    # A legal short standard reply makes its EMPTY_MESSAGE sentinel observable:
    # the old EEPROM completion must not replace it with another status ZLP.
    setup(cpu, 8, kind=0x80, length=1)  # GET_CONFIGURATION
    packet = queued(cpu)
    assert packet[0] == 5 and cpu.mem[0x0100] == 0xFF
    assert not run_service(cpu)
    assert not run_service(cpu)
    assert cpu.eeprom[62:64] == b'AB'
    assert cpu.mem[MEM_STATE] == ST_DONE
    assert queued(cpu) == packet
    assert cpu.mem[0x0100] == 0xFF
    transmit(cpu)
    classify(cpu, bytes([ACK]))
    prepare(cpu)
    assert cpu.mem[0x010F] == NAK
