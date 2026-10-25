#!/usr/bin/env python3
"""Micronucleus+ ATtiny88 USB EEPROM + Flash read programmer (v2.8 / 2.9).

Compatible with ATtiny88 Micronucleus+ extensions 2.8 (up to 8-byte Flash reads)
and 2.9 (one-byte compact Flash reads).
For Flash *writing*, delegates to the stock Micronucleus CLI to preserve the
well-tested legacy protocol and vector patching; supply --micronucleus path.
Does not expose fuse, lock-bit, signature or arbitrary ISP instructions.
Requires PyUSB + libusb for physical usage: python -m pip install pyusb
No hardware is accessed for --help or in unit tests.

Vendor IN controls:
  0x00 GET_INFO, normal Micronucleus v2 command (8 bytes)
  0xA0 READ EEPROM: wValue=address, wIndex=0, wLength=1 -> data byte
  0xC0 WRITE EEPROM: wValue=address, wIndex=byte, wLength=1 -> status byte
  0xF0 RDY/BSY: wValue=wIndex=0, wLength=1 -> 0 ready, 1 busy
  0xB0 READ FLASH: wValue=byte-address, wIndex=0, wLength 1..8 (2.8) or 1 (2.9)
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Mapping

VID, PID = 0x16D0, 0x0753
USB_REQUEST_IN_VENDOR = 0xC0
EEPROM_SIZE = 64
EEPROM_FEATURE_FLAG = 0x40
FLASH_READ_FEATURE_FLAG = 0x80
REQ_INFO, REQ_READ, REQ_WRITE, REQ_READY, REQ_READFLASH = 0x00, 0xA0, 0xC0, 0xF0, 0xB0
REQ_CRC_FLASH, REQ_CRC_EEPROM, REQ_CRC_STEP = 0xD0, 0xD1, 0xD2


class EEPROMError(RuntimeError):
    pass

def crc16_usb(data: bytes) -> int:
    """USB CRC16: poly=0x8005, reflected 0xA001, init/xorout 0xFFFF."""
    crc = 0xffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc ^ 0xffff




class EEPROMTool:
    def __init__(self, dev, sleep=time.sleep):
        self.dev = dev
        self.sleep = sleep
        self.size = None
        self.flash_size = None
        self.features = None
        self.version = None
        self.flash_block_size = 8

    def transfer(self, opcode: int, w_value: int = 0, w_index: int = 0, length: int = 1) -> bytes:
        try:
            result = self.dev.ctrl_transfer(USB_REQUEST_IN_VENDOR, opcode, w_value, w_index, length, timeout=3000)
        except Exception as exc:
            raise EEPROMError(f'USB request 0x{opcode:02X} failed: {exc}') from exc
        return bytes(result)

    def check_device(self) -> int:
        header = self.transfer(REQ_INFO, length=8)
        if len(header) != 8:
            raise EEPROMError(f'Micronucleus info length {len(header)}, expected 8')
        if header[4:6] != bytes((0x93, 0x11)):
            raise EEPROMError(f'This firmware is for ATtiny88 only, got signature 0x1E{header[4]:02X}{header[5]:02X}')
        if header[6] & (EEPROM_FEATURE_FLAG | FLASH_READ_FEATURE_FLAG) != (EEPROM_FEATURE_FLAG | FLASH_READ_FEATURE_FLAG):
            raise EEPROMError('EEPROM+Flash extension not advertised; connect an ATtiny88 Micronucleus+ v2.8 device')
        self.features = header[6]
        self.version = header[7]
        # The USB device descriptor is bcdDevice 0x0208 (fast) or
        # 0x0209 (compact). GET_INFO[7] is the application version.
        # Unknown variants default to historical Micronucleus+ 2.8 (8-byte).
        bcd = int(getattr(self.dev, 'bcdDevice', 0x0208))
        self.flash_block_size = 1 if bcd == 0x0209 else 8
        self.crc_supported = bcd >= 0x0210  # Experimental Micronucleus+ CRC range extension
        self.size = EEPROM_SIZE
        self.flash_size = (header[0] << 8) | header[1]
        if not (0 < self.flash_size <= 8192) or (self.flash_size + 4) % 64 != 0:
            raise EEPROMError(f'Invalid programmable Flash size from bootloader: {self.flash_size}')
        return self.size

    def require(self, address: int):
        if self.size is None:
            raise EEPROMError('Call check_device() before touching EEPROM')
        if not 0 <= address < self.size:
            raise EEPROMError(f'EEPROM address {address} not in 0..{self.size-1}')

    def busy(self) -> bool:
        result = self.transfer(REQ_READY)
        if len(result) != 1 or result[0] not in (0, 1):
            raise EEPROMError(f'Bad EEPROM ready response: {result.hex()}')
        return result[0] == 1

    def wait_ready(self, max_seconds=0.25, interval=0.003) -> None:
        deadline = time.monotonic() + max_seconds
        while self.busy():
            if time.monotonic() >= deadline:
                raise EEPROMError('Timed out waiting for EEPROM write to finish')
            self.sleep(interval)

    def crc_range_local(self, memory: str, start: int, end: int) -> int:
        """Compatible, slower fallback: read memory using existing USB commands
        and compute exactly the same CRC on the host. No firmware CRC extension.
        """
        if self.flash_size is None:
            raise EEPROMError('Call check_device() before CRC range')
        if memory == 'flash':
            if not 0 <= start < end <= self.flash_size:
                raise EEPROMError('Invalid local Flash CRC range')
            data = self.read_flash(start, end-start)
        elif memory == 'eeprom':
            if not 0 <= start < end <= self.size:
                raise EEPROMError('Invalid local EEPROM CRC range')
            data = bytes(self.read_byte(addr) for addr in range(start,end))
        else:
            raise EEPROMError('Unknown memory region')
        return crc16_usb(data)

    def crc_range(self, memory: str, start: int, end: int, *, chunk: int = 8) -> int:
        """CRC-16/USB over [start,end), computed on the MCU with the existing
        V-USB CRC bit kernel. The host sends bounded STEP requests to keep
        SETUP-processing latency shorter than a monolithic memory scan.

        This is an experimental protocol: hardware-level turnaround timing
        needs verification before use on production devices.
        """
        if self.flash_size is None:
            raise EEPROMError('Call check_device() before CRC range')
        if not getattr(self, 'crc_supported', False):
            raise EEPROMError('CRC range is not supported by this Micronucleus firmware')
        if memory not in ('flash','eeprom'):
            raise EEPROMError(f'Bad memory type: {memory}')
        limit = self.flash_size if memory == 'flash' else self.size
        if not (0 <= start < end <= limit):
            raise EEPROMError(f'Invalid {memory} CRC range [{start:#x},{end:#x}) (limit {limit:#x})')
        if not 1 <= chunk <= 16:
            raise EEPROMError('CRC chunk must be 1..16; smaller chunks reduce USB turnaround latency')
        opcode = REQ_CRC_FLASH if memory == 'flash' else REQ_CRC_EEPROM
        ack = self.transfer(opcode, w_value=start, w_index=end, length=1)
        if ack != b'\x00':
            raise EEPROMError(f'CRC range START rejected: {ack.hex()}')
        total = end-start
        steps = (total + chunk-1)//chunk
        for _ in range(steps):
            status = self.transfer(REQ_CRC_STEP, w_value=chunk, w_index=0, length=3)
            if len(status)!=3:
                raise EEPROMError(f'CRC STEP reply length {len(status)}, expected 3')
            if status[0] == 1:
                return int.from_bytes(status[1:], 'little')
            if status[0] != 0:
                raise EEPROMError(f'CRC STEP returned error status {status[0]}')
        raise EEPROMError(f'CRC did not finish after {steps} bounded steps')

    def read_byte(self, addr: int) -> int:
        self.require(addr)
        self.wait_ready()
        data = self.transfer(REQ_READ, w_value=addr)
        if len(data) != 1:
            raise EEPROMError(f'EEPROM read at {addr} returned {len(data)} bytes, not 1')
        return data[0]

    def write_byte(self, addr: int, value: int) -> None:
        self.require(addr)
        if not 0 <= value <= 255:
            raise EEPROMError(f'Not a byte: {value}')
        self.wait_ready()
        for attempt in range(3):
            status = self.transfer(REQ_WRITE, w_value=addr, w_index=value)
            if len(status) != 1:
                raise EEPROMError(f'EEPROM write at {addr} did not acknowledge status')
            if status[0] == 0:
                self.wait_ready()
                return
            if status[0] == 2:
                raise EEPROMError(f'EEPROM write invalid address or parameter at {addr}')
            if status[0] != 1:
                raise EEPROMError(f'Unknown EEPROM write status {status[0]}')
            self.wait_ready()
        raise EEPROMError(f'EEPROM stayed busy at address {addr}')

    def read(self) -> bytes:
        return bytes(self.read_byte(a) for a in range(self.size or 0))

    def program(self, patch: Mapping[int, int], *, skip_unchanged=True, verify=True) -> int:
        count = 0
        for addr in sorted(patch):
            self.require(addr)
            value = int(patch[addr])
            if not 0 <= value <= 255:
                raise EEPROMError(f'Invalid data byte at {addr}: {value}')
            if skip_unchanged and self.read_byte(addr) == value:
                continue
            self.write_byte(addr, value)
            count += 1
            if verify and self.read_byte(addr) != value:
                raise EEPROMError(f'Verify mismatch at 0x{addr:02X}')
        return count

    def verify(self, patch: Mapping[int, int]) -> None:
        for addr in sorted(patch):
            current = self.read_byte(addr)
            expected = patch[addr]
            if current != expected:
                raise EEPROMError(f'EEPROM mismatch at 0x{addr:02X}: read 0x{current:02X}, wanted 0x{expected:02X}')


    def read_flash_block(self, address: int, count: int) -> bytes:
        """Physical application Flash bytes, bounded by device-specific max block length."""
        if self.flash_size is None:
            raise EEPROMError('Call check_device() before Flash read')
        if not 1 <= count <= self.flash_block_size or address < 0 or address + count > self.flash_size:
            raise EEPROMError(f'Invalid Flash block 0x{address:04X} + {count} (limit {self.flash_size})')
        buf = self.transfer(REQ_READFLASH, w_value=address, w_index=0, length=count)
        if len(buf) != count:
            raise EEPROMError(f'Flash read at 0x{address:04X}: expected {count} bytes, got {len(buf)}')
        return buf

    def read_flash(self, start: int = 0, length: int | None = None) -> bytes:
        if self.flash_size is None:
            raise EEPROMError('Call check_device() before Flash read')
        if length is None:
            length = self.flash_size - start
        if not 0 <= start <= self.flash_size or length < 0 or start + length > self.flash_size:
            raise EEPROMError(f'Invalid Flash range 0x{start:04X} + {length}')
        n = self.flash_block_size
        return b''.join(self.read_flash_block(a, min(n, start + length - a))
                        for a in range(start, start + length, n))

    def verify_flash(self, patch: Mapping[int, int], skip_reset_vector: bool = False) -> None:
        """Verify sparse or dense Flash images with device-specific block size."""
        if self.flash_size is None:
            raise EEPROMError('Call check_device() before Flash verification')
        for addr in patch:
            if addr < 0 or addr >= self.flash_size:
                raise EEPROMError(f'Flash image address 0x{addr:04X} exceeds application area')
            if not 0 <= patch[addr] <= 255:
                raise EEPROMError(f'Invalid Flash byte at 0x{addr:04X}')
        addrs = sorted(a for a in patch if not (skip_reset_vector and a < 2))
        offset = 0
        while offset < len(addrs):
            segment = [addrs[offset]]
            offset += 1
            while offset < len(addrs) and len(segment) < self.flash_block_size and addrs[offset] == segment[-1] + 1:
                segment.append(addrs[offset])
                offset += 1
            buf = self.read_flash_block(segment[0], len(segment))
            for addr, actual in zip(segment, buf):
                if actual != patch[addr]:
                    hint = ' (reset vector is normally patched by Micronucleus)' if addr < 2 else ''
                    raise EEPROMError(f'Flash mismatch at 0x{addr:04X}: read 0x{actual:02X}, expected 0x{patch[addr]:02X}{hint}')


def write_flash_using_official_tool(path: pathlib.Path, *, tool='micronucleus', run=False) -> int:
    """Reuse original Micronucleus command-line Flash uploader unmodified."""
    executable = shutil.which(tool)
    if executable is None and not pathlib.Path(tool).is_file():
        raise EEPROMError(f'Micronucleus CLI not found: {tool}. Install the original CLI or pass --micronucleus PATH')
    # Default firmware is Intel HEX; original CLI handles reset vector patching.
    cmd = [tool]
    if path.suffix.lower() == '.bin':
        cmd += ['--type', 'raw']
    if run:
        cmd.append('--run')
    cmd.append(str(path))
    try:
        return subprocess.run(cmd, check=False).returncode
    except OSError as exc:
        raise EEPROMError(f'Unable to launch Micronucleus CLI: {exc}') from exc


def load_hex_bytes(content: str, max_size=EEPROM_SIZE) -> dict[int, int]:
    """Read Intel HEX, preserving sparse/only-specified EEPROM addresses."""
    output: dict[int, int] = {}
    base = 0
    have_eof = False
    for lineno, raw_line in enumerate(content.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if have_eof:
            raise EEPROMError(f'Data after Intel HEX EOF at line {lineno}')
        if not line.startswith(':') or len(line) < 11 or len(line) % 2 != 1:
            raise EEPROMError(f'Invalid Intel HEX record at line {lineno}')
        try:
            data = bytes.fromhex(line[1:])
        except ValueError as exc:
            raise EEPROMError(f'Non-hexadecimal record at line {lineno}') from exc
        n, ah, al, mode = data[:4]
        if len(data) != n + 5 or sum(data) % 256 != 0:
            raise EEPROMError(f'Bad length or checksum at line {lineno}')
        location = (ah << 8) | al
        payload = data[4:-1]
        if mode == 0:
            if location + base + n > max_size:
                raise EEPROMError(f'HEX record exceeds {max_size}-byte memory at line {lineno}')
            for i, value in enumerate(payload):
                where = base + location + i
                if where in output and output[where] != value:
                    raise EEPROMError(f'Conflicting Intel HEX bytes at 0x{where:02X}')
                output[where] = value
        elif mode == 1:
            if n != 0 or location != 0:
                raise EEPROMError('Malformed HEX end-of-file record')
            have_eof = True
        elif mode in (2, 4):
            if n != 2 or location != 0:
                raise EEPROMError('Malformed HEX base-address record')
            v = int.from_bytes(payload, 'big')
            base = (v << (4 if mode == 2 else 16))
        elif mode in (3, 5):
            # Optional execution start record: not relevant for EEPROM data.
            if n != 4:
                raise EEPROMError('Malformed HEX start-address record')
        else:
            raise EEPROMError(f'Unsupported Intel HEX type {mode} at line {lineno}')
    if not have_eof:
        raise EEPROMError('Intel HEX has no EOF record')
    return output


def hex_rec(addr: int, payload: bytes, typ=0) -> str:
    header = bytes((len(payload), (addr >> 8) & 0xff, addr & 0xff, typ))
    full = header + payload
    return ':' + (full + bytes((-sum(full) & 0xff,))).hex().upper()


def write_hex_bytes(data: bytes, base: int = 0) -> str:
    return '\n'.join([hex_rec(base + i, data[i:i+16]) for i in range(0, len(data), 16)] + [hex_rec(0,b'',1), ''])


def load_image(path: pathlib.Path, max_size=EEPROM_SIZE) -> dict[int, int]:
    if path.suffix.lower() in ('.hex', '.eep', '.ihex'):
        return load_hex_bytes(path.read_text(encoding='ascii'), max_size=max_size)
    raw = path.read_bytes()
    if len(raw) > max_size:
        raise EEPROMError(f'{len(raw)} bytes exceeds memory size of {max_size}')
    return dict(enumerate(raw))


def find_device():
    try:
        import usb.core
    except ImportError as exc:
        raise EEPROMError('PyUSB not installed; run: python -m pip install pyusb') from exc
    device = usb.core.find(idVendor=VID, idProduct=PID)
    if device is None:
        raise EEPROMError('No Micronucleus device detected; connect/reset the board while bootloader is active')
    return device


def parse_number(s: str) -> int:
    return int(s, 0)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Micronucleus+ v2.10 experimental ATtiny88 Flash/EEPROM/CRC USB programmer')
    parser.add_argument('--micronucleus', default='micronucleus', metavar='PATH',
                        help='Original Micronucleus executable used for Flash WRITE only')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('info', help='Identify and check memory capabilities')

    for command_name in ('eeprom-read', 'eeprom-write', 'eeprom-verify',
                         'flash-read', 'flash-verify', 'flash-write'):
        cmd = sub.add_parser(command_name)
        cmd.add_argument('path', type=pathlib.Path)
        if command_name == 'eeprom-write':
            cmd.add_argument('--force', action='store_true', help='Write unchanged bytes too (wears EEPROM)')
        if command_name == 'flash-read':
            cmd.add_argument('--start', type=parse_number, default=0, help='Start address; decimal or 0xHEX')
            cmd.add_argument('--length', type=parse_number, default=None, help='Bytes to read; default to end of application')
        if command_name == 'flash-verify':
            cmd.add_argument('--skip-reset-vector', action='store_true', help='Ignore bootloader-patched Flash bytes 0 and 1')
        if command_name == 'flash-write':
            cmd.add_argument('--run', action='store_true', help='Start user application after uploading')

    for command_name in ('flash-crc','eeprom-crc'):
        cmd = sub.add_parser(command_name, help='Compute CRC-16/USB in device for [start,end)')
        cmd.add_argument('start', type=parse_number, help='Inclusive start address (decimal or 0xHEX)')
        cmd.add_argument('end', type=parse_number, help='Exclusive end address (decimal or 0xHEX)')
        cmd.add_argument('--chunk', type=parse_number, default=8, help='1..16 memory bytes processed per request, default 8')
        cmd.add_argument('--local', action='store_true', help='Read memory and compute CRC on the PC (older Micronucleus+ compatible)')

    # Backward-compatible aliases from the preceding EEPROM-only utility.
    for alias in ('read','write','verify'):
        cmd = sub.add_parser(alias, help=f'Alias for eeprom-{alias}')
        cmd.add_argument('path', type=pathlib.Path)
        if alias == 'write': cmd.add_argument('--force', action='store_true')

    args = parser.parse_args(argv)
    try:
        if args.command == 'flash-write':
            return write_flash_using_official_tool(args.path, tool=args.micronucleus, run=args.run)
        dev = find_device()
        tool = EEPROMTool(dev)
        n = tool.check_device()
        if args.command == 'info':
            print(f'Micronucleus+ ATtiny88: EEPROM={n} bytes, application Flash={tool.flash_size} bytes')
            print(f'Features byte=0x{tool.features:02X}, EEPROM A0/C0/F0, Flash Read B0 ({tool.flash_block_size} byte(s)/request)')
        elif args.command in ('flash-crc','eeprom-crc'):
            region = 'flash' if args.command == 'flash-crc' else 'eeprom'
            result = (tool.crc_range_local(region,args.start,args.end) if args.local else
                      tool.crc_range(region,args.start,args.end,chunk=args.chunk))
            print(f'{region.upper()} [{args.start:#06x},{args.end:#06x}): CRC-16/USB = 0x{result:04X}' +
                  (' (computed on PC)' if args.local else ' (computed in ATtiny88)'))
            print('CRC definition: poly=0x8005 (reflected 0xA001), init=0xFFFF, xorout=0xFFFF')
        elif args.command in ('eeprom-read','read'):
            image = tool.read()
            if args.path.suffix.lower() in ('.hex', '.eep', '.ihex'):
                args.path.write_text(write_hex_bytes(image), encoding='ascii')
            else:
                args.path.write_bytes(image)
            print(f'Read {len(image)} EEPROM bytes to {args.path}')
        elif args.command in ('eeprom-write','write'):
            patch = load_image(args.path)
            changed = tool.program(patch, skip_unchanged=not args.force, verify=True)
            print(f'EEPROM write verified: {changed} bytes written, {len(patch)-changed} unchanged')
        elif args.command in ('eeprom-verify','verify'):
            patch = load_image(args.path)
            tool.verify(patch)
            print(f'EEPROM verified: {len(patch)} bytes match')
        elif args.command == 'flash-read':
            start = args.start
            length = tool.flash_size - start if args.length is None else args.length
            image = tool.read_flash(start, length)
            if args.path.suffix.lower() in ('.hex', '.eep', '.ihex'):
                args.path.write_text(write_hex_bytes(image, base=start), encoding='ascii')
            else:
                args.path.write_bytes(image)
            print(f'Read {len(image)} raw Flash bytes starting at 0x{start:04X} into {args.path}')
            if start == 0:
                print('NOTE: Reset vector in Flash is patched by the bootloader; raw dump is not the original application HEX.')
        elif args.command == 'flash-verify':
            patch = load_image(args.path, max_size=tool.flash_size)
            tool.verify_flash(patch, skip_reset_vector=args.skip_reset_vector)
            print(f'Flash verified: {len(patch)} specified bytes match' + (' (reset vector excluded)' if args.skip_reset_vector else ''))
        else:
            raise EEPROMError(f'Unexpected operation: {args.command}')
        return 0
    except (EEPROMError, OSError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
