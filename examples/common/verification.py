"""Read real AVR artifacts and check shared compact-loader invariants."""
import hashlib
from .avr import USB_DRIVER, run_tool


def symbols(toolchain, elf):
    return {fields[2]: int(fields[0], 16)
            for line in run_tool(toolchain, 'avr-nm', '-n', '--defined-only', elf).splitlines()
            if len(fields := line.split()) == 3}


def rjmp_target(data, address):
    word = int.from_bytes(data[address:address + 2], 'little')
    assert word & 0xF000 == 0xC000, 'Expected a normal ATtiny88 RJMP vector'
    offset = word & 0xFFF
    if offset & 0x800:
        offset -= 0x1000
    return (address + 2 + 2 * offset) % 8192


def check_placement(binary, cells, table, programmer):
    assert rjmp_target(binary, 0) > 2
    assert rjmp_target(binary, 2) == table['__vector_1'] != table['__bad_interrupt']
    for _, boot_at, _ in programmer.USB_PROFILES.values():
        packed = programmer.pack_application(cells, boot_at=boot_at).image
        assert all(packed[at] == value for at, value in cells.items() if at >= 2)
        assert rjmp_target(packed, 0) == boot_at
        assert rjmp_target(packed, boot_at - 4) == rjmp_target(binary, 0)
        assert packed[boot_at - 2:boot_at] == b'\xff\xff'


def hid_items(report):
    position = 0
    while position < len(report):
        prefix = report[position]
        length = (0, 1, 2, 4)[prefix & 3]
        assert prefix != 0xFE and position + 1 + length <= len(report), 'Expected complete short HID items'
        yield prefix & 0xFC, int.from_bytes(report[position + 1:position + 1 + length], 'little')
        position += 1 + length


def verify_vendor():
    for line in (USB_DRIVER / 'SHA256SUMS').read_text(encoding='ascii').splitlines():
        expected, name = line.split()
        assert hashlib.sha256((USB_DRIVER / name).read_bytes()).hexdigest() == expected
