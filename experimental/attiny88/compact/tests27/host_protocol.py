#!/usr/bin/env python3
"""Offline v3.0 byte-selector client checks; the device is an independent mock.

These tests exercise planner, transport state and readback, not electrical USB,
physical EEPROM timing, transaction retries or boot-page power-loss behavior.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import compact_programmer as previous
from host import compact_programmer27 as h


class ByteUSBMock:
    """Model byte selectors, a page buffer and separately completed EEPROM writes."""
    idVendor, idProduct = h.USB_VID, h.USB_PID

    def __init__(self, version=h.USB_BCD):
        self.bcdDevice = version
        self.boot_at = h.USB_PROFILES[version][1]
        self.flash = bytearray(b'\xff' * self.boot_at + b'\xa5' * (h.FLASH_SIZE - self.boot_at))
        self.eeprom = bytearray(b'\xff' * h.EEPROM_SIZE)
        self.mode, self.cursor = 'flash', 0
        self.buffer = {}
        self.queued_eeprom = None
        self.calls = []
        self.ran = False

    def finish_eeprom(self, _delay=None):
        if self.queued_eeprom is not None:
            address, data = self.queued_eeprom
            self.eeprom[address:address + 4] = data
            self.cursor = address + 4
            self.queued_eeprom = None

    def ctrl_transfer(self, request_type, request, value, index, data, timeout=5000):
        self.calls.append((request_type, request, value, index))
        if request in (h.REQ_SET_ADDRESS, h.REQ_SELECT_ERASE):
            assert request_type == 0x40 and value == 0 and data == []
            if self.queued_eeprom is not None:
                return []  # MCU rejects selection while an earlier byte queue is active.
            self.mode = 'eeprom' if index & 0x8000 else 'flash'
            self.cursor = index & 0x7FFF  # Independently decode the documented wire format.
            assert self.cursor % 4 == 0
            assert self.cursor < (64 if self.mode == 'eeprom' else 8192)
            if self.mode == 'flash':
                self.buffer.clear()
            if request == h.REQ_SELECT_ERASE:
                assert self.mode == 'flash' and self.cursor % 64 == 0 and self.cursor < self.boot_at
                self.flash[self.cursor:self.cursor + 64] = b'\xff' * 64
            return []
        if request == h.REQ_WRITE4:
            assert request_type == 0x40 and data == []
            payload = value.to_bytes(2, 'little') + index.to_bytes(2, 'little')
            if self.mode == 'eeprom':
                assert self.queued_eeprom is None and 0 <= self.cursor <= 60
                self.queued_eeprom = (self.cursor, payload)
            else:
                assert 0 <= self.cursor <= self.boot_at - 4
                self.buffer.update({self.cursor + offset: byte for offset, byte in enumerate(payload)})
                self.cursor += 4
                if self.cursor % 64 == 0:
                    page = self.cursor - 64
                    assert page < self.boot_at
                    self.flash[page:page + 64] = bytes(self.buffer.get(page + offset, 0xFF) for offset in range(64))
                    self.buffer.clear()
            return []
        if request == h.REQ_READ8:
            assert request_type == 0xC0 and value == index == 0 and data == 8
            if self.queued_eeprom is not None:
                return []
            memory = self.eeprom if self.mode == 'eeprom' else self.flash
            assert 0 <= self.cursor <= len(memory) - 8
            result = memory[self.cursor:self.cursor + 8]
            self.cursor += 8
            return result
        if request == h.REQ_RUN:
            assert request_type == 0x40 and value == index == 0 and data == []
            self.ran = True
            return []
        raise AssertionError(('Unexpected USB operation', request_type, request))


def rejected(call, error=ValueError):
    try:
        call()
    except error:
        return
    raise AssertionError('Operation unexpectedly accepted')


def test_selectors():
    for eeprom, limit in ((False, 8192), (True, 64)):
        device = ByteUSBMock()
        transport = h.USBTransport(device)
        for address in range(0, limit, 4):
            selector = address | (0x8000 if eeprom else 0)
            assert h.encode_addr(address, eeprom=eeprom) == selector
            assert h.decode_addr(selector) == ('eeprom' if eeprom else 'flash', address)
            transport.set_address(address, eeprom=eeprom)
            assert device.calls[-1][3] == selector
        for address in (-4, -1, 1, 2, 3, limit, limit + 4):
            before = len(device.calls)
            rejected(lambda: transport.set_address(address, eeprom=eeprom))
            assert len(device.calls) == before
    for selector in (-1, 0x10000, 1, 0x2000, 0x7FFF, 0x8001, 0x8040, 0x8100, 0xFFFF):
        rejected(lambda: h.decode_addr(selector))
    print('PASS all 2064 valid byte selectors; invalid ranges/alignment/EEPROM aliases rejected before USB')


def test_transport():
    device = ByteUSBMock()
    device.flash[:] = bytes((index * 71) & 255 for index in range(8192))
    device.eeprom[:] = bytes((index * 17) & 255 for index in range(64))
    transport = h.USBTransport(device)
    for address in range(0, 256, 8):
        assert transport.read8(address) == device.flash[address:address + 8]
    assert sum(call[1] == h.REQ_SET_ADDRESS for call in device.calls) == 1
    assert all(call[2:] == (0, 0) for call in device.calls if call[1] == h.REQ_READ8)
    for address in (0, 8):
        assert transport.read8(address, eeprom=True) == device.eeprom[address:address + 8]
    assert sum(call[1] == h.REQ_SET_ADDRESS for call in device.calls) == 2
    assert transport.read8(0) == device.flash[:8]
    assert sum(call[1] == h.REQ_SET_ADDRESS for call in device.calls) == 3

    # A data timeout can occur after a request reached the MCU. Discard the cache.
    original = device.ctrl_transfer
    def fail(request_type, request, *args, **kwargs):
        if request == h.REQ_READ8:
            raise IOError('Injected lost USB reply')
        return original(request_type, request, *args, **kwargs)
    with patch.object(device, 'ctrl_transfer', fail):
        rejected(lambda: transport.read8(8), IOError)
    assert transport._cursor is None
    transport.read8(8)
    assert device.calls[-2][1:] == (h.REQ_SET_ADDRESS, 0, 8)

    with patch.object(device, 'ctrl_transfer', side_effect=IOError('Injected uncertain SELECT')):
        rejected(lambda: transport.set_address(64), IOError)
    assert transport._cursor is None
    rejected(lambda: transport.write4(b'1234'))
    transport.set_address(0, erase=True)
    selects = sum(call[1] in (h.REQ_SET_ADDRESS, h.REQ_SELECT_ERASE) for call in device.calls)
    for address in range(0, 64, 4):
        transport.write4(bytes(range(address, address + 4)))
    assert device.flash[:64] == bytes(range(64)) and transport._cursor == ('flash', 64)
    assert sum(call[1] in (h.REQ_SET_ADDRESS, h.REQ_SELECT_ERASE) for call in device.calls) == selects
    with patch.object(device, 'ctrl_transfer', side_effect=IOError('Injected uncertain WRITE4')):
        rejected(lambda: transport.write4(b'1234'), IOError)
    assert transport._cursor is None
    rejected(lambda: transport.write4(b'1234'))

    transport.set_address(0, eeprom=True)
    transport.write4(b'abcd')
    rejected(lambda: transport.read8(0, eeprom=True), IOError)
    assert transport._cursor is None
    device.finish_eeprom()
    assert transport.read8(0, eeprom=True)[:4] == b'abcd'
    assert device.calls[-2][1:] == (h.REQ_SET_ADDRESS, 0, 0x8000)

    for action in (
        lambda: transport.set_address(0, eeprom=True, erase=True),
        lambda: transport.set_address(4, erase=True),
        lambda: transport.set_address(transport.boot_at, erase=True),
        lambda: transport.write4(b'bad'),
        lambda: transport.read8(60, eeprom=True),
        lambda: transport.read8(transport.app_bytes - 4),
    ):
        before = len(device.calls)
        rejected(action)
        assert len(device.calls) == before
    transport.set_address(transport.boot_at)
    before = len(device.calls)
    rejected(lambda: transport.write4(b'1234'))
    assert len(device.calls) == before
    transport.set_address(60, eeprom=True)
    transport.write4(b'last')
    before = len(device.calls)
    rejected(lambda: transport.write4(b'over'))
    assert len(device.calls) == before
    device.finish_eeprom()

    with patch.object(device, 'ctrl_transfer', side_effect=IOError('Injected lost RUN acknowledgment')):
        rejected(transport.run, IOError)
    assert transport._cursor is None
    transport.run()
    assert device.ran and transport._cursor is None
    print('PASS READ8/WRITE4 automatic cursor, busy/short/error invalidation, seek recovery and write boundaries')


def test_vectors_and_programming():
    for version, (_name, boot, _code) in h.USB_PROFILES.items():
        device = ByteUSBMock(version)
        transport = h.USBTransport(device)
        prepared = h.pack_application({0: 0x80, 1: 0xC0, 0x102: 0xAB, boot - 5: 0x91}, boot_at=boot)
        assert prepared.reset_target_word == 0x81
        marker_pc = (boot - 4) // 2
        displacement = prepared.postscript_reset_word & 0xFFF
        if displacement & 0x800:
            displacement -= 4096
        assert (marker_pc + 1 + displacement) & 0xFFF == 0x81
        assert prepared.image[-2:] == b'\xff\xff'
        with patch.object(h.time, 'sleep', side_effect=device.finish_eeprom):
            h.program_application(transport, prepared)
            for address in range(0, 64, 4):
                h.program_eeprom_block(transport, address, bytes(((address + i) * 7) & 255 for i in range(4)))
        assert device.flash[:boot] == prepared.image
        assert device.flash[boot:] == b'\xa5' * (8192 - boot)
        assert device.eeprom == bytes((index * 7) & 255 for index in range(64))
        assert device.calls[0][1:] == (h.REQ_SELECT_ERASE, 0, boot - 64)
        assert sum(call[1] == h.REQ_SELECT_ERASE for call in device.calls) == boot // 64
        for size in (1, 4, 7, 8, 9, 63, boot - 4):
            assert h.read_flash(transport, size) == prepared.image[:size]
        assert h.read_eeprom(transport) == device.eeprom
        assert transport.read8_firmware(8184) == b'\xa5' * 8

        image = bytes((index * 13) & 255 for index in range(64))
        before = len(device.calls)
        with patch.object(h.time, 'sleep', side_effect=device.finish_eeprom):
            h.program_eeprom_stream(transport, image)
        commands = [call[1] for call in device.calls[before:]]
        assert commands.count(h.REQ_WRITE4) == 16 and commands.count(h.REQ_READ8) == 8
        assert commands.count(h.REQ_SET_ADDRESS) == 2 and device.eeprom == image
        rejected(lambda: h.program_eeprom_stream(transport, image, dwell=0.049))

        other_boot = 0x1B40 if boot == 0x1B80 else 0x1B80
        mismatch = h.pack_application({0: 2, 1: 0xC0}, boot_at=other_boot)
        before = len(device.calls)
        rejected(lambda: h.program_application(transport, mismatch))
        assert len(device.calls) == before
        for invalid in ({boot - 4: 1}, {boot: 1}, {0: 0xFF, 1: 0xFF}):
            rejected(lambda: h.pack_application(invalid, boot_at=boot))
        absolute = h.pack_application({0: 0x0C, 1: 0x94, 2: 0x34, 3: 1}, boot_at=boot)
        assert absolute.reset_target_word == 0x134
        text = h.image_to_hex(prepared.image)
        assert h.parse_intel_hex(text) == dict(enumerate(prepared.image))
        transport.run()
        assert device.ran
        print('PASS full mock Flash/EEPROM programming/readback, RESET/postscript, stream and RUN', hex(version), hex(boot))


def test_identification_and_cli():
    device = ByteUSBMock()
    for version in (0, 0x0550, 0x0563, 0xFFFF):
        device.bcdDevice = version
        rejected(lambda: h.USBTransport(device))
        assert not device.calls
    device.bcdDevice = h.USB_BCD
    device.idVendor = 0
    rejected(lambda: h.USBTransport(device))
    assert not device.calls
    for argv in (['missing.hex', '--execute'], ['--execute', '--i-have-isp-recovery']):
        with redirect_stderr(io.StringIO()):
            rejected(lambda: h.main(argv), SystemExit)

    temporary_root = ROOT / 'build'
    temporary_root.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='compact-pass27-host-', dir=temporary_root) as temporary:
        root = Path(temporary)
        assert root.resolve().is_relative_to(temporary_root.resolve())
        application, output = root / 'application.hex', root / 'prepared.hex'
        application.write_text(h.image_to_hex(b'\x80\xc0\x34\x12'), encoding='ascii')
        with redirect_stdout(io.StringIO()):
            h.main([str(application), '--out', str(output)])
        assert len(h.parse_intel_hex(output.read_text())) == h.BOOT_AT

        # PyUSB is replaced completely: even the CLI execute path has no device access.
        device = ByteUSBMock(0x0301)
        usb, core = ModuleType('usb'), ModuleType('usb.core')
        core.find = lambda **_kwargs: device
        usb.core = core
        with patch.dict(sys.modules, {'usb': usb, 'usb.core': core}), redirect_stdout(io.StringIO()):
            h.main(['--identify'])
            assert not device.calls
            with patch.object(h.time, 'sleep', side_effect=device.finish_eeprom) as pauses:
                h.main([str(application), '--execute', '--i-have-isp-recovery', '--boot-at', '0x1C00',
                        '--flash-delay-ms', '11.5'])
                assert pauses.call_args_list and all(call.args == (0.0115,) for call in pauses.call_args_list)
        # A manual offline placement cannot override a known hardware descriptor.
        assert device.calls[0][3] == device.boot_at - 64
        assert device.flash[device.boot_at:] == b'\xa5' * (8192 - device.boot_at)
    print('PASS descriptor-only identification, unknown profiles, offline CLI and both mocked execution gates')


def test_flash_delay_policy():
    device = ByteUSBMock()
    transport = h.USBTransport(device)
    prepared = h.pack_application({0: 0x80, 1: 0xC0})
    with patch.object(h.time, 'sleep', side_effect=device.finish_eeprom) as pauses:
        h.program_application(transport, prepared)
    assert h.DEFAULT_FLASH_DELAY_MS == 7
    assert pauses.call_args_list and all(call.args == (0.007,) for call in pauses.call_args_list)
    for invalid in (0, -1, float('nan'), float('inf')):
        before = len(device.calls)
        rejected(lambda: h.program_application(transport, prepared, delay=invalid))
        assert len(device.calls) == before
        with redirect_stderr(io.StringIO()):
            rejected(lambda: h.main(['--identify', '--flash-delay-ms', str(invalid)]), SystemExit)
    print('PASS default7ms, custom11.5ms CLI and invalid waits rejected before USB')


def test():
    original_profiles = deepcopy(previous.USB_PROFILES)
    original_encoding = previous.encode_addr(60, eeprom=True)
    test_selectors()
    test_transport()
    test_vectors_and_programming()
    test_identification_and_cli()
    test_flash_delay_policy()
    assert previous.USB_PROFILES == original_profiles
    assert previous.encode_addr(60, eeprom=True) == original_encoding == 0x800F
    assert h.encode_addr(60, eeprom=True) == 0x803C
    print('PASS v3.0 client and complete offline host scenarios; Pass26 globals remain unchanged')


if __name__ == '__main__':
    test()
