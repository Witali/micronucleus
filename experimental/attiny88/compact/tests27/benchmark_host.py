#!/usr/bin/env python3
"""Offline guard/completion checks; this module never imports USB or touches hardware."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hardware.benchmark30 import Compact, ScratchLegacy, PAGES, base


class Device:
    bcdDevice = 0x0391

    def __init__(self):
        self.cursor = 0
        self.eeprom = bytearray(64)
        self.pending = None
        self.busy_reads = 0
        self.calls = []

    def ctrl_transfer(self, kind, request, value, index, data, timeout):
        self.calls.append((kind, request, value, index, data))
        if kind == 0x40 and request == 1:
            if self.pending is None:
                self.cursor = index
            return 0
        if kind == 0x40 and request == 3:
            assert self.pending is None
            assert self.cursor & 0x8000
            address = self.cursor & 0x7fff
            self.pending = (address, value.to_bytes(2, 'little') + index.to_bytes(2, 'little'))
            self.cursor += 4
            self.busy_reads = 2
            return 0
        if kind == 0xc0 and request == 0xb0:
            if self.pending is not None:
                self.busy_reads -= 1
                if self.busy_reads == 0:
                    address, block = self.pending
                    self.eeprom[address:address + 4] = block
                    self.pending = None
                return b''
            address = self.cursor & 0x7fff
            self.cursor += 8
            return bytes(self.eeprom[address:address + 8])
        raise AssertionError('Unexpected control transfer')


class HostGuards(unittest.TestCase):
    def test_flash_bounds_before_usb(self):
        device = Device()
        adapter = Compact(device, writable=True)
        adapter.connect()
        for address in (-64, 0, 0x80, 0x201, 0xfc0, 0x1000, 0x1480, 0x1ac0, 0x1b00, 0xffc0):
            with self.assertRaises(base.BenchmarkError):
                adapter.erase_page(address)
            with self.assertRaises(base.BenchmarkError):
                adapter.write_page(address, bytes(64))
        self.assertEqual(device.calls, [])
        for address in PAGES:
            adapter.require_scratch(address, 64)

    def test_readonly_rejects_mutation(self):
        device = Device()
        device.bcdDevice = 0x0390
        adapter = Compact(device)
        adapter.connect()
        with self.assertRaises(base.BenchmarkError):
            adapter.erase_page(0x200)
        with self.assertRaises(base.BenchmarkError):
            adapter.write_eeprom(bytes(64))
        self.assertEqual(device.calls, [])

    def test_eeprom_reselects_after_busy_and_confirms(self):
        device = Device()
        adapter = Compact(device, writable=True)
        adapter.connect()
        pattern = bytes(range(64))
        adapter.write_eeprom(pattern)
        self.assertEqual(bytes(device.eeprom), pattern)
        self.assertIsNone(device.pending)
        self.assertEqual(adapter.read(1, 0, 64), pattern)
        writes = [call for call in device.calls if call[:2] == (0x40, 3)]
        self.assertEqual(len(writes), 16)

    def test_only_guarded_revision_can_write(self):
        device = Device()
        device.bcdDevice = 0x0390
        with self.assertRaises(base.BenchmarkError):
            Compact(device, writable=True).connect()
        device.bcdDevice = 0x0300
        with self.assertRaises(base.BenchmarkError):
            Compact(device).connect()
        device.bcdDevice = 0x0391
        Compact(device).connect()  # Repeat snapshots remain read-only.

    def test_legacy_bounds_do_not_change_priming(self):
        adapter = ScratchLegacy(Device())
        adapter.connected = True
        for address in (0, 0x80, 0xfc0, 0x1000, 0x1480, 0x1ac0, 0x1b00):
            with self.assertRaises(base.BenchmarkError):
                adapter.require_scratch(address, 64)
        adapter.require_scratch(0x200, 64)


if __name__ == '__main__':
    unittest.main()
