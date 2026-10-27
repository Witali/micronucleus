#!/usr/bin/env python3
"""Experimental compact Pass27 client, protocol v5.6 with byte-address SELECT.

The host validates memory geometry and alignment before sending a selector.
Offline image planning needs no USB packages. Physical programming requires
both --execute and --i-have-isp-recovery; these candidates lack hardware admission.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import time

if __package__:
    from . import compact_programmer as base
else:
    import compact_programmer as base

USB_VID, USB_PID, USB_BCD = base.USB_VID, base.USB_PID, 0x0560
# Provisional research profiles: update sizes only after the matching build audit.
USB_PROFILES = {
    0x0560: ('Pass27 / no LED; 18 pages', 0x1B80, 1100),
    0x0561: ('Pass27 / LED active-high; 19 pages', 0x1B40, 1118),
    0x0562: ('Pass27 / LED active-low; 19 pages', 0x1B40, 1116),
}
FLASH_SIZE, EEPROM_SIZE, PAGE_BYTES = base.FLASH_SIZE, base.EEPROM_SIZE, base.PAGE_BYTES
BLOCK_BYTES, READ_BYTES = base.BLOCK_BYTES, base.READ_BYTES
ADDRESS_MASK, EEPROM_SELECT = 0x7FFF, 0x8000
BOOT_AT = USB_PROFILES[USB_BCD][1]
POSTSCRIPT_AT = APP_BYTES = BOOT_AT - 4
REQ_SET_ADDRESS, REQ_SELECT_ERASE = base.REQ_SET_ADDRESS, base.REQ_SELECT_ERASE
REQ_WRITE4, REQ_RUN, REQ_READ8 = base.REQ_WRITE4, base.REQ_RUN, base.REQ_READ8

# These helpers depend only on image bytes or the supplied transport's geometry.
# Reuse their validation and readback without changing the Pass26 module's globals.
PatchedImage = base.PatchedImage
parse_intel_hex = base.parse_intel_hex
image_from_file = base.image_from_file
decode_app_reset = base.decode_app_reset
record = base.record
image_to_hex = base.image_to_hex
plan_flash_pages = base.plan_flash_pages
verify_application_page = base.verify_application_page
program_application = base.program_application
read_eeprom = base.read_eeprom
program_eeprom_block = base.program_eeprom_block
program_eeprom_stream = base.program_eeprom_stream


def encode_addr(byte_address: int, *, eeprom: bool = False) -> int:
    """Encode a validated byte cursor; no four-byte-block scaling goes on wire."""
    limit = EEPROM_SIZE if eeprom else FLASH_SIZE
    if not 0 <= byte_address < limit or byte_address % BLOCK_BYTES:
        raise ValueError('Memory address out of bounds or not 4-byte-aligned')
    return (EEPROM_SELECT if eeprom else 0) | byte_address


def decode_addr(field: int) -> tuple[str, int]:
    """Reject aliases that the compact MCU intentionally leaves to host validation."""
    if not 0 <= field <= 0xFFFF:
        raise ValueError('Address field is 16-bit')
    eeprom = bool(field & EEPROM_SELECT)
    address = field & ADDRESS_MASK
    encode_addr(address, eeprom=eeprom)
    return ('eeprom' if eeprom else 'flash', address)


def pack_application(raw: dict[int, int], *, boot_at: int = BOOT_AT) -> PatchedImage:
    """Prepare RESET and postscript for the selected Pass27 Flash boundary."""
    return base.pack_application(raw, boot_at=boot_at)


class USBTransport(base.USBTransport):
    """Reuse READ8/WRITE4 cursor handling with a separate profile/selector contract."""

    def __init__(self, dev):
        if (int(dev.idVendor), int(dev.idProduct)) != (USB_VID, USB_PID):
            raise ValueError('Wrong USB VID/PID')
        version = int(dev.bcdDevice)
        if version not in USB_PROFILES:
            raise ValueError(f'Unknown Pass27 variant bcdDevice={version:#06x}; no commands sent')
        self.dev = dev
        self.profile, self.boot_at, self.code_bytes = USB_PROFILES[version]
        self.app_bytes = self.boot_at - 4
        self._cursor = None

    def set_address(self, byte_address: int, *, eeprom=False, erase=False):
        """Validate geometry locally, then SELECT the exact byte cursor on the AVR."""
        if eeprom and erase:
            raise ValueError('ERASE applies only to Flash')
        field = encode_addr(byte_address, eeprom=eeprom)
        if erase and (byte_address % PAGE_BYTES or byte_address >= self.boot_at):
            raise ValueError('SELECT+ERASE requires an aligned application Flash page')
        try:
            self.dev.ctrl_transfer(0x40, REQ_SELECT_ERASE if erase else REQ_SET_ADDRESS,
                                   0, field, [], timeout=5000)
        except Exception:
            # An uncertain SELECT may already have moved the hardware cursor.
            self._cursor = None
            raise
        self._cursor = ('eeprom' if eeprom else 'flash', byte_address)

    def write4(self, data: bytes):
        """Prevent host writes into the loader or beyond EEPROM before any USB IO."""
        if len(data) != BLOCK_BYTES:
            raise ValueError('Exactly four data bytes required')
        if self._cursor is None:
            raise ValueError('WRITE4 requires initial SELECT')
        kind, address = self._cursor
        limit = EEPROM_SIZE if kind == 'eeprom' else self.boot_at
        if address < 0 or address % BLOCK_BYTES or address + BLOCK_BYTES > limit:
            raise ValueError('WRITE4 cursor lies outside writable memory')
        # The inherited method advances only on completion and invalidates on USB errors.
        super().write4(data)

    def run(self):
        """RUN ends the bootloader session even when its USB acknowledgment is lost."""
        try:
            super().run()
        finally:
            self._cursor = None


def read_flash(transport: USBTransport, size: int | None = None) -> bytes:
    """Return the requested application bytes, including short initial fragments."""
    if size is None:
        size = transport.app_bytes
    if not 0 < size <= transport.app_bytes:
        raise ValueError('Invalid Flash read length')
    if size < READ_BYTES:
        return transport.read8(0)[:size]
    result = bytearray()
    while len(result) + READ_BYTES <= size:
        result.extend(transport.read8(len(result)))
    if len(result) < size:
        # Round the overlapping final window UP to a legal four-byte boundary:
        # rounding down can leave the requested final one to three bytes unread.
        start = ((size - READ_BYTES + BLOCK_BYTES - 1) // BLOCK_BYTES) * BLOCK_BYTES
        tail = transport.read8(start)
        offset = len(result) - start
        result.extend(tail[offset:offset + size - len(result)])
    return bytes(result)


def main(argv=None):
    """Keep offline preparation separate from explicitly requested hardware access."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', type=Path, nargs='?', help='Application HEX/BIN; optional with --identify')
    parser.add_argument('--out', type=Path, help='Write prepared HEX offline')
    parser.add_argument('--boot-at', type=lambda value: int(value, 0), default=BOOT_AT,
                        help='Offline placement only; hardware geometry comes from its descriptor')
    parser.add_argument('--identify', action='store_true', help='Read only standard device descriptor fields')
    parser.add_argument('--execute', action='store_true', help='Write the identified experimental device')
    parser.add_argument('--i-have-isp-recovery', action='store_true', help='Confirm ISP recovery and complete backups')
    args = parser.parse_args(argv)
    if args.application is None and not args.identify:
        parser.error('An application is required except for --identify')
    if args.execute and args.application is None:
        parser.error('--execute requires an application BIN/HEX')
    if args.execute and not args.i_have_isp_recovery:
        parser.error('--execute requires --i-have-isp-recovery')

    transport = None
    if args.identify or args.execute:
        try:
            import usb.core
        except ImportError as error:
            raise SystemExit('PyUSB and a libusb backend are required') from error
        device = usb.core.find(idVendor=USB_VID, idProduct=USB_PID)
        if device is None:
            raise SystemExit('No compatible USB device detected')
        try:
            transport = USBTransport(device)
        except ValueError as error:
            raise SystemExit(f'Unknown device; no vendor commands issued: {error}') from error
        print(f'USB DESCRIPTOR: {transport.profile}, bcdDevice={int(device.bcdDevice):#06x}, '
              f'boot_at={transport.boot_at:#06x}, code={transport.code_bytes} B, READ8 requests=0')

    if args.application is None:
        return
    boot_at = transport.boot_at if transport is not None else args.boot_at
    prepared = pack_application(image_from_file(args.application), boot_at=boot_at)
    print(f'Application: {boot_at - 4} bytes, BOOT_AT={boot_at:#06x}, postscript={boot_at - 4:#06x}')
    print(f'Reset target: {prepared.reset_target_word * 2:#06x}, '
          f'boot RJMP={prepared.boot_reset_word:#06x}, postscript RJMP={prepared.postscript_reset_word:#06x}')
    if args.out:
        args.out.write_text(image_to_hex(prepared.image), encoding='ascii', newline='\n')
        print('Wrote prepared image:', args.out)
    if args.execute:
        assert transport is not None
        program_application(transport, prepared)
        print('Experimental write/readback complete, including postscript. Hardware unverified.')
    elif not args.identify:
        print('Dry run only. No USB device was modified.')


if __name__ == '__main__':
    main()
