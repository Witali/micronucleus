"""Application image parsing and RESET/postscript packing; no USB transport.

Active clients supply the descriptor-derived boot boundary explicitly. The
legacy helper default remains only for compatibility with archived fixtures.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

FLASH_SIZE, PAGE_BYTES, BOOT_AT = 8192, 64, 0x1B40


@dataclass(frozen=True)
class PatchedImage:
    image: bytes  # entire application sector: [0, BOOT_AT), postscript included
    reset_target_word: int
    boot_reset_word: int
    postscript_reset_word: int


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


def record(addr: int, data: bytes = b'', typ: int = 0) -> str:
    hdr=bytes((len(data), (addr>>8)&255, addr&255, typ))
    rec=hdr+data
    return ':'+(rec+bytes(((-sum(rec))&255,))).hex().upper()


def image_to_hex(image: bytes) -> str:
    lines=[record(a,image[a:a+16]) for a in range(0,len(image),16)]
    lines.append(record(0,b'',1))
    return '\n'.join(lines)+'\n'
