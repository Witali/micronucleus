#!/usr/bin/env python3
"""Generate a 32-byte USB CRC16 nibble table and prove its arithmetic.

USB 2.0 section 8.3.5.2 specifies x^16+x^15+x^2+1, an all-one initial
register and a complemented transmitted CRC. Here the reflected polynomial
is 0xA001; appending the complemented low/high trailer gives raw residual
0xB001. Feed DATA payload/trailer bytes only, excluding the USB PID.

This is a data/math experiment. It does not change a receiver, demonstrate
an AVR implementation's timing, or program hardware. The optional 16-byte
folded-parity lookup is separate from the requested 32-byte CRC table.
"""
from pathlib import Path
import argparse
import hashlib
import json

POLYNOMIAL = 0xA001
INITIAL_CRC = 0xFFFF
DATA_RESIDUAL = 0xB001
LOW_LABEL = 'crc_nibble_table_low'
HIGH_LABEL = 'crc_nibble_table_high'
FOLDED_LABEL = 'crc_fold_table'


def advance_nibble_bitwise(crc: int, value: int) -> int:
    """Independent serial reference: feed four incoming bits, LSB first."""
    if not (0 <= crc <= 0xFFFF and 0 <= value <= 15):
        raise ValueError('CRC and nibble must be unsigned 16/4-bit values')
    for bit in range(4):
        feedback = (crc ^ (value >> bit)) & 1
        crc >>= 1
        if feedback:
            crc ^= POLYNOMIAL
    return crc


def advance_byte_bitwise(crc: int, value: int) -> int:
    """Independent serial reference, with no generated table access."""
    if not (0 <= crc <= 0xFFFF and 0 <= value <= 255):
        raise ValueError('CRC and byte must be unsigned 16/8-bit values')
    for bit in range(8):
        feedback = (crc ^ (value >> bit)) & 1
        crc >>= 1
        if feedback:
            crc ^= POLYNOMIAL
    return crc


TABLE_WORDS = tuple(advance_nibble_bitwise(0, value) for value in range(16))
TABLE_LOW = bytes(value & 255 for value in TABLE_WORDS)
TABLE_HIGH = bytes(value >> 8 for value in TABLE_WORDS)

# In the separate folded update's parity substitute, all three result bits
# are the XOR of the four input-nibble bits. This is lookup data only; the
# complete folded AVR recurrence requires its own independent opcode test.
FOLDED_PARITY_TABLE = bytes(7 * (value.bit_count() & 1) for value in range(16))


def advance_nibble_table(crc: int, value: int) -> int:
    if not (0 <= crc <= 0xFFFF and 0 <= value <= 15):
        raise ValueError('CRC and nibble must be unsigned 16/4-bit values')
    return (crc >> 4) ^ TABLE_WORDS[(crc ^ value) & 15]


def advance_byte_nibble(crc: int, value: int) -> int:
    """Two nibble steps, low nibble before high nibble; no final complement."""
    if not (0 <= crc <= 0xFFFF and 0 <= value <= 255):
        raise ValueError('CRC and byte must be unsigned 16/8-bit values')
    crc = (crc >> 4) ^ TABLE_WORDS[(crc ^ value) & 15]
    return (crc >> 4) ^ TABLE_WORDS[(crc ^ (value >> 4)) & 15]


def crc_nibble(data: bytes, initial: int = INITIAL_CRC) -> int:
    if not 0 <= initial <= 0xFFFF:
        raise ValueError('Initial CRC must be an unsigned 16-bit value')
    crc = initial
    for value in data:
        crc = advance_byte_nibble(crc, value)
    return crc


def wire_crc(data: bytes) -> bytes:
    return ((~crc_nibble(data)) & 0xFFFF).to_bytes(2, 'little')


def render_assembly(low_label: str = LOW_LABEL, high_label: str = HIGH_LABEL) -> str:
    """Emit exactly 32 data bytes as contiguous 16-byte low/high halves.

    A 32-byte alignment also guarantees this table never crosses a 256-byte
    Flash page. Merely aligning to 16 could place the halves at xxF0/xy00.
    Alignment padding is not included in the stated 32 data bytes.
    """
    return '\n'.join([
        '/* Generated reflected USB CRC16 nibble table; 32 data bytes. */',
        '.balign 32', low_label + ':',
        '.byte ' + ', '.join(f'0x{value:02x}' for value in TABLE_LOW),
        high_label + ':',
        '.byte ' + ', '.join(f'0x{value:02x}' for value in TABLE_HIGH),
    ]) + '\n'


def render_folded_assembly(label: str = FOLDED_LABEL) -> str:
    """Separate parity substitute, not the 32-byte nibble CRC table."""
    return '\n'.join([
        '/* Optional folded-parity lookup; 16 data bytes, no timing claim. */',
        '.balign 16', label + ':',
        '.byte ' + ', '.join(f'0x{value:02x}' for value in FOLDED_PARITY_TABLE),
    ]) + '\n'


def exhaustive_transition_check() -> int:
    """Compare every state/byte pair with the independent eight-bit shift.

    Cache the serial zero-input transformation of all 65,536 states, then
    apply input-byte XOR to its argument. Every one of the 16,777,216 pairs
    still executes the public two-nibble operation and is compared. The
    reference cache never uses either generated lookup table.
    """
    serial_after_xor = tuple(advance_byte_bitwise(state, 0) for state in range(65536))
    actual_step = advance_byte_nibble
    checked = 0
    for state in range(65536):
        for value in range(256):
            actual = actual_step(state, value)
            expected = serial_after_xor[state ^ value]
            if actual != expected:
                raise AssertionError((state, value, actual, expected))
            checked += 1
    return checked


def self_test() -> dict:
    checked = exhaustive_transition_check()
    vectors = [bytes([value]) * length
               for length in range(11) for value in range(256)]
    vectors += [b'123456789', bytes(range(64))]
    for payload in vectors:
        expected = INITIAL_CRC
        for value in payload:
            expected = advance_byte_bitwise(expected, value)
        assert crc_nibble(payload) == expected
        assert crc_nibble(payload + wire_crc(payload)) == DATA_RESIDUAL
    assert crc_nibble(b'123456789') == 0x4B37
    assert all(TABLE_LOW[n] == n.bit_count() % 2 for n in range(16))
    return {
        'state_byte_pairs': checked, 'payload_vectors': len(vectors),
        'initial_crc': hex(INITIAL_CRC), 'raw_data_residual': hex(DATA_RESIDUAL),
        'nibble_table_bytes': 32,
        'nibble_table_sha256': hashlib.sha256(TABLE_LOW + TABLE_HIGH).hexdigest(),
        'optional_folded_parity_table_bytes': len(FOLDED_PARITY_TABLE),
        'timing_proof': 'not established by CRC arithmetic tests',
        'receiver_changed': False, 'hardware_accessed': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='write the 32-byte split CRC table')
    parser.add_argument('--folded-output', type=Path,
                        help='write the separate optional 16-byte parity lookup')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    for path, rendered in ((args.output, render_assembly()),
                           (args.folded_output, render_folded_assembly())):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding='ascii', newline='\n')
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
    elif not args.output and not args.folded_output:
        print(render_assembly(), end='')


if __name__ == '__main__':
    main()
