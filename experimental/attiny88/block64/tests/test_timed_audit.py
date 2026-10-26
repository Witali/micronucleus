"""Timed-opcode mutations must fail the build audit, regardless of size."""
from pathlib import Path
import sys

import pytest

from avr_sim import syms

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from usb_transaction_audit import audit_timed_instructions


@pytest.mark.parametrize('label,offset', [
    ('usb_crc16_append', 0), ('USB_handler', 0), ('L1c66', 0),
    ('L1cb2', -2),
])
def test_reject_changed_timed_opcode_or_address_commit(label, offset):
    symbols = syms()
    raw = bytearray((ROOT/'build/block64.full.bin').read_bytes())
    address = symbols[label]+offset
    raw[address:address+2] = b'\x00\x00'
    with pytest.raises(AssertionError):
        audit_timed_instructions(bytes(raw), symbols)
