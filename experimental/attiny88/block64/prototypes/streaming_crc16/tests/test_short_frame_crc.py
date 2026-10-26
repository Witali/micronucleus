"""Actual short-DATA framing and CRC/counter agreement, without hardware.

The mathematical minimum-length implication is necessary but insufficient
alone: the sampler must count the same decoded bytes its CRC pipeline sees.
This test freezes one assembled image and examines both old and refactored
EOP accounting through real opcodes and all nominal synchronization phases.
"""
from pathlib import Path
import itertools
import os
import sys

PROTOTYPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTOTYPE/'tools'))
import verify_streaming as V
from crc_tables import crc_bitwise


def short_frame_matrix(build):
    """Return evidence for 48,864 short-frame/phase combinations.

    All 256 possible single bytes after either DATA PID are tested without
    dribble. For dribble lengths 1..6, all bit strings are checked with PID
    only and PID+00. The latter is exhaustive for potential two-decoded-byte
    B001 acceptance: the only two-byte preimage is 00 00, independently
    established by the mathematical test. This is not an electrical proof.
    """
    original_cpu = V.TraceCPU

    class CountCPU(original_cpu):
        def step(self):
            for name in ('stream_crc_valid', 'stream_crc_drop'):
                if self.pc == self.labels.get(name):
                    pointer = self.r[28] | self.r[29] << 8
                    # Older EOP code leaves Y at the end of RX and R19 as
                    # remaining capacity. Refactored code restores Y and
                    # converts R19 to the decoded count before CRC cleanup.
                    if pointer > 0x0116:
                        count = pointer - 0x0116
                        assert count == 11 - self.r[19]
                    else:
                        assert pointer == 0x0116
                        count = self.r[19]
                    self.short_crc_snapshot = (
                        name, count, bytes(self.m[0x0116:0x0116+count]),
                        self.r[25] << 8 | self.r[30],
                    )
            return super().step()

    frames = 0
    seen_crc = 0
    counts = {}
    V.TraceCPU = CountCPU
    try:
        def check(packet, phase, dribble):
            nonlocal frames, seen_crc
            levels, metadata = V.wire(packet, dribble=dribble)
            obs, cpu, _ = V.receive(build, packet, phase,
                                    levels=levels, metadata=metadata)
            frames += 1
            snapshot = getattr(cpu, 'short_crc_snapshot', None)
            if snapshot:
                seen_crc += 1
                name, count, decoded, remainder = snapshot
                assert 1 <= count <= 11
                assert decoded[0] in (0xC3, 0x4B)
                counts[count] = counts.get(count, 0) + 1
                expected = crc_bitwise(decoded[1:])
                assert remainder == expected, (
                    'CRC/counter mismatch', packet.hex(), phase, dribble,
                    decoded.hex(), remainder, expected,
                )
                if count < 3:
                    assert remainder != 0xB001
                assert name != 'stream_crc_valid', (
                    'A short wire frame reached the valid residual',
                    packet.hex(), phase, dribble, decoded.hex(), count,
                )
            assert obs.response_pid is None and obs.published_length == 0, (
                'Short frame ACK/publication', packet.hex(), phase, dribble,
                obs, snapshot,
            )

        for pid in (0xC3, 0x4B):
            for suffix in [b''] + [bytes([value]) for value in range(256)]:
                for phase in range(-47, 1):
                    check(bytes([pid])+suffix, phase, ())
        for width in range(1, 7):
            for dribble in itertools.product((0, 1), repeat=width):
                for pid in (0xC3, 0x4B):
                    for suffix in (b'', b'\x00'):
                        for phase in range(-47, 1):
                            check(bytes([pid])+suffix, phase, dribble)
    finally:
        V.TraceCPU = original_cpu
    assert frames == 48864 and seen_crc > 0
    return {'sha256': build['sha256'], 'frames': frames,
            'crc_counter_snapshots': seen_crc,
            'decoded_length_counts': counts,
            'entry_phase_thirds': '-47..0', 'dribble_bits': '0..6',
            'short_data_acknowledged': 0, 'crc_counter_mismatches': 0}


def test_short_data_crc_and_count_at_every_nominal_phase():
    manifest = os.environ.get('STREAMING_CRC_MANIFEST',
                              str(PROTOTYPE/'build/streaming/manifest.json'))
    short_frame_matrix(V.load_build(manifest))
