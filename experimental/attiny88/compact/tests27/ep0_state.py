#!/usr/bin/env python3
"""Check observable standard EP0 replies through actual candidate AVR opcodes.

Expected descriptor bytes, request effects, USB CRC16 and packet sequencing are
defined independently of the optimized dispatcher. This is a control-state and
packet-staging model; it does not certify electrical USB or retry/ACK behavior.
"""
from collections.abc import MutableMapping
from functools import lru_cache
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_candidate import checked_build
from test_read_previous import decode
from tests27 import avr_exec27 as avr_exec23

CONTEXT = 0x100
DATA0, DATA1, NAK = 0xC3, 0x4B, 0x5A
VERSIONS = {'NONE': 0x0300, 'ACTIVE_HIGH': 0x0301, 'ACTIVE_LOW': 0x0302}
DESCRIPTOR_KINDS = (0, 1, 2, 3, 7, 255)
CONFIGURATION_DESCRIPTOR = bytes((9, 2, 18, 0, 1, 1, 0, 0x80, 50,
                                  9, 4, 0, 0, 0, 0, 0, 0, 0))


class ContextView(MutableMapping):
    """Map Y-relative USB fields onto the executor's actual modeled SRAM bytes."""
    def __init__(self, memory):
        self.memory = memory

    def __getitem__(self, offset):
        return self.memory[CONTEXT + offset]

    def __setitem__(self, offset, value):
        self.memory[CONTEXT + offset] = value

    def __delitem__(self, offset):
        del self.memory[CONTEXT + offset]

    def __iter__(self):
        return (address - CONTEXT for address in self.memory
                if CONTEXT <= address < CONTEXT + 44)

    def __len__(self):
        return sum(1 for _ in self)


@lru_cache(maxsize=16)
def decoded_snapshot(path, timestamp, size):
    """Cache only a particular saved ELF, never an earlier build at the same path."""
    return decode(Path(path))


def cached_decode(path):
    path = Path(path)
    stat = path.stat()
    return decoded_snapshot(str(path), stat.st_mtime_ns, stat.st_size).copy()


def usb_crc(payload):
    """USB CRC16: reflected polynomial A001, initial FFFF, final complement."""
    accumulator = 0xFFFF
    for byte in payload:
        accumulator ^= byte
        for _ in range(8):
            accumulator = (accumulator >> 1) ^ (0xA001 if accumulator & 1 else 0)
    return ((~accumulator) & 0xFFFF).to_bytes(2, 'little')


def device_descriptor(mode):
    version = VERSIONS[mode]
    return bytes((18, 1, 0x10, 0x01, 0xFF, 0, 0, 8,
                  0xD0, 0x16, 0x53, 0x07, version & 255, version >> 8,
                  0, 0, 0, 1))


def initialize(artifact):
    with patch.object(avr_exec23, 'decode', cached_decode):
        machine = avr_exec23.AVRExec(artifact)
    machine.ram = ContextView(machine.data_memory)
    # This represents the completed startup clear of the 44-byte USB context.
    for offset in range(44):
        machine.ram[offset] = 0
    machine.r[29] = 1
    machine.r[21] = 0xA0
    machine.r[2] = 0xA5  # R2 is free; replies must not treat it as a memory source.
    machine.r[4:6] = [0x34, 0x12]
    end = min(8192, artifact['boot'] + len(artifact['body']))
    machine.flash[artifact['boot']:end] = artifact['body'][:end - artifact['boot']]
    machine.ram[12] = machine.ram[19] = 42  # PHY stores doubled addresses.
    return machine


def expected_reply(mode, request, descriptor, configuration):
    """The compact endpoint answers unsupported standard requests with no data."""
    if request == 0:
        return bytes(2)
    if request == 6:
        if descriptor == 1:
            return device_descriptor(mode)
        if descriptor == 2:
            return CONFIGURATION_DESCRIPTOR
    if request == 8:
        return bytes((configuration,))
    if request == 10:
        return bytes(1)
    return b''


def transfer(machine, mode, request, *, value=0, descriptor=0, length=18):
    """Run SETUP, then each prepared DATA packet, checking externally used state."""
    configuration, pending_address = machine.ram[21], machine.ram[12]
    cursor = machine.r[4:6]
    unused_r2 = machine.r[2]
    next_configuration = (value if request == 9 and descriptor == 0 and value < 2
                          else configuration)
    expected = expected_reply(mode, request, descriptor, configuration)[:length]
    # The preceding eight-byte packet leaves CRC at offsets10/11. Zero replies
    # must use the permanent zero pair16/17, never those stale CRC bytes.
    machine.ram.update({10: 0xA5, 11: 0x5A, 15: NAK, 18: 11, 13: 0x2D,
                        23: 0x80, 24: request, 25: value, 26: descriptor,
                        29: length & 255, 30: length >> 8})
    machine.steps.clear()
    assert machine.run('usb_control_process_received_packet',
                       stop=('usb_rx_release_buffer',), limit=220) == 'stop'
    assert machine.ram[0] == len(expected), (mode, request, descriptor, length, machine.ram[0])
    assert machine.ram[21] == next_configuration
    assert machine.ram[19] == ((value * 2) & 255 if request == 5 else pending_address)

    observed = bytearray()
    packets = []
    for packet_index in range(4):
        before = len(expected) - len(observed)
        machine.ram[15] = NAK  # The PHY consumed the previous staged packet.
        machine.steps.clear()
        assert machine.run('usb_rx_release_buffer',
                           stop=('bootloader_check_idle_timeout',), limit=1800) == 'stop'
        count = machine.ram[15] - 4
        assert count == min(before, 8), (mode, request, descriptor, length, count, before)
        payload = bytes(machine.data_memory[CONTEXT + 2 + i] for i in range(count))
        checksum = bytes(machine.data_memory[CONTEXT + 2 + count + i] for i in range(2))
        assert payload == expected[len(observed):len(observed) + count], (
            mode, request, descriptor, length, packet_index, payload, expected)
        assert checksum == usb_crc(payload), (mode, request, descriptor, length, checksum, usb_crc(payload))
        assert machine.ram[1] == (DATA1 if packet_index % 2 == 0 else DATA0), (
            mode, request, descriptor, length, packet_index, machine.ram[1])
        observed.extend(payload)
        remaining = len(expected) - len(observed)
        assert machine.ram[0] == (0xFF if count < 8 else remaining), (
            mode, request, descriptor, length, packet_index, machine.ram[0], remaining)
        assert machine.ram[16] == machine.ram[17] == 0
        assert machine.r[1] == 0 and machine.r[4:6] == cursor
        assert machine.r[2] == unused_r2
        packets.append((machine.ram[1], payload))
        if count < 8 or len(observed) >= length:
            break
    else:
        raise AssertionError('Standard reply exceeded four endpoint-zero packets')
    assert bytes(observed) == expected
    assert machine.ram[21] == next_configuration
    assert machine.ram[19] == ((value * 2) & 255 if request == 5 else pending_address)
    # Model the completed packet TX applying the pending doubled address.
    machine.ram[12] = machine.ram[19]
    return packets


def check_standard(artifact, mode):
    """Cover every standard bRequest independently of old scratch/register choices."""
    machine = initialize(artifact)
    count = 0
    for request in range(256):
        for descriptor in DESCRIPTOR_KINDS:
            for configuration, value in ((0, 1), (1, 0), (1, 255)):
                machine.ram[21] = configuration
                machine.ram[19] = 43
                transfer(machine, mode, request, value=value, descriptor=descriptor)
                count += 1
    assert count == 4608
    print('PASS', mode, count,
          'standard SETUP/TX payload/state cases; independent descriptors/CRC, persistent zero context')


def check_configuration_words(artifact):
    """Reject every malformed complete wValue from both valid prior states."""
    machine = initialize(artifact)
    count = 0
    for value in range(65536):
        for previous in (0, 1):
            machine.ram.update({18: 11, 13: 0x2D, 23: 0, 24: 9,
                                25: value & 255, 26: value >> 8, 29: 0, 30: 0,
                                21: previous})
            machine.steps.clear()
            machine.run('usb_control_process_received_packet',
                        stop=('usb_rx_release_buffer',), limit=220)
            assert machine.ram[21] == (value if value < 2 else previous), (value, previous)
            assert machine.ram[0] == 0 and machine.r[1] == 0
            assert machine.r[2] == 0xA5
            count += 1
    print('PASS', artifact['mode'], count,
          'complete SET_CONFIGURATION words and both valid prior states; malformed values preserve state')


def check_transfers(artifact):
    """Exercise stateful configuration and all descriptor wLength values0..256."""
    mode = artifact['mode']
    machine = initialize(artifact)
    count = 0
    for descriptor in (1, 2):
        for length in range(257):
            packets = transfer(machine, mode, 6, descriptor=descriptor, length=length)
            if length >= 18:
                assert [len(payload) for _pid, payload in packets] == [8, 8, 2]
                assert [pid for pid, _payload in packets] == [DATA1, DATA0, DATA1]
            count += 1
    for configuration in (1, 0, 255, 19, 100, 0, 1, 255):
        for length in (0, 1, 2, 7, 8, 9, 18, 255, 256):
            transfer(machine, mode, 9, value=configuration, length=length)
            transfer(machine, mode, 6, descriptor=1, length=18)
            transfer(machine, mode, 8, length=length)
            transfer(machine, mode, 0, length=length)
            transfer(machine, mode, 10, length=length)
            count += 5
    for address in (0, 1, 19, 100, 127, 0):
        transfer(machine, mode, 5, value=address, length=0)
        transfer(machine, mode, 6, descriptor=2, length=256)
        assert machine.ram[19] == address * 2
        count += 2
    print('PASS', mode, count,
          'stateful EP0 transfers, descriptor wLength0..256, DATA1/DATA0, remaining lengths and stale CRC isolation')


def test():
    for mode, boot in (('NONE', 0x1B80), ('ACTIVE_HIGH', 0x1B40), ('ACTIVE_LOW', 0x1B40)):
        artifact = checked_build(mode, boot)
        check_standard(artifact, mode)
        check_transfers(artifact)
        check_configuration_words(artifact)
    print('PASS 13824 standard request combinations and complete EP0 packet/state regressions')


if __name__ == '__main__':
    test()
