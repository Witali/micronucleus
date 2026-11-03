"""Measure the emitted normal-cell loop; this does not build a USB loader."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests35 import ep0_model as h


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patterns', type=int, default=4096,
                        help='Number of 12-bit patterns, from 1 through 4096')
    args = parser.parse_args()
    if not 1 <= args.patterns <= 4096:
        parser.error('--patterns must be between 1 and 4096')
    SOURCE = Path(__file__).with_name('sampler_probe.S').read_text()
    source_dir = ROOT / 'build/raw_loop_probe'
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / 'micronucleus_t88_compact.S').write_text(SOURCE)
    art = h.build(source='build/raw_loop_probe', boot=0x1b00)


    def outside(value):
        return (value & 1) | ((value & 62) << 2)


    class SequenceIO(dict):
        def __init__(self, values):
            self.values = values
            self.reads = []

        def get(self, address, default=0):
            if address == 9:
                value = self.values[len(self.reads)]
                self.reads.append(value)
                return value
            return super().get(address, default)


    phases = [art['symbols']['raw_loop_phase' + str(index)] for index in range(3)]
    stuffs = [art['symbols']['raw_loop_stuff' + str(index)] for index in range(3)]
    eop = art['symbols']['raw_loop_eop']
    cases = 0
    sample_cells = 0
    stuff_exits = 0
    for value in range(args.patterns):
        for noise in (0, 21, 42, 63):
            bits = [(value >> index) & 1 for index in range(12)]
            line = h.J
            levels = []
            for bit in bits:
                if not bit:
                    line = h.K if line == h.J else h.J
                levels.append(line)
            raw = [level | outside((noise + 17 * index) & 63)
                   for index, level in enumerate(level for line in levels for level in (line, line))]
            cpu = h.CPU(art, h.Wave(b''), 0)
            cpu.io = SequenceIO(raw)
            cpu.r[16] = h.J | outside(noise)
            cpu.r[18] = 0
            cpu.r[0] = 0xa7
            cpu.r[1] = 0
            cpu.r[20] = 0xb9
            expected = 0
            count = 0
            previous_pc = None
            while count < len(bits):
                assert cpu.steps < 200, 'Normal-cell instruction bound'
                if cpu.pc == eop:
                    raise AssertionError('Pristine nonzero line entered EOP cold path')
                if cpu.pc in stuffs:
                    assert expected >= 0xfc and cpu.r[18] == expected
                    stuff_exits += 1
                    break
                if cpu.pc in phases and cpu.pc != previous_pc:
                    phase = count % 3
                    assert cpu.pc == phases[phase]
                    assert cpu.t == 32 * (count // 3) + (0, 10, 21)[phase]
                    assert cpu.r[18] == expected
                    assert cpu.r[(16, 19, 17)[phase]] == (
                        raw[2 * count - 1] if count else h.J | outside(noise))
                    if count:
                        sample_cells += 1
                    expected = (expected >> 1) | (bits[count] << 7)
                    count += 1
                previous_pc = cpu.pc
                cpu.step()
            # Complete the final decoded cell before checking its retained byte.
            while cpu.pc not in phases + stuffs:
                assert cpu.pc != eop
                cpu.step()
            assert cpu.r[18] == expected
            assert cpu.r[0] == 0xa7 and cpu.r[1] == 0 and cpu.r[20] == 0xb9
            cases += 1

    report = dict(bytes=art['size'], sha256=art['sha256'], source_sha256=hashlib.sha256(SOURCE.encode()).hexdigest(),
                  cases=cases, checked_intercell_boundaries=sample_cells,
                  six_one_exits=stuff_exits,
                  normal_first_sample_clocks=[0, 10, 21, 32, 42, 53, 64],
                  normal_second_sample_offset=2,
                  claim='The emitted normal loop uses its history branch as the 10/11/11 back edge.',
                  limits=['No byte counter, publication, stuffed-symbol continuation or EOP qualification.',
                          'No SYNC acquisition or analog/waveform qualification; this is not a loader.'])
    directory = ROOT / 'build/raw_loop_schedule'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (directory / 'probe.S').write_text(SOURCE)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
