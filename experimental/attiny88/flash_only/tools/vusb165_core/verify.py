"""Execute the emitted experimental RX core against bounded independent GPIO.

This is a centered-entry component test. It does not qualify SYNC, malformed
stuffing/EOP, USB protocol effects, analogue behavior or a hardware loader.
"""
from pathlib import Path
from bisect import bisect_right
from collections import Counter
import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys

BOOT = 0x1b00


def build(source, output):
    """Use linked physical AVR instructions, never LLVM relocation words."""
    output.mkdir(parents=True, exist_ok=True)
    reloc, elf = output / 'receiver.reloc.o', output / 'receiver.elf'
    full, body = output / 'receiver.full.bin', output / 'receiver.body.bin'
    def command(args):
        return subprocess.check_output(args, text=True)
    command(['clang', '-target', 'avr', '-mmcu=attiny88', '-x', 'assembler-with-cpp',
             '-c', str(source), '-o', str(reloc)])
    command(['avr-ld', '-m', 'avr25', '-Ttext=0', '-e', 'bootloader_start',
             '-o', str(elf), str(reloc)])
    if 'R_AVR_' in command(['llvm-objdump', '-r', str(elf)]):
        raise AssertionError('Execution object still contains AVR relocations')
    command(['llvm-objcopy', '-O', 'binary', '-j', '.text', str(elf), str(full)])
    image = full.read_bytes()
    assert image[:BOOT] == bytes(BOOT)
    payload = image[BOOT:]
    assert BOOT + len(payload) <= 8192
    body.write_bytes(payload)
    symbols = {}
    for line in command(['llvm-nm', '-n', str(elf)]).splitlines():
        columns = line.split()
        if len(columns) == 3:
            symbols[columns[2]] = int(columns[0], 16)
    return dict(boot=BOOT, body=payload, obj=elf, bin=body, symbols=symbols,
                size=len(payload), sha256=hashlib.sha256(payload).hexdigest())


class GPIO(dict):
    """Independent NRZI/stuffed-symbol encoder with synchronized GPIO aperture."""
    def __init__(self, cpu, value, rate, sign, *, pulse=None, repeat=False):
        super().__init__()
        self.cpu = cpu
        period = 16_000_000 / rate
        start = .5 - period / 2
        bits = []
        ones = 0
        for byte in bytes([value]) * 24:
            for i in range(8):
                bit = (byte >> i) & 1
                bits.append(bit)
                ones = ones + 1 if bit else 0
                if ones == 6:
                    bits.append(0)
                    ones = 0
        self.times, self.levels = [], []
        line = 2
        for i, bit in enumerate(bits):
            if not bit:
                line = 4 if line == 2 else 2
            self.times.append(start + i * period + sign * (.55 if line == 2 else -.55))
            self.levels.append(line)
        if pulse is not None:
            observed, fraction = pulse
            indexes = [i for i in range(1, len(bits)) if self.levels[i] != self.levels[i - 1]]
            selected = indexes if repeat else [next(i for i in indexes if i >= 20)]
            for i in reversed(selected):
                t, level = self.times[i], self.levels[i]
                self.times[i:i + 1] = [t - 3.36 * fraction, t + 3.36 * (1 - fraction)]
                self.levels[i:i + 1] = [observed, level]

    def get(self, address, default=0):
        if address == 9:
            when = self.cpu.t - .5 + 1e-7
            index = bisect_right(self.times, when) - 1
            return self.levels[index] if index >= 0 else 2
        return super().get(address, default)


def execute(h, art, value, rate, sign, raw_register, pulse=None, repeat=False):
    """Check payload and live foreground registers after every actual opcode."""
    cpu = h.CPU(art, h.Wave(b''), 0)
    cpu.pc = art['symbols']['rxLoop']
    cpu.io = GPIO(cpu, value, rate, sign, pulse=pulse, repeat=repeat)
    cpu.r[16] = 0xff
    cpu.r[17] = 3
    cpu.r[19] = 2
    cpu.r[20] = 0xff
    cpu.r[21] = 0
    cpu.r[22] = 255
    cpu.r[raw_register] = 2
    cpu.r[28:32] = [0, 1, 0, 1]
    protected = {24: 0xb6, 25: 0xc7}
    if raw_register == 23:
        protected[0] = 0xa7
        cpu.r[23] = 0x5a  # First reference must not depend on incoming scratch.
    for register, initial in protected.items():
        cpu.r[register] = initial
    entries = []
    for _ in range(30000):
        if cpu.pc == art['symbols']['rxLoop']:
            entries.append(cpu.t)
            if len(entries) == 13:
                break
        if cpu.pc == art['symbols']['se0'] or cpu.pc == 0xfffe:
            return dict(passed=False, early_exit=True, time=cpu.t)
        cpu.step()
        for register, expected in protected.items():
            assert cpu.r[register] == expected, ('Foreground register clobbered', register)
    else:
        raise AssertionError('Receive-core execution bound')
    published = bytes(cpu.m[0x101:0x10c])
    return dict(passed=published == bytes([value]) * 11, early_exit=False,
                published=published.hex(),
                periods=[entries[i + 1] - entries[i] for i in range(len(entries) - 1)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument('--root', type=Path, default=default_root,
                        help='Repository experimental/attiny88/flash_only directory')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--raw-register', type=int, choices=(0, 23), default=23)
    parser.add_argument('--all-byte-values', action='store_true')
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / 'tests35/ep0_model.py').is_file():
        parser.error('--root must contain the maintained tests35 executor')
    os.environ['MICRONUCLEUS_TEST_MODEL_ROOT'] = str(root.parent / 'compact')
    sys.path.insert(0, str(root))
    h = importlib.import_module('tests35.ep0_model')
    source = args.source.resolve()
    output = args.output.resolve()
    art = build(source, output)
    if args.expected_sha256 and art['sha256'] != args.expected_sha256:
        raise AssertionError('Compiler output differs from the selected frozen body')
    report = dict(bytes=art['size'], sha256=art['sha256'], raw_register=args.raw_register,
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  protected_registers=[0, 24, 25] if args.raw_register == 23 else [24, 25],
                  scope='Centered-entry RX component only; no SYNC/EOP/protocol qualification',
                  model_sha256={p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in
                                ('tests35/ep0_model.py', 'tests35/avr_cycles.py')}, results=[])
    def check(group, **context):
        result = execute(h, art, raw_register=args.raw_register, **context)
        report['results'].append(dict(group=group, **context, **result))
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
    if args.all_byte_values:
        for value in range(256):
            for rate in (1499250, 1500000, 1500750):
                for sign in (-1, 0, 1):
                    check('all_values_pristine', value=value, rate=rate, sign=sign)
    failures = [r for r in report['results'] if not r['passed']]
    summary = dict(bytes=art['size'], sha256=art['sha256'], cases=len(report['results']),
                   groups=dict(Counter(r['group'] for r in report['results'])),
                   failures=len(failures), failure_groups=dict(Counter(r['group'] for r in failures)),
                   first_failure=failures[0] if failures else None)
    report['summary'] = summary
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summary), flush=True)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
