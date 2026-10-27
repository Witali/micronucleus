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
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_build import build
from build_candidate import SOURCE, checked_build
from audit_phy27 import audit_candidate
from test_read_previous import decode
from tests import avr_exec, avr_exec23
from test_standard import disasm_q, execute
from tests26 import test26_nvm as nvm
from tests26 import test26_cursor_opcodes as cursor
from tests26 import test26_combined_erase as erase
from tests26 import test26_tx_bytes as tx


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
    old_ops, new_ops = disasm_q(old['obj']), disasm_q(artifact['obj'])
    branches, states = audit_candidate(old, artifact, '')
    print('PASS PHY: 9-cycle RX setup,', branches, 'branch targets,', states,
          'flag-liveness states; three branch operands corrected')
    count = 0
    for request in range(256):
        for descriptor in (0, 1, 2, 3, 7, 255):
            for config, value in ((0, 0), (1, 19), (255, 100)):
                left = execute(old, old_ops, request, descriptor, config, value)
                right = execute(artifact, new_ops, request, descriptor, config, value)
                assert left == right, (mode, request, descriptor, config, value, left, right)
                count += 1
    start = artifact['symbols']['USB_handler'] - artifact['boot'] - 18
    descriptor = artifact['body'][start:start + 18]
    expected = {'NONE': 0x0560, 'ACTIVE_HIGH': 0x0561, 'ACTIVE_LOW': 0x0562}[mode]
    assert int.from_bytes(descriptor[12:14], 'little') == expected
    print('PASS', mode, count, 'standard request dispatch cases; distinct candidate descriptor')


def check_control_reply(artifact):
    """Run SETUP through packet staging, rather than stopping at reply helpers."""
    for request, value, descriptor, length, config, expected in (
        (0, 0, 0, 2, 0, b'\0\0'),
        (8, 0, 0, 1, 7, b'\7'),
        (10, 0, 0, 1, 0, b'\0'),
        (6, 0, 1, 8, 0, artifact['body'][20:28]),
        (6, 0, 2, 9, 0, artifact['body'][2:10]),
    ):
        machine = avr_exec23.AVRExec(artifact)
        machine.ram = ContextView(machine.data_memory)
        machine.r[29] = 1
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
    for mode in ('NONE', 'ACTIVE_HIGH', 'ACTIVE_LOW'):
        boot = 0x1B40 if mode == 'NONE' else 0x1B00
        artifact = checked_build(mode, boot)
        assert artifact['size'] <= 8192 - boot
        check_standard(artifact, mode)
        nvm.test_setaddr(artifact)
        nvm.test_erase_and_commit(artifact)
        nvm.test_flash_write_data(artifact)
        nvm.test_eeprom_queue(artifact)
        check_invalid_vendor(artifact)
        check_control_reply(artifact)
    cursor.SRC = SOURCE
    cursor.test()
    erase.SRC = SOURCE
    erase.test()
    tx.SRC = SOURCE
    tx.test()
    print('PASS modular candidate: standard USB, Flash/EEPROM, cursor and TX opcode contracts')


if __name__ == '__main__':
    test()
