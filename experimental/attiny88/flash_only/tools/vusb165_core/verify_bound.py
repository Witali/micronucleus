"""Execute an eleven-byte publication ceiling with an overlength GPIO source.

This is a centered-entry component check. It does not qualify SYNC, EOP,
dribble, arbitrary packet framing, protocol effects, or a hardware loader.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import os
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--all-byte-values', action='store_true')
parser.add_argument('--expected-sha256')
args = parser.parse_args()
root = args.root.resolve()
if not (root / 'tests35/ep0_model.py').is_file():
    parser.error('--root must contain the maintained tests35 executor')
os.environ['MICRONUCLEUS_TEST_MODEL_ROOT'] = str(root.parent / 'compact')
sys.path.insert(0, str(root))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tests35 import ep0_model as h
from verify import build, GPIO
source, output = args.source.resolve(), args.output.resolve()
art = build(source, output)
if args.expected_sha256 and art['sha256'] != args.expected_sha256:
    raise AssertionError('Compiler output differs from the selected frozen body')

def execute(value, rate, sign, pulse=None, repeat=False):
    cpu = h.CPU(art, h.Wave(b''), 0)
    cpu.pc = art['symbols']['rxLoop']
    cpu.io = GPIO(cpu, value, rate, sign, pulse=pulse, repeat=repeat)
    cpu.r[16] = 0xff
    cpu.r[17] = 3
    cpu.r[19] = 2
    cpu.r[20] = 0x5a ^ 0xff
    cpu.r[21] = 0
    cpu.r[22] = 0x91
    cpu.r[23] = 0x62
    cpu.r[28:32] = [0x15, 1, 0, 1]
    protected = {i: ((i * 19 + 0x27) & 255) for i in range(2, 16)}
    protected.update({0: 0xa7, 1: 0, 22: 0x91, 24: 0xb6, 25: 0xc7})
    for register, initial in protected.items():
        cpu.r[register] = initial
    cpu.m[0x115] = 0x5a
    cpu.m[0x121:0x12a] = bytes([0x6d]) * 9
    overflow = False
    for _ in range(30000):
        if cpu.pc == art['symbols']['overflow']:
            # SE0 and overflow share RET in this component. Require the
            # actual bit2 BRSH predecessor, not merely that shared address.
            overflow |= cpu.executing_pc == art['symbols']['rx_bound_overflow_branch']
        if cpu.pc == 0xfffe:
            break
        cpu.step()
        for register, expected in protected.items():
            assert cpu.r[register] == expected, ('Live register clobbered', register)
        assert cpu.word(30) == 0x100, 'Context pointer clobbered'
    else:
        raise AssertionError('Bounded RX instruction limit')
    published = bytes(cpu.m[0x116:0x121])
    errors = []
    if published != bytes([value]) * 11:
        errors.append('eleven exact bytes')
    if not overflow:
        errors.append('overflow route')
    if cpu.word(28) != 0x121 or bytes(cpu.m[0x121:0x12a]) != bytes([0x6d]) * 9:
        errors.append('twelfth store or pointer ceiling')
    if cpu.m[0x115] != 0x5a:
        errors.append('configuration dummy store')
    if cpu.raw_stack:
        errors.append('stack balance')
    return dict(passed=not errors, errors=errors, published=published.hex(),
                time=cpu.t, Y=cpu.word(28))

rows = []
def check(group, **context):
    rows.append(dict(group=group, **context, **execute(**context)))
for value in (0x00, 0x15, 0x9f, 0xef, 0xff):
    for rate in (1499250, 1500000, 1500750):
        for sign in (-1, 0, 1):
            check('original_pristine', value=value, rate=rate, sign=sign)
            for observed in (0, 6):
                for fraction in (1/21, .5, 20/21):
                    for repeat in (False, True):
                        check('original_repeat' if repeat else 'original_single',
                              value=value, rate=rate, sign=sign,
                              pulse=(observed, fraction), repeat=repeat)
for value in (0x55, 0xaa, 0x42, 0x03, 0xfc):
    for rate in (1499250, 1500000, 1500750):
        for sign in (-1, 0, 1):
            check('extra_pristine', value=value, rate=rate, sign=sign)
for value in (range(256) if args.all_byte_values else ()):
    for rate in (1499250, 1500000, 1500750):
        for sign in (-1, 0, 1):
            check('all_values_pristine', value=value, rate=rate, sign=sign)
failures = [row for row in rows if not row['passed']]
summary = dict(bytes=art['size'], sha256=art['sha256'],
               source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               cases=len(rows), failures=len(failures),
               groups=dict(Counter(row['group'] for row in rows)),
               first_failure=failures[0] if failures else None,
               scope='Centered component with bounded publication, not qualified EOP/SYNC')
(output / 'verification.json').write_text(json.dumps(dict(summary=summary, rows=rows), indent=2) + '\n')
print(json.dumps(summary), flush=True)
raise SystemExit(bool(failures))
