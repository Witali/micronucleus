"""Build linked execution artifacts inside the ATtiny88's physical Flash.

Use build.build directly to measure overflowing experiments. Returning an
execution artifact must never silently model code beyond the real 8 KiB.
"""
from pathlib import Path

from build import build as measured_build
from host.profiles import BOOT_AT

FLASH_BYTES = 8192


def build(source=None, mode='NONE', boot=BOOT_AT):
    if not 0 <= boot < FLASH_BYTES:
        raise ValueError('Execution placement must be inside physical 8 KiB Flash')
    variant = str(Path(source).parent) if source is not None else 'source'
    image = measured_build(where=variant, led=mode, boot=boot)
    if not image['fits'] or boot + image['bytes'] > FLASH_BYTES:
        raise ValueError(f"Execution image exceeds physical Flash: {image['bytes']} "
                         f"bytes at {boot:#06x}; capacity {FLASH_BYTES - boot}")
    symbols = {}
    for line in image['symbols'].splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[2] == '.text':
            symbols[fields[-1]] = int(fields[0], 16)
    return dict(body=Path(image['bin']).read_bytes()[boot:], boot=boot,
                obj=Path(image['obj']), symbols=symbols)
