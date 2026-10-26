"""CRC arithmetic only; real opcode/sample timing belongs to the RX harness."""
import importlib.util
from pathlib import Path
import random
import sys


PATH = Path(__file__).resolve().parents[1] / "tools/crc_tables.py"
SPEC = importlib.util.spec_from_file_location("streaming_crc_tables", PATH)
CRC = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CRC
SPEC.loader.exec_module(CRC)


def incoming_bit_reference(data, initial=0xFFFF):
    """Feed incoming bits one at a time, independent of the table indexing."""
    result = initial
    for value in data:
        for bit in range(8):
            feedback = ((value >> bit) ^ result) & 1
            result >>= 1
            if feedback:
                result ^= 0xA001
    return result


def test_all_65536_states_and_256_bytes_match_serial_reference():
    assert CRC.exhaustive_transition_check() == 65536 * 256


def test_virtual_zero_seed_and_first_two_pipeline_iterations():
    assert CRC.TABLE_LOW[0x54] == 0x01
    assert CRC.TABLE_HIGH[0x54] == 0xFF
    assert CRC.advance_byte_bitwise(0xFE54, 0) == 0xFFFF
    for pid in (0, 0xC3, 0x4B, 0xD2, 0x69, 0xE1, 0x2D):
        state = CRC.Pipeline(old_high=pid, byte_latch=pid)
        state.bit4()
        assert (state.old_high, state.zl) == (0xFE, 0x54)
        state.bit5()
        state.bit6()
        assert (state.pending_high, state.zl) == (0xFF, 0x01)
        state.bit7(0xA5)
        state.bit4()
        assert state.old_high == 0xFF and state.zl == 0xFF ^ 0xA5


def test_every_constant_length_and_random_payload_crc_is_independent():
    vectors = [bytes([value]) * length for length in range(11) for value in range(256)]
    randomizer = random.Random(0xC16)
    vectors += [bytes(randomizer.randrange(256) for _ in range(randomizer.randrange(11)))
                for _ in range(4096)]
    for payload in vectors:
        expected = incoming_bit_reference(payload)
        assert CRC.crc_bitwise(payload) == expected
        for pid in (0, 0xC3, 0x4B):
            assert CRC.pipeline_crc(payload, pid_latch=pid) == expected


def test_received_wire_crc_gives_residual_and_all_single_bit_errors_fail():
    payloads = [b"", bytes(range(8)), b"\xff" * 8, b"\x00" * 8,
                b"\x7f\xfe\xfb\xef\xbf\x55\xaa\x11"]
    for payload in payloads:
        frame = payload + CRC.wire_crc(payload)
        assert incoming_bit_reference(frame) == 0xB001
        assert CRC.pipeline_crc(frame) == 0xB001
        for bit in range(len(frame) * 8):
            changed = bytearray(frame)
            changed[bit // 8] ^= 1 << (bit % 8)
            assert CRC.pipeline_crc(changed) != 0xB001


def test_generator_is_512_bytes_and_low_high_have_page_layout():
    assembly = CRC.render_assembly()
    assert assembly.count(".balign 256") == 1
    assert assembly.index(CRC.LOW_LABEL + ":") < assembly.index(CRC.HIGH_LABEL + ":")
    data = bytes(int(value, 16) for line in assembly.splitlines()
                 if line.startswith(".byte ") for value in line[6:].split(", "))
    assert data == CRC.TABLE_LOW + CRC.TABLE_HIGH
    assert len(data) == 512


def test_data_residual_requires_at_least_two_decoded_bytes_after_pid():
    """The fast-path length implication also needs sampler/counter agreement.

    This proves the arithmetic implication only. Separate waveform tests must
    establish that the sampler's decoded count describes the same complete
    byte sequence consumed by the delayed pipeline at each EOP/dribble path.
    A partial wire byte decoded as a full byte is a distinct framing issue;
    a decoded-length guard would not detect it once it is counted as byte 2.
    """
    assert incoming_bit_reference(b'') == 0xFFFF != 0xB001
    one_byte_states = {incoming_bit_reference(bytes([value])) for value in range(256)}
    assert len(one_byte_states) == 256 and 0xB001 not in one_byte_states
    for pid in (0xC3, 0x4B):
        assert CRC.pipeline_crc(b'', pid_latch=pid) == 0xFFFF
        for value in range(256):
            payload = bytes([value])
            assert CRC.pipeline_crc(payload, pid_latch=pid) == incoming_bit_reference(payload)
            assert CRC.pipeline_crc(payload, pid_latch=pid) != 0xB001
    preimages = []
    for first in range(256):
        initial = incoming_bit_reference(bytes([first]))
        for second in range(256):
            if CRC.advance_byte_table(initial, second) == 0xB001:
                preimages.append(bytes([first, second]))
    assert preimages == [b'\x00\x00']
