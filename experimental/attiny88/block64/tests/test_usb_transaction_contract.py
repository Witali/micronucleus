"""USB transaction contracts missing from the original handler-only checks.

These execute compiled AVR paths from the post-decode receive classifier or
the IN handler through its actual transmit loop. They do not synthesize NRZI
input, electrical timing, or a real USB host. Strict expected failures record
confirmed protocol defects; an unexpected pass requires reviewing the fix.
USB 2.0 sections 8.4.5, 8.5.3 and 8.6 define the applicable contracts.
"""
from pathlib import Path

import pytest

from avr_sim import (
    BOOT, CPU, MEM_BUFFER, MEM_EXPECT_PID, MEM_INDEX, MEM_REMAIN, MEM_STATE,
    ST_FLASH_WAIT_PREP, ST_IDLE, ST_RECEIVE, ST_SPM_WAIT_SENT,
)

ROOT = Path(__file__).resolve().parents[1]
NAK = 0x5A
ACK = 0xD2
DATA0 = 0xC3
DATA1 = 0x4B


class USBContractViolation(AssertionError):
    """Only the intended protocol assertion may satisfy a known-failure mark."""


def require_contract(condition, message):
    if not condition:
        raise USBContractViolation(message)


def crc16(payload):
    result = 0xFFFF
    for byte in payload:
        result ^= byte
        for _ in range(8):
            result = (result >> 1) ^ (0xA001 if result & 1 else 0)
    return ((~result) & 0xFFFF).to_bytes(2, "little")


@pytest.fixture
def cpu():
    raw = (ROOT / "build/block64.full.bin").read_bytes()
    image = bytearray(b"\xff" * 8192)
    image[BOOT:len(raw)] = raw[BOOT:]
    return CPU(image=bytes(image))


def context(cpu):
    cpu.r[28:30] = [0, 1]
    cpu.r[30:32] = [0, 1]


def receive_to_handshake_selection(cpu, payload, pid=DATA1, corrupt=False,
                                   token=0xE1):
    """Execute real DATA classification, stopping before ACK bit transmission.

    The payload and CRC represent the sampler's already-decoded SRAM output.
    Returning ACK means the actual PHY selected ACK, not that the transmitter
    or a physical host has observed it.
    """
    context(cpu)
    cpu.mem[0x0112] = 0  # receive buffer is available
    cpu.mem[0x0114] = token
    cpu.mem[0x0116] = pid
    cpu.mem[0x0117:0x0117 + len(payload)] = payload
    checksum = bytearray(crc16(payload))
    if corrupt:
        checksum[0] ^= 1
    cpu.mem[0x0117 + len(payload):0x0119 + len(payload)] = checksum
    cpu.r[19] = len(payload) + 3
    cpu.run_from("L1bf6", stop_at=["L1c4e"], count=100)
    return cpu.r[19]


def consume_out(cpu, length):
    context(cpu)
    cpu.r[24] = length
    cpu.run_from("block_accept_out", stop_at=["L1df8"],
                 count=2000, execute_ret=True)
    cpu.run_from("L1df8", stop_at=["L1dfc"], count=10)


def prepare_reply(cpu):
    context(cpu)
    cpu.run_from("L1dfc", stop_at=["L1e64"],
                 count=2000, execute_ret=True)


def queued_packet(cpu):
    length = cpu.mem[0x010F]
    assert 4 <= length <= 12
    # TX length includes the SYNC byte synthesized by the transmit engine.
    return length, bytes(cpu.mem[0x0101:0x0101 + length - 1])


def transmit_in_without_host_ack(cpu):
    context(cpu)
    cpu.mem[0x0112] = 0
    cpu.run_from("L1c14", stop_at=["L1be8"],
                 count=4000, execute_ret=True)
    # The actual NRZI transmit loop has run to its post-EOP return path.
    # No host ACK packet has been injected into the receive classifier.


def begin_erase(cpu):
    cpu.flash[0x0100:0x0140] = b"\x55" * 64
    cpu.set_setup(0x14, 0x0100, 0, 0, 0x40)
    cpu.run_from("block_erase_setup", stop_at=["L1df8"],
                 count=500, execute_ret=True)
    assert cpu.mem[MEM_STATE] == ST_FLASH_WAIT_PREP
    assert not cpu.spm_oplog


@pytest.mark.parametrize("length", range(1, 9))
def test_valid_out_duplicate_is_acked_without_second_application_copy(cpu, length):
    cpu.set_setup(0x11, 0, 16, 1, 0x40)
    cpu.run_from("block_write_setup", stop_at=["L1df8"],
                 count=500, execute_ret=True)
    payload = bytes(range(1, length + 1))
    assert receive_to_handshake_selection(cpu, payload) == ACK
    consume_out(cpu, length)
    assert cpu.mem[MEM_STATE] == ST_RECEIVE
    assert cpu.mem[MEM_INDEX] == length
    assert cpu.mem[MEM_REMAIN] == 16 - length
    assert cpu.mem[MEM_EXPECT_PID] == DATA0
    saved = bytes(cpu.mem[MEM_BUFFER:MEM_BUFFER + 64])
    assert saved[:length] == payload
    assert receive_to_handshake_selection(cpu, payload) == ACK
    consume_out(cpu, length)
    assert cpu.mem[MEM_INDEX] == length
    assert cpu.mem[MEM_REMAIN] == 16 - length
    assert cpu.mem[MEM_EXPECT_PID] == DATA0
    assert bytes(cpu.mem[MEM_BUFFER:MEM_BUFFER + 64]) == saved


def test_corrupt_out_does_not_change_application_buffer_or_progress(cpu):
    cpu.set_setup(0x11, 0, 16, 1, 0x40)
    cpu.run_from("block_write_setup", stop_at=["L1df8"],
                 count=500, execute_ret=True)
    before = bytes(cpu.mem[MEM_BUFFER:MEM_BUFFER + 64])
    receive_to_handshake_selection(cpu, b"12345678", corrupt=True)
    consume_out(cpu, 8)
    assert cpu.mem[MEM_INDEX] == 0
    assert cpu.mem[MEM_REMAIN] == 16
    assert cpu.mem[MEM_EXPECT_PID] == DATA1
    assert bytes(cpu.mem[MEM_BUFFER:MEM_BUFFER + 64]) == before


@pytest.mark.xfail(strict=True, raises=USBContractViolation,
                   reason="PHY selects ACK before checking DATA CRC")
def test_corrupt_out_packet_is_not_acknowledged(cpu):
    selected = receive_to_handshake_selection(cpu, b"12345678", corrupt=True)
    require_contract(selected != ACK, "Invalid DATA CRC selected the ACK handshake")


@pytest.mark.xfail(strict=True, raises=USBContractViolation,
                   reason="SETUP dispatch has no CRC validation gate")
def test_corrupt_setup_does_not_start_eeprom_receive(cpu):
    payload = bytes([0x40, 0x11, 0, 0, 1, 0, 1, 0])
    receive_to_handshake_selection(cpu, payload, pid=DATA0,
                                   corrupt=True, token=0x2D)
    context(cpu)
    cpu.run_from("L1d9c", stop_at=["L1df8"],
                 count=1000, execute_ret=True)
    require_contract(cpu.mem[MEM_STATE] == ST_IDLE,
                     "CRC-invalid SETUP started the EEPROM receive operation")


@pytest.mark.xfail(strict=True, raises=USBContractViolation,
                   reason="IN packet buffer/PID advance without host ACK")
def test_lost_in_ack_replays_same_pid_length_and_payload(cpu):
    cpu.flash[0x0100:0x0110] = bytes(range(16))
    cpu.mem[0x0100] = 16
    cpu.mem[0x0101] = DATA0
    cpu.mem[0x0110:0x0112] = bytes([0, 1])
    prepare_reply(cpu)
    first = queued_packet(cpu)
    assert first[1][0] == DATA1
    transmit_in_without_host_ack(cpu)
    prepare_reply(cpu)
    require_contract(queued_packet(cpu) == first,
                     "Lost IN ACK advanced the DATA PID or payload")


@pytest.mark.xfail(strict=True, raises=USBContractViolation,
                   reason="SPM readiness checks TX disposal, not status ACK")
def test_lost_status_ack_cannot_start_flash_erase(cpu):
    begin_erase(cpu)
    prepare_reply(cpu)
    assert cpu.mem[MEM_STATE] == ST_SPM_WAIT_SENT
    assert queued_packet(cpu)[0] == 4
    transmit_in_without_host_ack(cpu)
    context(cpu)
    cpu.run_from("block_spm_after_quiet", count=500, execute_ret=True)
    require_contract(not cpu.spm_oplog and
                     cpu.flash[0x0100:0x0140] == b"\x55" * 64,
                     "Flash erase started without the status-stage host ACK")


@pytest.mark.xfail(strict=True, raises=USBContractViolation,
                   reason="Any prepared reply can satisfy mutation status marker")
def test_get_status_data_packet_cannot_complete_prior_erase_status_stage(cpu):
    begin_erase(cpu)
    cpu.set_setup(0x12, 0, 8, 0, 0xC0)
    cpu.mem[0x0112] = 11
    cpu.mem[0x010D] = 0x2D
    context(cpu)
    cpu.run_from("L1d9c", stop_at=["L1e64"],
                 count=2000, execute_ret=True)
    require_contract(cpu.mem[MEM_STATE] != ST_SPM_WAIT_SENT,
                     "GET_STATUS DATA IN replaced the prior erase status stage")
