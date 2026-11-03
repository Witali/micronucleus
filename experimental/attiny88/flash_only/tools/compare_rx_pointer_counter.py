"""Compare linked RX countdown and pointer-limit continuations without rebuilding.

Supply frozen artifact.json manifests from before and after this optimization.
This characterizes three instruction joins; it is not a USB receiver gate.
"""
from pathlib import Path
from itertools import product
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests35 import ep0_model as h
from tests35.ep0_cases import bind


def load(path):
    """Require the recorded body identity and physical ATtiny88 execution range."""
    art = json.loads(path.read_text())
    for key in ('obj', 'bin'):
        value = art[key]
        if sys.platform == 'win32' and value.startswith('/mnt/c/'):
            value = 'C:/' + value[7:]
        art[key] = Path(value)
    art['body'] = art['bin'].read_bytes()
    assert len(art['body']) == art['size']
    assert hashlib.sha256(art['body']).hexdigest() == art['sha256']
    assert 0 <= art['boot'] < art['boot'] + art['size'] <= 8192
    return art


class Pins(dict):
    """Record actual IN clocks while keeping arbitrary non-USB inputs visible."""
    def __init__(self, cpu, level):
        super().__init__()
        self.cpu, self.level, self.samples = cpu, level, []

    def get(self, address, default=0):
        if address == 9:
            self.samples.append((self.cpu.t, self.level))
            return self.level
        return super().get(address, default)


def positions(art, word):
    body = art['body']
    return [art['boot'] + offset for offset in range(0, len(body), 2)
            if int.from_bytes(body[offset:offset + 2], 'little') == word]


def execute(art, pc, committed, fraction, level, flags, history):
    """Stop after carry has been overwritten and the first payload ROR joins."""
    bind(art)
    cpu = h.CPU(art, h.Wave(b''), 0)
    cpu.r[:] = [(index * 23 + 7) & 255 for index in range(32)]
    cpu.r[1], cpu.r[18], cpu.r[21] = 0, history, fraction & 255
    cpu.r[23] = 11 - committed
    cpu.r[28:32] = [0x16 + committed, 1, 0, 1]
    cpu.flags, cpu.pc = flags, pc
    cpu.io = Pins(cpu, level)
    for _ in range(60):
        instruction = cpu.step()
        if instruction.op == 'ror':
            registers = cpu.r[:]
            # R23 is retired scratch here; packet length is recomputed at EOF.
            # Compare all other registers and every SREG flag, without masks.
            registers[23] = None
            return dict(registers=registers, flags=cpu.flags, time=cpu.t,
                        samples=cpu.io.samples, stack=cpu.raw_stack,
                        bus=cpu.bus_events)
    raise AssertionError('No first decoded shift in bounded join')


def compare(before, after):
    """Check ordinary, odd5 and recovered-odd5 joins for every byte position."""
    # These are exact SUBI R23,1 and CPI YL,0x20 encodings for the reviewed
    # layout (RX start 0x116; the final byte begins with ten bytes committed).
    # Reject another layout instead of silently comparing a different seam.
    old_sites, new_sites = positions(before, 0x5071), positions(after, 0x32c0)
    assert len(old_sites) == len(new_sites) == 3
    cases = 0
    for site, committed, fraction, level, flags, history in product(
            range(3), range(11), range(-3, 4), (2, 4, 0x82),
            (0, 0x55, 0xaa, 0xff), (0, 0x55, 0xfc, 0xff)):
        context = (site, committed, fraction, level, flags, history)
        old = execute(before, old_sites[site], *context[1:])
        new = execute(after, new_sites[site], *context[1:])
        assert old == new, (context, old, new)
        cases += 1
    return dict(cases=cases, sites=3, before_sha256=before['sha256'],
                after_sha256=after['sha256'],
                scope='Comparator through first ROR: clocks, GPIO reads, SREG, live registers, stack and bus writes; retired R23 excluded')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    args = parser.parse_args()
    report = compare(load(args.before), load(args.after))
    output = ROOT / 'build/rx_pointer_counter'
    output.mkdir(parents=True, exist_ok=True)
    (output / (report['after_sha256'][:16] + '.json')).write_text(
        json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
