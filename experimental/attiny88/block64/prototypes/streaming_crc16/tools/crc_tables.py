#!/usr/bin/env python3
"""USB CRC16 tables and the delayed receiver's AVR-register arithmetic.

This module generates data only. It does not enable a USB receiver, program
Flash, or establish sampling/handshake timing. Tables use reflected 0xA001,
initial CRC 0xFFFF and the uncomplemented wire residual 0xB001.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

POLYNOMIAL = 0xA001
INITIAL_CRC = 0xFFFF
DATA_RESIDUAL = 0xB001
VIRTUAL_ZERO_SEED = 0xFE54
LOW_LABEL = "stream_crc_table_low"
HIGH_LABEL = "stream_crc_table_high"


def advance_byte_bitwise(crc: int, value: int) -> int:
    """The reference operation, with no table access."""
    if not (0 <= crc <= 0xFFFF and 0 <= value <= 0xFF):
        raise ValueError("CRC and input byte must be unsigned 16/8-bit values")
    crc ^= value
    for _ in range(8):
        crc = (crc >> 1) ^ (POLYNOMIAL if crc & 1 else 0)
    return crc


def tables() -> tuple[bytes, bytes]:
    words = tuple(advance_byte_bitwise(0, value) for value in range(256))
    return (bytes(value & 0xFF for value in words),
            bytes(value >> 8 for value in words))


TABLE_LOW, TABLE_HIGH = tables()
TABLE_WORDS = tuple(lo | hi << 8 for lo, hi in zip(TABLE_LOW, TABLE_HIGH))


def advance_byte_table(crc: int, value: int) -> int:
    index = (crc & 0xFF) ^ value
    return TABLE_WORDS[index] ^ (crc >> 8)


def crc_bitwise(data: bytes, initial: int = INITIAL_CRC) -> int:
    crc = initial
    for value in data:
        crc = advance_byte_bitwise(crc, value)
    return crc


def wire_crc(data: bytes) -> bytes:
    return ((~crc_bitwise(data)) & 0xFFFF).to_bytes(2, "little")


@dataclass
class Pipeline:
    """Exact data roles: ZL/R30, old high/R24, pending high/R25, latch/R20.

    At bit 4, finish the previous table lookup then XOR the preceding byte.
    Bits 5/6 load its high/low table results. At bit 7, latch the just decoded
    byte. A virtual zero consumes the inverse seed before the actual bytes.

    The normal receiver stores PID then clears the latch, so all defaults
    apply. If it retains PID in R20 until the first bit 4, set both old_high
    and byte_latch to that PID; their XOR cancels without entering DATA CRC.
    """
    zl: int = 0x54
    old_high: int = 0
    pending_high: int = 0xFE
    byte_latch: int = 0

    def bit4(self) -> None:
        self.zl ^= self.old_high       # EOR ZL, R24
        self.old_high = self.pending_high  # MOV R24, R25
        self.zl ^= self.byte_latch     # EOR ZL, R20

    def bit5(self) -> None:
        self.pending_high = TABLE_HIGH[self.zl]  # LPM R25, Z

    def bit6(self) -> None:
        self.zl = TABLE_LOW[self.zl]   # LPM ZL, Z; old index is now dead

    def bit7(self, decoded_byte: int) -> None:
        self.byte_latch = decoded_byte

    def receive_byte(self, decoded_byte: int) -> None:
        self.bit4()
        self.bit5()
        self.bit6()
        self.bit7(decoded_byte)

    def finish_eop(self) -> int:
        """Return the post-cleanup R25:ZL value, without complementing it.

        Three prefix ALU instructions finish the pending previous-byte update
        and form the last-byte index. Two LDI plus two three-cycle LPM and
        one EOR complete the last lookup: 12 arithmetic/lookup cycles. The
        valid-residual comparisons add four cycles; restoring Z adds two.
        These counts exclude EOP detection and all caller/classifier work.
        """
        self.bit4()
        self.bit5()
        self.bit6()
        self.zl ^= self.old_high
        return self.pending_high << 8 | self.zl


def pipeline_crc(data: bytes, pid_latch: int = 0) -> int:
    state = Pipeline(old_high=pid_latch, byte_latch=pid_latch)
    for value in data:
        state.receive_byte(value)
    return state.finish_eop()


def render_assembly(low_label: str = LOW_LABEL,
                    high_label: str = HIGH_LABEL) -> str:
    """Emit a 256-aligned low table immediately followed by its high table."""
    lines = ["/* Generated reflected USB CRC16 tables; 512 data bytes. */",
             ".balign 256", low_label + ":"]
    for data, label in ((TABLE_LOW, low_label), (TABLE_HIGH, high_label)):
        if label != low_label:
            lines.append(label + ":")
        for first in range(0, 256, 16):
            lines.append(".byte " + ", ".join(f"0x{v:02x}" for v in data[first:first+16]))
    return "\n".join(lines) + "\n"


def exhaustive_transition_check() -> int:
    """Enumerate all 16,777,216 CRC/input pairs against serial recurrence.

    Cache the independently bit-shifted result for every possible CRC after
    byte XOR. The cache covers all 65,536 inputs to that bitwise transform;
    the pair enumeration still checks every state and every byte, using no
    generated table to form the reference results.
    """
    serial_after_xor = tuple(advance_byte_bitwise(value, 0) for value in range(65536))
    words = TABLE_WORDS
    checked = 0
    for state in range(65536):
        low, high = state & 255, state >> 8
        for byte in range(256):
            actual = words[low ^ byte] ^ high
            expected = serial_after_xor[state ^ byte]
            if actual != expected:
                raise AssertionError((state, byte, actual, expected))
            checked += 1
    return checked


def self_test() -> dict:
    pairs = exhaustive_transition_check()
    assert TABLE_LOW[0x54] == 0x01 and TABLE_HIGH[0x54] == 0xFF
    assert advance_byte_bitwise(VIRTUAL_ZERO_SEED, 0) == INITIAL_CRC
    packets = [bytes([value]) * length for length in range(9) for value in range(256)]
    packets.extend([bytes(range(8)), b"123456789", bytes([0xFF, 0, 0x7F, 0xFE])])
    for payload in packets:
        assert pipeline_crc(payload) == crc_bitwise(payload)
        frame = payload + wire_crc(payload)
        for pid in (0, 0xC3, 0x4B):
            assert pipeline_crc(frame, pid_latch=pid) == DATA_RESIDUAL
    return {"state_byte_pairs": pairs, "payload_vectors": len(packets),
            "virtual_zero_seed": hex(VIRTUAL_ZERO_SEED),
            "raw_data_residual": hex(DATA_RESIDUAL), "table_bytes": 512,
            "table_sha256": hashlib.sha256(TABLE_LOW + TABLE_HIGH).hexdigest(),
            "timing_proof": "not established by CRC arithmetic tests"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write generated assembler table data")
    parser.add_argument("--self-test", action="store_true", help="run exhaustive arithmetic proof")
    args = parser.parse_args()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_assembly(), encoding="ascii", newline="\n")
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
    elif not args.output:
        print(render_assembly(), end="")


if __name__ == "__main__":
    main()
