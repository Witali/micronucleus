"""Verify the one-clock descriptor-selector reduction on one frozen image pair.

Each JSON object provides boot, size, sha256, obj and bin. File paths may be
absolute or relative to that manifest. The bin file contains the unpadded body;
the ELF .text must contain precisely its zero prefix and those same bytes.
This executes the unchanged offline AVR model, never an attached USB device.
"""
from pathlib import Path
from itertools import product
import argparse
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_standard import Quiet, request


def command(arguments):
    return subprocess.check_output(arguments)


def load(manifest):
    """Validate body, ELF and symbol identities before interpreting opcodes."""
    manifest = manifest.resolve()
    art = json.loads(manifest.read_text())
    assert isinstance(art, dict), 'Expected one frozen artifact object'
    for field in ('obj', 'bin'):
        path = Path(art[field])
        art[field] = (path if path.is_absolute() else manifest.parent / path).resolve()
    art['body'] = art['bin'].read_bytes()
    assert 0 <= art['boot'] < 8192
    assert len(art['body']) == art['size'] and art['boot'] + art['size'] <= 8192
    assert hashlib.sha256(art['body']).hexdigest() == art['sha256'], 'Body identity changed'
    art['elf_sha256'] = hashlib.sha256(art['obj'].read_bytes()).hexdigest()
    exported = command(['llvm-objcopy', '-O', 'binary', '-j', '.text', str(art['obj']), '-'])
    assert exported == bytes(art['boot']) + art['body'], 'ELF text and frozen body differ'
    symbols = {}
    for line in command(['llvm-objdump', '-t', str(art['obj'])]).decode().splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[2] == '.text':
            symbols[fields[-1]] = int(fields[0], 16)
    if 'symbols' in art:
        assert all(symbols.get(name) == address for name, address in art['symbols'].items()), \
            'Manifest contains stale symbol addresses'
    art['symbols'] = symbols
    return art


def select_time(art, kind):
    """Measure actual cycles from descriptor guard to reply-pointer or STALL."""
    bind(art)
    cpu = h.CPU(art, Quiet(), 0)
    cpu.pc = art['symbols']['usb_standard_check_get_descriptor']
    cpu.r[3] = 0
    cpu.r[12:16] = [0, kind, 0, 0]
    cpu.r[24:26] = [0x80, 6]
    for _ in range(100):
        if cpu.pc == art['symbols']['usb_reply_use_flash_pointer']:
            return 'reply', cpu.t
        if cpu.pc == art['symbols']['usb_standard_stall']:
            return 'stall', cpu.t
        cpu.step()
    raise AssertionError('Descriptor selector did not finish')


def compare(before, after):
    """Retain all 2078 field cases and all 256 selector-time comparisons."""
    assert before['boot'] == after['boot'], 'Compare images at the same placement'
    cases = [(kind, 0, 0, length, config)
             for kind, length, config in product(range(256), (0, 1, 18, 256), (0, 1))]
    cases += [(kind, low, index, 18, 1)
              for kind, low, index in product((1, 2), (0, 1, 2, 255), (0, 1, 0x80, 0x100))
              if low or index]
    results = []
    for art in (before, after):
        rows = []
        for kind, low, index, length, config in cases:
            row = request(art, 0x80, 6, value=(kind << 8) | low,
                          index=index, length=length, config=config)
            valid = kind in (1, 2) and low == 0 and index == 0
            assert row['kind'] == ('reply' if valid else 'stall')
            if valid:
                assert row['count'] == min(length, 18)
            rows.append(row)
        results.append(rows)
    assert results[0] == results[1], 'Externally visible descriptor behavior changed'
    timings = []
    for kind in range(256):
        old_kind, old_time = select_time(before, kind)
        new_kind, new_time = select_time(after, kind)
        assert old_kind == new_kind == ('reply' if kind in (1, 2) else 'stall')
        assert old_time - new_time == 1, 'Descriptor selector did not save exactly one clock'
        timings.append(dict(type=kind, kind=new_kind, before=old_time, after=new_time,
                            saved=old_time-new_time))
    for art in (before, after):
        assert hashlib.sha256(art['bin'].read_bytes()).hexdigest() == art['sha256']
        assert hashlib.sha256(art['obj'].read_bytes()).hexdigest() == art['elf_sha256']
    return dict(before_bytes=before['size'], after_bytes=after['size'],
                before_sha256=before['sha256'], after_sha256=after['sha256'],
                before_elf_sha256=before['elf_sha256'], after_elf_sha256=after['elf_sha256'],
                boot=before['boot'], request_cases_per_image=len(cases),
                compared_images=2, all_type_bytes=256, selector_timings=timings,
                body_and_elf_rechecked=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True, help='Frozen before artifact manifest')
    parser.add_argument('--after', type=Path, required=True, help='Frozen after artifact manifest')
    parser.add_argument('--report', type=Path, help='JSON output; default is an ignored build path')
    args = parser.parse_args()
    before, after = load(args.before), load(args.after)
    report = compare(before, after)
    output = args.report or ROOT / 'build/descriptor_compare' / \
        (before['sha256'][:12] + '-' + after['sha256'][:12] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(before_bytes=report['before_bytes'], after_bytes=report['after_bytes'],
                          request_cases_per_image=report['request_cases_per_image'],
                          selector_time_cases=len(report['selector_timings']),
                          clocks_saved=1, report=str(output)), indent=2))


if __name__ == '__main__':
    main()
