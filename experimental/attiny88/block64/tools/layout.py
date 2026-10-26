"""Use the same explicit development reservation as the assembler header."""
from pathlib import Path
import re

HEADER = Path(__file__).resolve().parents[1] / 'source/device_attiny88.inc'
SOURCE = HEADER.read_text()


def constant(name):
    match = re.search(r'^#define\s+' + name + r'\s+(0x[0-9a-fA-F]+|[0-9]+)\s*$', SOURCE, re.M)
    if not match:
        raise ValueError('Missing numeric device constant: ' + name)
    return int(match.group(1), 0)


BOOT = constant('BOOT_AT')
FLASH = constant('T88_FLASH_BYTES')
PAGE = constant('T88_FLASH_PAGE_BYTES')
APP = BOOT - 4
RESERVED = FLASH - BOOT
assert 0 < BOOT < FLASH and BOOT % PAGE == 0
