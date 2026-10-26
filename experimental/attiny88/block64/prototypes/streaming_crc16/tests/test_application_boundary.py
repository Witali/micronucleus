"""Keep the standalone receiver trial inside the old application boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys

PROTOTYPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTOTYPE/'tools'))
from verify_streaming import load_build, TraceCPU


def manifest():
    return Path(os.environ.get('STREAMING_CRC_MANIFEST',
                              str(PROTOTYPE/'build/streaming-v2/manifest.json')))


def test_hex_records_protect_the_installed_bootloader_and_restore_entry():
    meta = json.loads(manifest().read_text())
    written = {}
    ended = False
    for line in (manifest().parent/'application.hex').read_text().splitlines():
        raw = bytes.fromhex(line[1:])
        assert line.startswith(':') and len(raw) == raw[0]+5
        assert sum(raw) % 256 == 0 and not ended
        address = int.from_bytes(raw[1:3], 'big')
        if raw[3] == 1:
            assert raw[0] == 0
            ended = True
            continue
        assert raw[3] == 0
        for offset, value in enumerate(raw[4:-1]):
            location = address+offset
            assert 0 <= location < 0x1AFC
            assert location not in written
            written[location] = value
    assert ended and meta['protected_boot_address'] == 0x1B00
    assert bytes(written[i] for i in (0, 1)) == b'\x3f\xc0'
    # This source RESET goes to 0x0080; its trampoline goes to 0x0800.
    assert bytes(written[i] for i in (0x80, 0x81)) == b'\xbf\xc3'


def test_inactivity_cannot_jump_to_an_unrelated_postscript():
    build = load_build(manifest())
    assert build['manifest']['inactivity_application_jump_enabled'] is False
    cpu = TraceCPU(build, {'memory':bytearray(0x300), 'registers':[0]*32})
    cpu.pc = cpu.labels['prototype_disabled_autoexit']
    instruction = cpu.step()
    assert instruction.op == 'nop'
    assert cpu.pc != cpu.labels['L1eac']


def test_all_vendor_mutations_are_rejected_before_dispatch():
    build = load_build(manifest())
    for opcode in (0x11, 0x13, 0x14):
        registers = [0]*32
        registers[25] = opcode
        cpu = TraceCPU(build, {'memory':bytearray(0x300),
                               'registers':registers})
        cpu.pc = cpu.labels['block_vendor_out']
        instruction = cpu.step()
        assert instruction.op == 'rjmp'
        assert cpu.pc == cpu.labels['block_vendor_reject']


def test_linked_application_has_no_nvm_programming_instructions():
    listing = subprocess.check_output(
        ['llvm-objdump', '-d', str(manifest().parent/'application.o')], text=True)
    import re
    assert not re.search(r'\bspm\b', listing)
    assert not re.search(r'\bsbi\s+(?:0x1f|31),\s*1\b', listing)
