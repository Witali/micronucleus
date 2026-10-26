"""Pin timed AVR instructions while allowing reviewed transaction bookkeeping."""
from pathlib import Path
import importlib.util
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parents[2] / 'docs/attiny88-block64-history/archives/Micronucleus_ATtiny88_Block64_ALL_CODE_AGENT_HANDOFF_2026-10-26.zip'
PREFIX = 'Micronucleus_ATtiny88_Block64_COMPLETE_HANDOFF_2026-10-26/02_CURRENT_PASS15_EXPERIMENTAL/firmware/'


def audit_timed_instructions(raw, current):
    with zipfile.ZipFile(ARCHIVE) as archive:
        old_raw = archive.read(PREFIX + 'ISP_FULL_8192_19C0_PASS15.bin')
        text = archive.read(PREFIX + 'symbols.txt').decode()
    old = {name: int(address, 16) for name, address in
           re.findall(r'^(\S+)\s+0x([0-9a-fA-F]+)$', text, re.M)}
    spec = importlib.util.spec_from_file_location('transaction_decoder', ROOT/'tests/avr_decoder.py')
    decoder = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = decoder
    spec.loader.exec_module(decoder)

    def instructions(image, symbols, begin, end):
        decoder.START, decoder.raw = 0, image
        at = begin
        result = []
        while at < end:
            inst = decoder.decode(at)
            assert not inst.unknown, ('Unknown timed opcode', hex(at))
            result.append(inst)
            at += inst.size
        assert at == end
        return result

    def compare(first, last, tail=0, address_commit=False):
        a0, b0 = old[first], current[first]
        a1, b1 = old[last]+tail, current[last]+tail
        previous = instructions(old_raw, old, a0, a1)
        now = instructions(raw, current, b0, b1)
        assert a1-a0 == b1-b0 and len(previous) == len(now)
        for a, b in zip(previous, now):
            if address_commit and a.op == 'std' and a.operands == 'Z+12, r17':
                assert b.op == 'rjmp' and b.size == 2 and b.target == b.address+2
                continue
            assert (a.op, a.operands, a.size) == (b.op, b.operands, b.size), ('Timed instruction changed', hex(b.address))
            if a.target is not None:
                if a0 <= a.target < a1:
                    assert b.target-b0 == a.target-a0
                else:
                    names = [name for name in old if old[name] == a.target and name in current]
                    assert names and any(current[name] == b.target for name in names), ('Timed branch target changed', hex(b.address))
        return b1-b0

    crc = compare('usb_crc16_append', 'USB_handler')
    assert crc == 44
    sampler = compare('USB_handler', 'L1baa')
    transmitter = compare('L1c30', 'L1cc2', 12, address_commit=True)
    return {'crc_bytes': crc, 'sampler_bytes': sampler, 'transmitter_bytes': transmitter,
            'address_commit_slot': 'two-cycle jump; address commits on ACK'}
