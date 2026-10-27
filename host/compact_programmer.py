#!/usr/bin/env python3
"""Experimental ATtiny88 Micronucleus compact PC-side planner and programmer.

USB protocol v5.5 uses an automatic unified READ8/WRITE4 cursor; incompatible with older clients.
Read-only offline image preparation and protocol mock tests are safe. Actual
USB programming needs a deliberate --execute flag and an ISP recovery plan.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from pathlib import Path
import time

USB_VID, USB_PID, USB_BCD = 0x16D0, 0x0753, 0x0550
# bcdDevice: full build variant; all Pass23 variants reserve 20 Flash pages.
USB_PROFILES = {
    0x0550: ('Pass26 / no LED; 19 pages', 0x1B40, 1206),
    0x0551: ('Pass26 / LED active-high', 0x1B00, 1220),
    0x0552: ('Pass26 / LED active-low', 0x1B00, 1218),
}
FLASH_SIZE, EEPROM_SIZE, PAGE_BYTES = 8192, 64, 64
BOOT_AT = 0x1B40  # 19 pages for no-LED; LED modes remain at 0x1B00
POSTSCRIPT_AT = BOOT_AT - 4
APP_BYTES = POSTSCRIPT_AT
BLOCK_BYTES, READ_BYTES = 4, 8
BLOCK_INDEX_MASK, EEPROM_SELECT = 0x7FFF, 0x8000
REQ_SET_ADDRESS, REQ_SELECT_ERASE, REQ_WRITE4, REQ_RUN, REQ_READ8 = 1, 2, 3, 4, 0xB0


@dataclass(frozen=True)
class PatchedImage:
    image: bytes  # entire application sector: [0, BOOT_AT), postscript included
    reset_target_word: int
    boot_reset_word: int
    postscript_reset_word: int


def encode_addr(byte_address: int, *, eeprom: bool = False) -> int:
    limit = EEPROM_SIZE if eeprom else FLASH_SIZE
    if byte_address < 0 or byte_address >= limit or byte_address % BLOCK_BYTES:
        raise ValueError('Memory address out of bounds or not 4-byte-aligned')
    block = byte_address // BLOCK_BYTES
    if block > BLOCK_INDEX_MASK:
        raise ValueError('15-bit block index exhausted')
    return (EEPROM_SELECT if eeprom else 0) | block


def decode_addr(field: int) -> tuple[str, int]:
    if not 0 <= field <= 0xFFFF:
        raise ValueError('Address field is 16-bit')
    return ('eeprom' if field & EEPROM_SELECT else 'flash', (field & BLOCK_INDEX_MASK) * BLOCK_BYTES)


def parse_intel_hex(text: str) -> dict[int, int]:
    out: dict[int, int] = {}
    offset = 0
    finished = False
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if finished or not line.startswith(':'):
            raise ValueError(f'Invalid Intel HEX record at line {number}')
        try:
            record = bytes.fromhex(line[1:])
        except ValueError as e:
            raise ValueError(f'Bad hexadecimal record at line {number}') from e
        if len(record) < 5 or len(record) != 5 + record[0] or sum(record) & 0xff:
            raise ValueError(f'Invalid length/checksum at line {number}')
        n, lo, hi, typ = record[:4]
        address = lo * 256 + hi
        payload = record[4:4+n]
        if typ == 0:
            for j, byte in enumerate(payload):
                absolute = offset + address + j
                if absolute in out and out[absolute] != byte:
                    raise ValueError(f'Conflicting byte at {absolute:#x}')
                out[absolute] = byte
        elif typ == 1:
            if n != 0:
                raise ValueError('Invalid end record')
            finished = True
        elif typ == 2:
            if n != 2:
                raise ValueError('Invalid segment record')
            offset = int.from_bytes(payload, 'big') << 4
        elif typ == 4:
            if n != 2:
                raise ValueError('Invalid linear offset record')
            offset = int.from_bytes(payload, 'big') << 16
        elif typ in (3, 5):
            # Start address records contain host metadata, not Flash bytes.
            continue
        else:
            raise ValueError(f'Unsupported HEX record type {typ}')
    if not finished:
        raise ValueError('Missing Intel HEX EOF')
    return out


def image_from_file(path: Path) -> dict[int, int]:
    if path.suffix.lower() in ('.hex', '.ihex'):
        return parse_intel_hex(path.read_text(encoding='ascii'))
    if path.suffix.lower() == '.bin':
        data = path.read_bytes()
        return dict(enumerate(data))
    raise ValueError('Expected .hex/.ihex or .bin application')


def decode_app_reset(image: bytes) -> int:
    """Return the AVR word address of the original app entry point.

    The tiny88 has a 12-bit (4096-word) PC, so RJMP wraps modulo 4096.
    A 4-byte absolute JMP is also accepted for this AVR family.
    """
    word0 = int.from_bytes(image[:2], 'little')
    word1 = int.from_bytes(image[2:4], 'little')
    if word0 == 0x940C:
        target = word1
    elif (word0 & 0xF000) == 0xC000:
        rel = word0 & 0x0FFF
        if rel & 0x0800:
            rel -= 4096
        target = (1 + rel) & 0x0FFF
    else:
        raise ValueError(f'Unsupported application RESET instruction {word0:#06x}; expected RJMP/JMP')
    if not 0 <= target * 2 < len(image)-4:
        raise ValueError(f'Application RESET target {target*2:#06x} lies outside the application')
    return target


def pack_application(raw: dict[int, int], *, boot_at: int = BOOT_AT) -> PatchedImage:
    if boot_at % PAGE_BYTES or not (PAGE_BYTES <= boot_at < FLASH_SIZE):
        raise ValueError('Invalid bootloader placement; must be a 64-byte Flash boundary')
    app_size = boot_at - 4
    if any((addr < 0 or addr >= app_size) for addr in raw):
        raise ValueError('Application includes protected postscript or bootloader bytes')
    page = bytearray([0xff] * boot_at)
    for adr, val in raw.items():
        if not 0 <= val <= 255:
            raise ValueError('Each Flash data byte must be in 0..255')
        page[adr] = val
    target = decode_app_reset(page)
    boot_reset = 0xC000 | ((boot_at // 2 - 1) & 0x0FFF)
    last_pc = (boot_at - 4) // 2
    app_reset = 0xC000 | ((target - last_pc - 1) & 0x0FFF)
    page[:2] = boot_reset.to_bytes(2, 'little')
    page[boot_at-4:boot_at-2] = app_reset.to_bytes(2, 'little')
    return PatchedImage(bytes(page), target, boot_reset, app_reset)


class USBTransport:
    def __init__(self, dev):
        if (int(dev.idVendor), int(dev.idProduct)) != (USB_VID, USB_PID):
            raise ValueError('Wrong USB VID/PID')
        version = int(dev.bcdDevice)
        if version not in USB_PROFILES:
            raise ValueError(f'Unknown Micronucleus variant bcdDevice={version:#06x}; no commands sent')
        self.dev = dev
        self.profile, self.boot_at, self.code_bytes = USB_PROFILES[version]
        self.app_bytes = self.boot_at - 4
        # Next byte address after a successful SELECT, READ8 or WRITE4.
        # The MCU keeps this cursor in r4:r5; no redundant USB SELECT.
        self._cursor = None  # tuple(memory_name, next_byte_address)

    def set_address(self, byte_address: int, *, eeprom=False, erase=False):
        # 0x02 is a combined SELECT+ERASE operation; standalone ERASE no longer exists.
        if eeprom and erase:
            raise ValueError('ERASE applies only to Flash; EEPROM overwrites are automatic')
        field = encode_addr(byte_address, eeprom=eeprom)
        # Page erase always takes an aligned 64-byte Flash page.
        # The MCU no longer silently rounds an unaligned SET_ADDRESS request.
        if erase and byte_address % PAGE_BYTES:
            raise ValueError('SELECT+ERASE requires a page-aligned Flash address')
        self.dev.ctrl_transfer(0x40, REQ_SELECT_ERASE if erase else REQ_SET_ADDRESS,
                               0, field, [], timeout=5000)
        self._cursor = ('eeprom' if eeprom else 'flash', byte_address)

    def _read8_at(self, byte_address: int, *, eeprom: bool, raw_flash: bool = False) -> bytes:
        limit = EEPROM_SIZE if eeprom else (FLASH_SIZE if raw_flash else self.app_bytes)
        if byte_address < 0 or byte_address % BLOCK_BYTES or byte_address + READ_BYTES > limit:
            raise ValueError('READ8: unaligned or out-of-range byte address')
        expected = ('eeprom' if eeprom else 'flash', byte_address)
        if self._cursor != expected:
            self.set_address(byte_address, eeprom=eeprom)
        try:
            # v5.5: READ8 ignores wValue/wIndex; the AVR address is persistent.
            # Advance only on confirmed host-side completion, otherwise force SELECT.
            result = bytes(self.dev.ctrl_transfer(0xC0, REQ_READ8, 0, 0, READ_BYTES, timeout=5000))
        except Exception:
            self._cursor = None
            raise
        if len(result) != READ_BYTES:
            self._cursor = None
            raise IOError('Device returned a short READ8 reply (EEPROM busy/USB error)')
        self._cursor = (expected[0], byte_address + READ_BYTES)
        return result

    def read8(self, byte_address: int, *, eeprom=False) -> bytes:
        return self._read8_at(byte_address, eeprom=eeprom)

    def read8_firmware(self, byte_address: int) -> bytes:
        """Read all Flash including loader; standard descriptor identifies the layout."""
        return self._read8_at(byte_address, eeprom=False, raw_flash=True)

    def write4(self, data: bytes):
        if len(data) != BLOCK_BYTES:
            raise ValueError('Exactly four data bytes required')
        if self._cursor is None:
            raise ValueError('WRITE4 requires initial SELECT')
        try:
            self.dev.ctrl_transfer(0x40, REQ_WRITE4,
                                  int.from_bytes(data[:2], 'little'),
                                  int.from_bytes(data[2:], 'little'), [], timeout=5000)
        except Exception:
            self._cursor = None
            raise
        kind, addr = self._cursor
        self._cursor = (kind, addr + BLOCK_BYTES)

    def run(self):
        self.dev.ctrl_transfer(0x40, REQ_RUN, 0, 0, [], timeout=5000)


def read_flash(transport: USBTransport, size: int | None = None) -> bytes:
    if size is None:
        size=transport.app_bytes
    if not 0 < size <= transport.app_bytes:
        raise ValueError('Invalid Flash read length')
    result = bytearray()
    address = 0
    while address + 8 <= size:
        result.extend(transport.read8(address))
        address += 8
    if address < size:
        # Non-eight-byte tail: overlap the last block. Never read postscript.
        start = size - 8
        start -= start % 4
        result.extend(transport.read8(start)[address-start:address-start+size-address])
    return bytes(result)


def read_eeprom(transport: USBTransport) -> bytes:
    return b''.join(transport.read8(a, eeprom=True) for a in range(0, EEPROM_SIZE, 8))


def verify_application_page(transport: USBTransport, page: int, expected: bytes):
    if len(expected) != PAGE_BYTES or page % PAGE_BYTES:
        raise ValueError('Invalid application page')
    if page + PAGE_BYTES < transport.boot_at:
        actual = b''.join(transport.read8(page+j) for j in range(0, PAGE_BYTES, READ_BYTES))
        if actual != expected:
            raise IOError(f'Flash page {page:#x} readback mismatch')
    elif page + PAGE_BYTES == transport.boot_at:
        # v5.2 READ8 can also verify all four postscript bytes.
        actual = b''.join(transport.read8_firmware(page+j) for j in range(0, PAGE_BYTES, READ_BYTES))
        if actual != expected:
            raise IOError('Last page including postscript failed READ8 verification')
    else:
        raise ValueError('Cannot verify outside application pages')


def plan_flash_pages(image: PatchedImage) -> list[tuple[int, bytes]]:
    boot_at=len(image.image)
    assert boot_at % PAGE_BYTES==0 and PAGE_BYTES <=boot_at<FLASH_SIZE
    pages = [(a,image.image[a:a+PAGE_BYTES]) for a in range(0, boot_at, PAGE_BYTES)]
    assert pages[-1][0] == boot_at-PAGE_BYTES
    # First erase the previous postscript, to disable starting an old app.
    # All other writes come next; the activation marker in the final page is last.
    return pages[:-1] + pages[-1:]


def program_application(transport: USBTransport, patched: PatchedImage, *, delay: float = 0.015):
    if len(patched.image) != transport.boot_at:
        raise ValueError('Unsafe programming: application layout differs from identified loader')
    pages=plan_flash_pages(patched)
    last_page = pages[-1][0]
    transport.set_address(last_page, erase=True)
    time.sleep(delay)
    for page_start,data in pages:
        if page_start == last_page:
            # The last page was erased first; reselect it after all other pages.
            transport.set_address(last_page)
        else:
            # Exactly one USB request selects and queues erase for this page.
            transport.set_address(page_start, erase=True)
            time.sleep(delay)
        for i in range(0,PAGE_BYTES,BLOCK_BYTES):
            transport.write4(data[i:i+BLOCK_BYTES])
        time.sleep(delay)
        verify_application_page(transport,page_start,data)
    # The v5.5 READ8 also verifies the postscript. A power outage during
    # page-zero RESET erase/write can still destroy boot availability.


def program_eeprom_block(transport: USBTransport, address: int, data4: bytes, *, max_polls: int = 30):
    if len(data4)!=4 or address % 4 or not 0<=address<=EEPROM_SIZE-4:
        raise ValueError('EEPROM: writes require aligned four-byte blocks')
    transport.set_address(address, eeprom=True)
    transport.write4(data4)
    base = (address // 8)*8
    for _ in range(max_polls):
        time.sleep(0.004)
        try:
            readback=transport.read8(base, eeprom=True)
        except IOError:
            continue
        if readback[address-base:address-base+4] == data4:
            # The MCU silently ignores SELECT while a byte-write is pending.
            # Select and read again after the first successful, nonbusy read;
            # this rejects a stale pointer that happened to return identical data.
            transport.set_address(base, eeprom=True)
            try:
                confirm = transport.read8(base, eeprom=True)
            except IOError:
                continue
            if confirm[address-base:address-base+4] == data4:
                return
    raise TimeoutError('EEPROM block did not verify; do not repeat automatically')


def program_eeprom_stream(transport: USBTransport, image: bytes, *, dwell: float = 0.050) -> None:
    """Optional 4-byte-block EEPROM stream: one SELECT, then 16 WRITE4s.

    The AVR writes each byte asynchronously. Do not send the next WRITE4 while
    the preceding four-byte queue is active. The inter-block dwell is a host-
    controlled heuristic, NOT a USB busy acknowledgment or datasheet-proven
    maximum time. A complete post-write readback is mandatory. This method is
    experimental until physical timing tests establish an adequate dwell.
    """
    if len(image) != EEPROM_SIZE:
        raise ValueError('Whole EEPROM image must be exactly 64 bytes')
    if dwell < 0.050:
        raise ValueError('Experimental streaming mode requires >=50ms per four bytes')
    transport.set_address(0, eeprom=True)
    for start in range(0, EEPROM_SIZE, BLOCK_BYTES):
        transport.write4(image[start:start + BLOCK_BYTES])
        time.sleep(dwell)
    # Force a seek at verification start. READ8 advances the SAME MCU cursor.
    actual = read_eeprom(transport)
    if actual != image:
        raise IOError('EEPROM stream readback mismatch; do not blindly retry')



def record(addr: int, data: bytes = b'', typ: int = 0) -> str:
    hdr=bytes((len(data), (addr>>8)&255, addr&255, typ))
    rec=hdr+data
    return ':'+(rec+bytes(((-sum(rec))&255,))).hex().upper()


def image_to_hex(image: bytes) -> str:
    lines=[record(a,image[a:a+16]) for a in range(0,len(image),16)]
    lines.append(record(0,b'',1))
    return '\n'.join(lines)+'\n'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('application',type=Path,nargs='?',help='Application HEX/BIN; optional with --identify')
    ap.add_argument('--out',type=Path,help='Write patched HEX offline (safe)')
    ap.add_argument('--boot-at',type=lambda x:int(x,0),default=BOOT_AT,
                    help='Only for offline --out; auto-selected from USB device descriptor on hardware')
    ap.add_argument('--identify',action='store_true',help='Read-only identification using only standard USB descriptors')
    ap.add_argument('--execute',action='store_true',help='DANGEROUS: Flash-write the identified board')
    ap.add_argument('--i-have-isp-recovery',action='store_true',help='Confirm ISP access and complete backups')
    ns=ap.parse_args()
    if ns.application is None and not ns.identify:
        ap.error('An application is required except for --identify')
    if ns.execute and ns.application is None:
        ap.error('--execute requires an application BIN/HEX')
    if ns.execute and not ns.i_have_isp_recovery:
        ap.error('--execute requires --i-have-isp-recovery')
    programmer=None
    identity=None
    if ns.identify or ns.execute:
        try:
            import usb.core
        except ImportError as e:
            raise SystemExit('PyUSB and a libusb backend are required') from e
        dev=usb.core.find(idVendor=USB_VID,idProduct=USB_PID)
        if dev is None:
            raise SystemExit('No compatible USB device detected')
        try:
            programmer=USBTransport(dev)
        except ValueError as e:
            raise SystemExit(f'Unknown device; no vendor commands issued: {e}') from e
        identity=programmer
        print(f'USB DESCRIPTOR: {programmer.profile}, bcdDevice={int(dev.bcdDevice):#06x}, '
              f'boot_at={programmer.boot_at:#06x}, code={programmer.code_bytes} B, '
              f'READ8 requests=0')
    if ns.application is not None:
        boot_at=identity.boot_at if identity else ns.boot_at
        patch=pack_application(image_from_file(ns.application),boot_at=boot_at)
        print(f'Application: {boot_at-4} bytes, BOOT_AT={boot_at:#06x}, postscript={boot_at-4:#06x}')
        print(f'Reset target: {patch.reset_target_word*2:#06x}, boot RJMP={patch.boot_reset_word:#06x}, postscript RJMP={patch.postscript_reset_word:#06x}')
        if ns.out:
            ns.out.write_text(image_to_hex(patch.image))
            print('Wrote prepared image:',ns.out)
        if ns.execute:
            if identity is None:
                raise SystemExit('No known device descriptor/unsupported write protocol')
            assert programmer is not None
            program_application(programmer,patch)
            print('Experimental write/readback complete, including postscript. Hardware unverified.')
        elif not ns.identify:
            print('Dry run only. No USB device was modified.')

if __name__=='__main__':main()
