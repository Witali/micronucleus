"""Prove emitted byte publication/count clocks, not a full USB receiver."""
from pathlib import Path
from itertools import product
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'build/raw_publication_probe'
sys.path.insert(0, str(ROOT))
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from publication_schedule import write_probe


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def build():
    """Link real AVR words inside physical Flash and retain their exact identity."""
    source = write_probe(OUTPUT)
    reloc, obj, full, body = (OUTPUT / name for name in
                              ('probe.reloc.o', 'probe.o', 'probe.full.bin', 'probe.body.bin'))
    boot = 0x1b00
    run(['clang', '-target', 'avr', '-mmcu=attiny88', f'-DBOOT_AT={boot}',
         '-x', 'assembler-with-cpp', '-c', str(source), '-o', str(reloc)])
    run(['avr-ld', '-m', 'avr25', '--defsym=__TEXT_REGION_LENGTH__=0x2000',
         '-Ttext=0', '-e', 'bootloader_start', '-o', str(obj), str(reloc)])
    assert 'R_AVR_' not in run(['llvm-objdump', '-r', str(obj)])
    run(['llvm-objcopy', '-O', 'binary', '-j', '.text', str(obj), str(full)])
    blob = full.read_bytes()
    assert blob[:boot] == bytes(boot) and len(blob) <= 8192
    body.write_bytes(blob[boot:])
    symbols = {}
    for line in run(['llvm-objdump', '-t', str(obj)]).splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[2] == '.text':
            symbols[fields[-1]] = int(fields[0], 16)
    art = dict(boot=boot, body=blob[boot:], size=len(blob)-boot, obj=obj,
               bin=body, symbols=symbols, sha256=hashlib.sha256(blob[boot:]).hexdigest())
    (OUTPUT / 'artifact.json').write_text(json.dumps(
        {k: str(v) if isinstance(v, Path) else v for k, v in art.items() if k != 'body'}, indent=2))
    (OUTPUT / 'disassembly.txt').write_text(run(['llvm-objdump', '-d', str(obj)]))
    assert art['size'] == 520
    assert art['sha256'] == '9acb54d3b75fa0417b61144b1bb0bd6a902bdc0e030a9f813fc40b6acf07e984'
    return art


def outside(value):
    return (value & 1) | ((value & 62) << 2)


class SequenceIO(dict):
    """Supply raw roles while recording actual emitted IN instruction clocks."""
    def __init__(self, cpu, raw):
        super().__init__()
        self.cpu, self.raw, self.reads, self.times = cpu, raw, [], []

    def get(self, address, default=0):
        if address == 9:
            assert len(self.reads) < len(self.raw), 'Read beyond test waveform'
            value = self.raw[len(self.reads)]
            self.reads.append(value)
            self.times.append(self.cpu.t)
            return value
        return super().get(address, default)


def check(art, phase, remaining, noise, data, tail, pending=0xc3):
    """Check rolling history, every store, counter retirement and preserved owners."""
    bind(art)
    cpu = h.CPU(art, h.Wave(b''), 0)
    cpu.pc = art['symbols'][f'byte{phase}_bit0']
    cpu.r[18] = pending
    cpu.r[23] = 0x7f + remaining
    cpu.r[28:30] = [0x16, 1]
    cpu.r[0], cpu.r[1], cpu.r[20:23] = 0xa7, 0, [0xb9, 0xca, 0xdb]
    cpu.r[24:26] = [0xd3, 0xe4]
    previous_role = (16, 19, 17)[phase]
    cpu.r[previous_role] = h.J | outside(noise)
    cpu.flags = (noise * 37) & 255
    source = bytes([data] * (remaining - 1))
    bits = [(byte >> bit) & 1 for byte in source for bit in range(8)] + list(tail)
    line = h.J
    raw = []
    for bit in bits:
        if not bit:
            line = h.K if line == h.J else h.J
        for _ in range(2):
            raw.append(line | outside((noise + 17 * len(raw)) & 63))
    cpu.io = SequenceIO(cpu, raw)
    cells = {address: name for name, address in art['symbols'].items() if name.startswith('byte')}
    cold = {address for name, address in art['symbols'].items() if name.startswith('cold_group')}
    expected = pending
    pending_bytes = bytes([pending]) + source
    stored = 0
    index = 0
    expected_time = 0
    decoded = 0
    last_cell = None
    current_bit = None
    last_boundary_first = None
    full_entry = None
    first_clocks = []
    for _ in range(2000):
        if cpu.pc in (art['symbols']['full_tail_ones'], art['symbols']['full_tail_invalid']):
            assert stored == remaining and decoded == len(bits)
            assert cpu.r[23] == 0x7f and cpu.r[28:30] == [0x16 + remaining, 1]
            valid = cpu.pc == art['symbols']['full_tail_ones']
            assert valid == (tail == (1, 1))
            assert bytes(cpu.m[0x116:0x116+remaining]) == pending_bytes
            assert cpu.r[0:2] == [0xa7, 0] and cpu.r[20:23] == [0xb9, 0xca, 0xdb]
            assert cpu.r[24:26] == [0xd3, 0xe4] and cpu.r[30:32] == [0, 1]
            assert cpu.io.times == [value for clock in first_clocks for value in (clock, clock+2)]
            return dict(stores=stored, cells=decoded, valid=valid, cold=False,
                        full_entry_after_boundary=full_entry-last_boundary_first,
                        full_classified_after_boundary=cpu.t-last_boundary_first)
        if cpu.pc in cold:
            assert last_cell is not None
            bit = int(last_cell.rsplit('bit', 1)[1])
            assert expected >= (0xf0 if bit == 7 else 0xfc)
            assert cpu.r[18] == expected
            assert bytes(cpu.m[0x116:0x116+stored]) == pending_bytes[:stored]
            assert cpu.io.times == [value for clock in first_clocks for value in (clock, clock+2)]
            return dict(stores=stored, cells=decoded, valid=False, cold=True)
        if cpu.pc == art['symbols']['full_validate']:
            full_entry = cpu.t
        if cpu.pc in cells:
            name = cells[cpu.pc]
            assert name == f'byte{(phase + 8 * (index // 8)) % 3}_bit{index % 8}', (name, index, phase)
            assert cpu.t == expected_time, (name, cpu.t, expected_time)
            first_clocks.append(cpu.t)
            assert cpu.r[18] == expected, (name, cpu.r[18], expected)
            role = (16, 19, 17)[(phase + index) % 3]
            assert cpu.r[role] == (raw[2 * index - 1] if index else h.J | outside(noise))
            last_cell = name
            current_bit = bits[index]
            if index % 8 == 0:
                last_boundary_first = cpu.t
            expected_time += (10, 11, 11)[(phase + index) % 3]
            index += 1
        pc = cpu.pc
        ins = cpu.step()
        if ins.op == 'st':
            assert stored < remaining, 'Twelfth or excess byte store'
            assert cpu.t == last_boundary_first + 6, 'Publication moved the sample schedule'
            assert cpu.r[28:30] == [0x16 + stored + 1, 1]
            assert cpu.m[0x116 + stored] == pending_bytes[stored]
            stored += 1
        if ins.op == 'ror':
            expected = (expected >> 1) | (current_bit << 7)
            decoded += 1
            assert cpu.r[18] == expected
    raise AssertionError('Publication/count instruction bound')



def main():
    art = build()
    cases = stores = boundaries = cold_cases = valid_tails = 0
    terminal_entries = {phase: set() for phase in range(3)}
    terminal_classifications = {phase: set() for phase in range(3)}
    for phase, remaining, noise, data, tail in product(
            range(3), range(1, 12), (0, 21, 42, 63), (0, 0x55, 0xaa, 0x33),
            ((0, 0), (0, 1), (1, 0), (1, 1))):
        result = check(art, phase, remaining, noise, data, tail)
        assert not result['cold']
        cases += 1
        stores += result['stores']
        boundaries += result['cells']
        valid_tails += result['valid']
        exit_phase = (phase + 8 * (remaining - 1)) % 3
        terminal_entries[exit_phase].add(result['full_entry_after_boundary'])
        terminal_classifications[exit_phase].add(result['full_classified_after_boundary'])
    # Exercise the strongest admitted boundary histories and the deferred live test.
    for phase, noise, pending in product(range(3), (0, 63), (0xe0, 0xe7, 0xef)):
        result = check(art, phase, 11, noise, 0xff, (1, 1), pending=pending)
        assert result['cold'] and result['cells'] == 3
        cold_cases += 1
    boundary_cold_cases = 0
    for phase, noise, data in product(range(3), (0, 63), range(0xf0, 0x100)):
        result = check(art, phase, 2, noise, data, (1, 1))
        assert result['cold'] and result['stores'] == 1 and result['cells'] <= 8
        boundary_cold_cases += 1
    report = dict(bytes=art['size'], sha256=art['sha256'], publication_cases=cases,
                  byte_stores=stores, decoded_cells=boundaries, valid_two_one_tail_cases=valid_tails,
                  deferred_history_cases=cold_cases, phases=3, remaining_counts=list(range(1, 12)),
                  boundary_lookahead_cold_cases=boundary_cold_cases,
                  full_dispatch_clocks_after_boundary={p: sorted(v) for p, v in terminal_entries.items()},
                  full_classification_clocks_after_boundary={p: sorted(v) for p, v in terminal_classifications.items()},
                  count_encoding='remaining + 0x7f; full=0x7f; no twelfth store',
                  cadence='FIRST 0/10/21/32 with SECOND +2, modulo entry phase',
                  limits=['24 explicitly unrolled logical-cell states; size is not a complete receiver.',
                          'F0 histories exit to cold stubs; stuffing/EOP/acquisition are not implemented.',
                          'Full dispatch is one clock after the next ordinary FIRST; classification is later still.',
                          'The two-bit full-tail classifier is not qualified EOP or packet admission.'])
    (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
