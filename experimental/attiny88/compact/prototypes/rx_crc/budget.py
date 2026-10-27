"""Enumerate actual RX sample-to-sample paths and pipeline-free cycle slots."""
from collections import defaultdict
import json
import random
from probe import OWN, build, freeze, receive, data_packet


def site(meta, pc):
    labels = [(address, name) for name, address in meta['symbols'].items()
              if name.startswith('usb_rx_') and address <= pc]
    address, name = max(labels)
    return name + (f'+{pc - address}' if pc != address else '')


if __name__ == '__main__':
    meta, manifest = build('baseline', freeze())
    patterns = [bytes([value]) * 8 for value in range(256)]
    patterns += [random.Random(index + 730).randbytes(8) for index in range(128)]
    groups = {}
    checked = 0
    for pid in (0xC3, 0x4B):
        for payload in patterns:
            result = receive(meta, data_packet(payload, pid), trace=True)
            assert result['ok'], result
            samples = [(round(time + .5, 6), pc, cell) for time, pc, level, cell in result['samples']
                       if meta['symbols']['usb_rx_delay_complete'] <= pc < meta['symbols']['usb_rx_overflow']]
            history = result['history']
            for (begin, pc, cell), (end, next_pc, next_cell) in zip(samples, samples[1:]):
                # Physical bit cell index identifies which data/unstuff phase
                # this path sampled. All instructions, including both taken
                # and skipped branches, are represented by emitted opcodes.
                path = [item for item in history if begin < item['time'] <= end]
                names = tuple((item['op'], item['operands']) for item in path)
                key = (site(meta, pc), site(meta, next_pc), round(end - begin, 6), names)
                if key not in groups:
                    groups[key] = dict(source=key[0], target=key[1], cycles=key[2],
                                       instructions=[dict(op=op, operands=operands) for op, operands in names],
                                       count=0, example=dict(pid=hex(pid), payload=payload.hex(), physical_cell=cell, next_cell=next_cell))
                groups[key]['count'] += 1
            checked += 1
    rows = sorted(groups.values(), key=lambda row: (row['source'], row['target'], row['cycles'], str(row['instructions'])))
    summary = defaultdict(set)
    for row in rows:
        summary[(row['source'], row['target'])].add(row['cycles'])
    result = dict(manifest=manifest, packets=checked, path_variants=len(rows),
                  sample_paths=[dict(source=a, target=b, cycles=sorted(cycles)) for (a, b), cycles in sorted(summary.items())],
                  paths=rows)
    (OWN / 'rx-cycle-budget.json').write_text(json.dumps(result, indent=2) + '\n')
    print('packets', checked, 'path variants', len(rows))
    for row in result['sample_paths']:
        print(row)
