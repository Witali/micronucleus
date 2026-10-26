"""Independent arithmetic proof for the 32-byte nibble CRC experiment."""
from pathlib import Path
import importlib.util
import random

PATH = Path(__file__).resolve().parents[1] / 'tools/crc_nibble.py'
SPEC = importlib.util.spec_from_file_location('streaming_crc_nibble', PATH)
CRC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CRC)


def incoming_bits(data, initial=0xFFFF):
    """A separate serial reference, independent of table construction."""
    state = initial
    for value in data:
        for bit in range(8):
            feedback = ((value >> bit) ^ state) & 1
            state >>= 1
            if feedback:
                state ^= 0xA001
    return state


def assembly_bytes(source):
    return bytes(int(value, 16) for line in source.splitlines()
                 if line.startswith('.byte ')
                 for value in line[6:].split(', '))


def test_all_65536_states_and_256_bytes_match_the_independent_serial_reference():
    assert CRC.exhaustive_transition_check() == 65536 * 256


def test_nibble_order_basis_seed_and_standard_check_vector():
    assert [CRC.TABLE_WORDS[i] for i in (0, 1, 2, 4, 8)] == [
        0x0000, 0xCC01, 0xD801, 0xF001, 0xA001,
    ]
    assert CRC.crc_nibble(b'') == 0xFFFF
    assert CRC.wire_crc(b'') == b'\x00\x00'
    assert CRC.crc_nibble(b'123456789') == incoming_bits(b'123456789') == 0x4B37
    assert CRC.wire_crc(b'123456789') == b'\xc8\xb4'
    for initial in (0, 1, 0xFFFF, 0xA001, 0x1234, 0xB001):
        for value in range(256):
            low = CRC.advance_nibble_table(initial, value & 15)
            both = CRC.advance_nibble_table(low, value >> 4)
            assert both == CRC.advance_byte_nibble(initial, value)
            assert both == incoming_bits(bytes([value]), initial)


def test_constant_and_random_payloads_match_bit_reference():
    vectors = [bytes([value]) * length
               for length in range(11) for value in range(256)]
    rng = random.Random(0xA00132)
    vectors += [bytes(rng.randrange(256) for _ in range(rng.randrange(65)))
                for _ in range(4096)]
    for payload in vectors:
        assert CRC.crc_nibble(payload) == incoming_bits(payload)
        trailer = ((~incoming_bits(payload)) & 0xFFFF).to_bytes(2, 'little')
        assert CRC.wire_crc(payload) == trailer
        assert CRC.crc_nibble(payload + trailer) == 0xB001


def test_payload_and_crc_trailer_single_bit_corruption_is_detected():
    payloads = [b'', b'123456789', bytes(range(8)), b'\xff' * 8, b'\x00' * 8,
                b'\x80\x01\x7f\xfe\x55\xaa\x11\xee']
    for payload in payloads:
        wire = payload + CRC.wire_crc(payload)
        assert CRC.crc_nibble(wire) == incoming_bits(wire) == 0xB001
        for bit in range(len(wire) * 8):
            corrupt = bytearray(wire)
            corrupt[bit // 8] ^= 1 << (bit % 8)
            assert CRC.crc_nibble(corrupt) == incoming_bits(corrupt) != 0xB001


def test_generated_split_table_is_exactly_32_bytes_on_one_flash_page():
    source = CRC.render_assembly()
    assert source.count('.balign 32') == 1
    assert source.index(CRC.LOW_LABEL + ':') < source.index(CRC.HIGH_LABEL + ':')
    assert assembly_bytes(source) == CRC.TABLE_LOW + CRC.TABLE_HIGH
    assert len(CRC.TABLE_LOW) == len(CRC.TABLE_HIGH) == 16
    for start in range(0, 256, 32):
        assert start // 256 == (start + 31) // 256
    assert CRC.FOLDED_LABEL + ':' not in source


def test_optional_folded_lookup_is_only_a_separate_parity_substitute():
    """Prove the requested substitute, not a whole folded AVR CRC update."""
    for nibble in range(16):
        parity = (nibble ^ (nibble >> 1) ^ (nibble >> 2) ^ (nibble >> 3)) & 1
        repeated = nibble * 0x11
        first = repeated ^ (repeated >> 2)
        folded = (first ^ (first >> 1)) & 7
        assert CRC.TABLE_LOW[nibble] == parity
        assert CRC.FOLDED_PARITY_TABLE[nibble] == folded == parity * 7
    source = CRC.render_folded_assembly()
    assert assembly_bytes(source) == CRC.FOLDED_PARITY_TABLE
    assert len(assembly_bytes(source)) == 16 and source.count('.balign 16') == 1
    assert CRC.LOW_LABEL + ':' not in source and CRC.HIGH_LABEL + ':' not in source
