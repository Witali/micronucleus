#!/usr/bin/env python3
"""Exercise candidate opcodes against preserved contracts and independent CRC.

This is software-only validation, not USB electrical or full retry admission.
Pass26 fixtures retain their source/profile choices; only this runner selects
the modular candidate. Decode caching makes exhaustive cases practical while
keying the cache to the actual ELF's modification time and size.
"""
from collections.abc import MutableMapping
from functools import lru_cache
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_build import build
from build_candidate import SOURCE, checked_build, CANDIDATE_SAVINGS
from audit_phy27 import audit_candidate
from test_read_previous import decode
from tests27 import avr_exec27 as avr_exec
from tests27 import avr_exec27 as avr_exec23


@lru_cache(maxsize=32)
def decoded_snapshot(path, timestamp, size):
    return decode(Path(path))


def cached_decode(path):
    stat = Path(path).stat()
    return decoded_snapshot(str(path), stat.st_mtime_ns, stat.st_size).copy()


avr_exec.decode = cached_decode
avr_exec23.decode = cached_decode


class ContextView(MutableMapping):
    """Alias the executor's Y-relative context onto real modeled SRAM bytes."""
    def __init__(self, memory):
        self.memory = memory

    def __getitem__(self, offset):
        return self.memory[0x100 + offset]

    def __setitem__(self, offset, value):
        self.memory[0x100 + offset] = value

    def __delitem__(self, offset):
        del self.memory[0x100 + offset]

    def __iter__(self):
        return (address - 0x100 for address in self.memory if 0x100 <= address < 0x12C)

    def __len__(self):
        return sum(1 for _ in self)


def usb_crc(payload):
    crc = 0xFFFF
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return ((~crc) & 0xFFFF).to_bytes(2, 'little')


def check_standard(artifact, mode):
    old = build(ROOT / 'variants/strict_usb_optimized/micronucleus_t88_pass26.S',
                mode, artifact['boot'])
    branches, states = audit_candidate(old, artifact, '')
    check_phy_audit_mutations(old, artifact)
    print('PASS PHY: unchanged RX schedule,', branches, 'branch targets,', states,
          'flag-liveness states; independent TX/return contracts')
    # Compare observable USB data/state, not intentionally removed scratch stores.
    from tests27.ep0_state import (check_standard as standard, check_transfers,
                                  check_configuration_words)
    standard(artifact, mode)
    check_transfers(artifact)
    check_configuration_words(artifact)
    start = artifact['symbols']['USB_handler'] - artifact['boot'] - 18
    descriptor = artifact['body'][start:start + 18]
    expected = {'NONE': 0x0300, 'ACTIVE_HIGH': 0x0301, 'ACTIVE_LOW': 0x0302}[mode]
    assert int.from_bytes(descriptor[12:14], 'little') == expected
    print('PASS', mode, 'distinct candidate descriptor')


def check_phy_audit_mutations(reference, artifact):
    """Ensure the timing/ABI audit rejects broken replacements, not just passes."""
    mutations = (
        ('entry context copy', 'USB_handler', 0, lambda word: word ^ 1),
        ('return context copy', 'usb_return_context', 0, lambda word: word ^ 1),
        ('seed call target', 'usb_rx_delay_complete', 4, lambda word: word + 1),
        ('RX length address', 'usb_rx_delay_complete', 14, lambda word: word ^ 1),
        ('DATA flag', 'usb_rx_handle_data', 12, lambda word: word & ~7),
        ('IN flag', 'usb_rx_handle_in', 2, lambda word: word & ~7),
        ('TX rate', 'usb_tx_begin_byte', 0, lambda word: 0xE365),
        ('J delay', 'usb_tx_finish_eop', 16, lambda word: 0),
        ('released port bit', 'usb_tx_finish_eop', 24, lambda word: word ^ 3),
    )
    for name, symbol, offset, transform in mutations:
        raw = bytearray(artifact['body'])
        at = artifact['symbols'][symbol] + offset - artifact['boot']
        raw[at:at + 2] = transform(int.from_bytes(raw[at:at + 2], 'little')).to_bytes(2, 'little')
        try:
            audit_candidate(reference, dict(artifact, body=bytes(raw)), '')
        except (AssertionError, KeyError):
            continue
        raise AssertionError('PHY audit accepted mutation: ' + name)
    try:
        audit_candidate(reference, artifact, 'U missing_operand')
    except AssertionError:
        pass
    else:
        raise AssertionError('PHY audit accepted unresolved symbol')
    print('PASS', artifact['mode'], len(mutations) + 1, 'negative PHY audit cases')


def check_tx_bytes(artifact):
    """Independent payload/CRC and persistent reply-cursor checks at real opcodes."""
    rng = random.Random(0x2757)
    count = 0
    for source, offset in (('flash', 0x142), ('flash', 0x1AFE),
                           ('eeprom', 16), ('eeprom', 56)):
        for length in range(9):
            if source == 'eeprom' and offset + length > 64:
                continue
            for fill in (0, 255, 0x55, 0xAA, None):
                payload = bytes(fill if fill is not None else rng.randrange(256)
                                for _ in range(length))
                machine = avr_exec23.AVRExec(artifact)
                machine.r[29] = 1
                machine.r[24] = length
                machine.r[0] = machine.r[25] = 0
                machine.r[21] = 0xA0
                machine.r[8] = 0xA5  # The former source register is now free.
                pointer = offset | (0x8000 if source == 'eeprom' else 0)
                machine.r[14:16] = [pointer & 255, pointer >> 8]
                for index, value in enumerate(payload):
                    if source == 'flash':
                        machine.flash[offset + index] = value
                    elif source == 'eeprom':
                        machine.eeprom[offset + index] = value
                machine.run('usb_tx_initialize_payload_crc',
                            stop=('usb_tx_publish_packet_length',), limit=1500)
                actual = bytes(machine.data_memory[0x102 + i] for i in range(length + 2))
                assert actual == payload + usb_crc(payload), (source, offset, payload, actual)
                assert machine.r[14] | (machine.r[15] << 8) == pointer + length
                assert machine.r[8] == 0xA5
                count += 1
    print('PASS', count, 'actual-opcode payload/independent CRC/register-cursor cases')


def check_control_reply(artifact):
    """Run SETUP through packet staging, rather than stopping at reply helpers."""
    for request, value, descriptor, length, config, expected in (
        (0, 0, 0, 2, 0, b'\0\0'),
        (8, 0, 0, 1, 1, b'\1'),
        (10, 0, 0, 1, 0, b'\0'),
        (6, 0, 1, 8, 0, artifact['body'][20:28]),
        (6, 0, 2, 9, 0, artifact['body'][2:10]),
    ):
        machine = avr_exec23.AVRExec(artifact)
        machine.ram = ContextView(machine.data_memory)
        machine.r[29] = 1
        machine.r[21] = 0xA0
        machine.flash[:min(8192, artifact['boot'] + len(artifact['body']))] = (
            bytes(artifact['boot']) + artifact['body'])[:8192]
        machine.ram.update({18: 11, 13: 0x2D, 23: 0x80, 24: request,
                            25: value, 26: descriptor, 29: length, 30: 0,
                            21: config})
        machine.run('usb_control_process_received_packet',
                    stop=('bootloader_check_idle_timeout',), limit=1500)
        payload = bytes(machine.data_memory[0x102 + i] for i in range(len(expected)))
        checksum = bytes(machine.data_memory[0x102 + len(expected) + i] for i in range(2))
        assert payload == expected, (request, descriptor, payload, expected)
        assert checksum == usb_crc(expected), (request, descriptor, checksum, usb_crc(expected))
        assert machine.ram[15] == len(expected) + 4
    print('PASS complete standard SETUP-to-TX path and independent USB CRC16')


def check_invalid_vendor(artifact):
    for request in (0, 5, 6, 0x7F, 0xFF):
        machine = avr_exec.AVRExec(artifact)
        machine.r[25] = request
        machine.r[29] = 1
        machine.ram.update({27: 0x10, 28: 0})
        machine.run('bootloader_check_set_flash_address', stop=('usb_reply_empty',))
        assert machine.r[3] == 0 and not machine.spms, request
    print('PASS unknown vendor opcodes cannot queue SPM or modify the page buffer')


def test():
    # Candidate selectors are exact bytes, so retain Pass26 fixtures unchanged
    # and exercise v3.0 with its own actual-opcode and host suites.
    from host import compact_programmer27 as host
    from tests27 import nvm_opcodes, host_protocol
    from tests27.startup_init import check_startup
    for mode, version in (('NONE', 0x0300), ('ACTIVE_HIGH', 0x0301), ('ACTIVE_LOW', 0x0302)):
        _name, boot, expected_size = host.USB_PROFILES[version]
        artifact = checked_build(mode, boot)
        assert artifact['size'] <= 8192 - boot
        candidate_size = expected_size - CANDIDATE_SAVINGS[mode]
        assert artifact['size'] == candidate_size, (mode, artifact['size'], candidate_size)
        check_startup(artifact)
        check_standard(artifact, mode)
        nvm_opcodes.check_nvm(artifact)
        check_invalid_vendor(artifact)
        check_control_reply(artifact)
        check_tx_bytes(artifact)
    host_protocol.test()
    print('PASS modular candidate: standard USB, Flash/EEPROM, cursor and TX opcode contracts')


if __name__ == '__main__':
    test()
