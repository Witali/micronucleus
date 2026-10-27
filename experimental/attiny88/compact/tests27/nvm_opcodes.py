#!/usr/bin/env python3
"""Run v5.6 NVM/cursor contracts through decoded, compiled AVR instructions.

The host owns selector geometry/alignment. The MCU must still reject every
page-changing SPM at or above BOOT_AT, including malformed EEPROM selectors.
These tests model instruction/IO effects, not Flash electrical timing or USB ACKs.
"""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_candidate import checked_build
from host import compact_programmer27 as host
from tests import avr_exec
from tests27.ep0_state import cached_decode, initialize


def new_machine(artifact):
    with patch.object(avr_exec, 'decode', cached_decode):
        machine = avr_exec.AVRExec(artifact)
    machine.r[29] = 1
    machine.r[9] = 0x4B
    machine.r[14:16] = [0xEF, 0xBE]
    return machine


def pointer(machine):
    return machine.r[4] | (machine.r[5] << 8)


def set_pointer(machine, address):
    machine.r[4:6] = [address & 255, address >> 8]


def preserve_usb_registers(machine):
    assert machine.r[9] == 0x4B and machine.r[14:16] == [0xEF, 0xBE]
    assert machine.r[1] == 0


def check_selectors(artifact):
    count = 0
    for eeprom, limit in ((False, 8192), (True, 64)):
        for address in range(0, limit, 4):
            for request in (1, 2):
                machine = new_machine(artifact)
                selector = address | (0x8000 if eeprom else 0)
                machine.r[25] = request
                machine.ram.update({27: selector & 255, 28: selector >> 8})
                machine.run('bootloader_check_set_flash_address', stop=('usb_reply_empty',))
                assert pointer(machine) == selector and machine.r[3] == request + 1
                # CTPB clears only the inactive page buffer, even for EEPROM.
                assert len(machine.spms) == 1 and machine.spms[0][0] == 0x11
                machine.spms.clear()
                machine.run('bootloader_dispatch_command', stop=('bootloader_clear_command',))
                should_erase = request == 2 and not eeprom and (address & ~63) < artifact['boot']
                assert bool(machine.spms) == should_erase
                if machine.spms:
                    assert machine.spms[0][:2] == (3, address & ~63)
                preserve_usb_registers(machine)
                count += 1
    # Every possible EEPROM high-byte class stays above the protected Flash
    # boundary. Low-byte classes exercise both sides of page alignment/carry.
    for high in range(0x80, 0x100):
        for low in (0, 63, 64, 127, 128, 191, 192, 255):
            machine = new_machine(artifact)
            machine.r[25] = 2
            machine.ram.update({27: low, 28: high})
            machine.run('bootloader_check_set_flash_address', stop=('usb_reply_empty',))
            assert machine.r[4:6] == [low, high] and machine.r[3] == 3
            assert [event[0] for event in machine.spms] == [0x11]
            machine.spms.clear()
            machine.run('bootloader_dispatch_command', stop=('bootloader_clear_command',))
            assert not machine.spms
            count += 1
    print('PASS', count, 'byte SELECT/erase cases, physical EEPROM aliases and final Flash guard')


def check_page_operations(artifact):
    count = 0
    for page in [*range(0, 8192, 64), 0xFFC0]:
        for operation in (3, 5):
            machine = new_machine(artifact)
            cursor = page if operation == 3 else (page + 64) & 0xFFFF
            set_pointer(machine, cursor)
            machine.r[3] = operation
            machine.run('bootloader_dispatch_command', stop=('bootloader_clear_command',))
            assert bool(machine.spms) == (page < artifact['boot']), (hex(page), operation, machine.spms)
            if machine.spms:
                assert machine.spms[0][:2] == (operation, page)
            preserve_usb_registers(machine)
            count += 1
    print('PASS', count, 'actual erase/page-commit operations across all Flash pages and cursor wrap')


def check_flash_write4(artifact):
    count = 0
    for address in range(0, 8192, 4):
        machine = new_machine(artifact)
        set_pointer(machine, address)
        machine.r[25] = 3
        data = bytes(((address * 7) ^ (offset * 0x63 + 0x91)) & 255 for offset in range(4))
        machine.ram.update(dict(zip((25, 26, 27, 28), data)))
        machine.run('bootloader_check_set_flash_address', stop=('usb_reply_empty',))
        assert machine.spms == [(1, address, int.from_bytes(data[:2], 'little')),
                                (1, address + 2, int.from_bytes(data[2:], 'little'))]
        assert pointer(machine) == address + 4
        assert machine.r[3] == (5 if (address + 4) % 64 == 0 else 0)
        assert machine.r[8] == 0
        preserve_usb_registers(machine)
        if machine.r[3] == 5:
            machine.spms.clear()
            machine.run('bootloader_dispatch_command', stop=('bootloader_clear_command',))
            page = address & ~63
            assert bool(machine.spms) == (page < artifact['boot'])
        count += 1
    print('PASS', count, 'aligned WRITE4 pairs, exact host words, cursor+4, R1 restoration and automatic commit')


def check_eeprom_write4(artifact):
    count = 0
    for address in range(256):
        machine = new_machine(artifact)
        set_pointer(machine, 0x8000 | address)
        machine.r[25] = 3
        data = bytes((0x73, 0xAB, 0x42, 0x19))
        machine.ram.update(dict(zip((25, 26, 27, 28), data)))
        machine.run('bootloader_check_set_flash_address', stop=('usb_reply_empty',))
        assert not machine.spms and not machine.io_events
        assert pointer(machine) == 0x8000 | address
        if address > 60:
            # Rejected requests may overwrite an inactive data queue, but must
            # not activate it or perform any EEPROM/Flash operation.
            assert machine.r[8] == 0
            continue
        assert machine.r[8] == 4 and machine.r[10:14] == list(data)
        for offset, byte in enumerate(data):
            machine.io[0x1F] = 2
            registers, events = machine.r[:], len(machine.io_events)
            machine.run('ee_write_step')
            assert machine.r == registers and len(machine.io_events) == events
            machine.io[0x1F] = 0
            machine.run('ee_write_step')
            assert machine.io_events[-4:] == [('out', 0x21, address + offset),
                                              ('out', 0x20, byte),
                                              ('sbi', 0x1F, 2), ('sbi', 0x1F, 1)]
            assert machine.r[8] == 3 - offset and machine.r[4] == address + offset + 1
            preserve_usb_registers(machine)
        assert machine.r[8] == 0
        machine.io[0x1F] = 0
        before = len(machine.io_events)
        machine.run('ee_write_step')
        assert len(machine.io_events) == before
        count += 1
    print('PASS', count, 'EEPROM start positions, 195 rejected low-byte bounds and asynchronous busy/data sequencing')


def check_busy_and_invalid_requests(artifact):
    count = 0
    for pending in (0, 1, 4):
        for eecr in (0, 2):
            machine = new_machine(artifact)
            set_pointer(machine, 0x800C)
            machine.r[8], machine.io[0x1F] = pending, eecr
            machine.run('ee_write_step')
            starts_byte = pending != 0 and eecr == 0
            assert bool(machine.io_events) == starts_byte
            assert machine.r[8] == pending - int(starts_byte)
            assert pointer(machine) == 0x800C + int(starts_byte)
            preserve_usb_registers(machine)
            count += 1
    for pending, eecr in ((1, 0), (4, 0), (0, 1), (0, 2), (0, 4), (0, 8), (0, 0x30), (0, 255)):
        for request in (1, 2, 3, 4):
            machine = new_machine(artifact)
            set_pointer(machine, 0x800C)
            machine.r[8], machine.r[25] = pending, request
            machine.io[0x1F] = eecr
            machine.ram.update({25: 0x11, 26: 0x22, 27: 0, 28: 0x80})
            registers = machine.r[:]
            machine.run('bootloader_check_set_flash_address', stop=('usb_reply_empty',))
            assert pointer(machine) == 0x800C and machine.r[8:14] == registers[8:14]
            assert not machine.spms and not machine.io_events and machine.r[3] == 0
            count += 1
    for request in range(256):
        if request in (1, 2, 3, 4, 0xB0):
            continue
        machine = new_machine(artifact)
        set_pointer(machine, 0x140)
        machine.r[25] = request
        machine.ram.update({27: 0, 28: 0x80})
        machine.run('bootloader_check_set_flash_address', stop=('usb_reply_empty',))
        assert pointer(machine) == 0x140 and machine.r[3] == 0 and not machine.spms
        count += 1
    print('PASS', count, 'busy/unknown requests cannot clear a page buffer, queue SPM or overwrite an active EEPROM queue')


def check_vendor_setup(artifact):
    """Include the real SETUP loader/dispatcher, not only isolated NVM entries."""
    count = 0
    for request in (1, 2, 3, 4, 0xB0, 0, 5, 255):
        for eeprom in (False, True):
            machine = initialize(artifact)
            address = 12 if eeprom else 0x104
            selector = address | (0x8000 if eeprom else 0)
            set_pointer(machine, selector)
            data = bytes((0x73, 0xAB, 0x42, 0x19))
            fields = {18: 11, 13: 0x2D, 23: 0xC0 if request == 0xB0 else 0x40,
                      24: request, 25: data[0], 26: data[1], 27: data[2], 28: data[3],
                      29: 8 if request == 0xB0 else 0, 30: 0}
            if request in (1, 2):
                fields[27], fields[28] = selector & 255, selector >> 8
            machine.ram.update(fields)
            machine.run('usb_control_process_received_packet', stop=('usb_rx_release_buffer',), limit=300)
            if request in (1, 2):
                assert pointer(machine) == selector and machine.r[3] == request + 1
                assert [event[0] for event in machine.spms] == [0x11]
            elif request == 3:
                if eeprom:
                    assert machine.r[8] == 4 and machine.r[10:14] == list(data)
                    assert not machine.spms
                else:
                    assert [event[:2] for event in machine.spms] == [(1, address), (1, address + 2)]
                    assert pointer(machine) == address + 4
            elif request == 4:
                assert machine.r[3] == 4 and not machine.spms
            elif request == 0xB0:
                assert pointer(machine) == selector + 8
                assert machine.r[14] | (machine.r[15] << 8) == address
                assert machine.r[2] == (0x80 if eeprom else 0) and machine.ram[0] == 8
            else:
                assert pointer(machine) == selector and machine.r[3] == 0 and not machine.spms
            assert machine.r[1] == 0
            count += 1
    print('PASS', count, 'complete vendor SETUP dispatch cases with exact byte selectors and payload fields')


def check_cursor(artifact, *, exhaustive=True):
    """Prove cursor arithmetic at actual ADD/ADC opcodes, including all carries."""
    machine = new_machine(artifact)
    values = range(65536) if exhaustive else (0, 0xF8, 0xFC, 0xFF, 0x1FF8, 0x8038, 0xFFF8, 0xFFFF)
    count = 0
    for cursor in values:
        set_pointer(machine, cursor)
        machine.r[18:20] = [cursor & 255, cursor >> 8]
        machine.C = cursor & 1  # ADD must define carry independently of entry flags.
        machine.steps.clear()
        machine.run('memory_read_advance', stop=('usb_reply_set_pointer',), limit=8)
        result = (cursor + 8) & 0xFFFF
        assert pointer(machine) == result and machine.r[18:20] == [cursor & 255, cursor >> 8]
        assert machine.r[24] == 8 and machine.r[1] == 0
        assert machine.C == int(cursor + 8 > 0xFFFF)
        # ADC Z describes its byte result; the reply path redefines flags before
        # using them, so it need not match ADIW's old whole-word Z behavior.
        assert machine.Z == int(result >> 8 == 0)
        count += 1
    for eeprom, starts in ((False, range(0, 8185, 4)), (True, range(0, 57, 4))):
        for address in starts:
            machine = new_machine(artifact)
            selector = address | (0x8000 if eeprom else 0)
            set_pointer(machine, selector)
            machine.run('memory_read', stop=('usb_reply_set_pointer', 'ee_empty'))
            assert machine.pc == artifact['symbols']['usb_reply_set_pointer']
            assert machine.r[18] | (machine.r[19] << 8) == address
            assert pointer(machine) == selector + 8
            assert machine.r[24] == 8 and machine.r[2] == (0x80 if eeprom else 0)
    for pending, eecr in ((1, 0), (0, 1), (0, 2), (0, 4), (4, 2)):
        machine = new_machine(artifact)
        set_pointer(machine, 0x8018)
        machine.r[8], machine.io[0x1F] = pending, eecr
        machine.run('memory_read', stop=('usb_reply_set_pointer', 'ee_empty'))
        assert machine.pc == artifact['symbols']['ee_empty'] and pointer(machine) == 0x8018
    print('PASS', count, 'cursor increments, all valid Flash/EEPROM READ8 starts and busy preservation')


def check_nvm(artifact):
    check_selectors(artifact)
    check_page_operations(artifact)
    check_flash_write4(artifact)
    check_eeprom_write4(artifact)
    check_busy_and_invalid_requests(artifact)
    check_vendor_setup(artifact)
    check_cursor(artifact)


def test():
    for mode, version in (('NONE', 0x0560), ('ACTIVE_HIGH', 0x0561), ('ACTIVE_LOW', 0x0562)):
        _name, boot, _size = host.USB_PROFILES[version]
        check_nvm(checked_build(mode, boot))
    print('PASS v5.6 byte-cursor NVM/host-bound policy and MCU Flash protection')


if __name__ == '__main__':
    test()
