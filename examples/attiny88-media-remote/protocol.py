"""Media remote reports. No USB, platform or GUI dependencies."""
import struct

ACTIONS = {
    'Disabled': 0, 'Mute': 0xe2, 'Volume up': 0xe9, 'Volume down': 0xea,
    'Play / pause': 0xcd, 'Next track': 0xb5, 'Previous track': 0xb6, 'Stop': 0xb7,
}
DEFAULTS = (0xe2, 0xe9, 0xea)


def mapping_report(mapping, persist=True):
    mapping = tuple(mapping)
    if len(mapping) != 3 or any(code not in ACTIONS.values() for code in mapping):
        raise ValueError('Select three supported media actions')
    return struct.pack('<BB3H', 3, 0x81 if persist else 1, *mapping)


def parse_mapping(data):
    if len(data) != 8:
        raise ValueError('Expected an 8-byte mapping feature report')
    report, status, *mapping = struct.unpack('<BB3H', data)
    if report != 3 or status & 0xf != 1 or status & ~0x31:
        raise ValueError('Unknown media remote protocol')
    if any(code not in ACTIONS.values() for code in mapping):
        raise ValueError('Unsupported mapping returned by device')
    if status & 0x20:
        raise OSError('The device reported an EEPROM readback failure')
    return tuple(mapping), bool(status & 0x10)


def mute_report(muted):
    return bytes((2, 0 if muted is None else 2 | int(bool(muted))))
