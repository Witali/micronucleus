"""Verify zero-clock sharing of the two terminal EOP rejection jumps.

Supply immutable before/after artifact.json files with identical placement.
This compares emitted words and control-flow edges, not USB qualification.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.descriptor_compare import load

def signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value

def cfg_equivalence(before, after):
    """Relate every named instruction and its emitted successor graph.

    Edges include both conditional outcomes, both skip outcomes, calls and
    call-return continuations. Ordinary opcodes and immediates must match
    exactly. Only encoded direct control-transfer displacements may differ.
    This tests the binary graph, rather than assuming source relocation works.
    """
    def word(art, pc):
        offset = pc - art['boot']
        assert 0 <= offset < art['size'] - 1, ('outside image', pc)
        return int.from_bytes(art['body'][offset:offset + 2], 'little')
    def size(art, pc):
        op = word(art, pc)
        return 4 if op & 0xfe0e in (0x940c, 0x940e) or op & 0xfe0f in (0x9000, 0x9200) else 2
    roots = [(before['symbols'][name], after['symbols'][name])
             for name in sorted(before['symbols'])
             if before['boot'] <= before['symbols'][name] < before['boot'] + before['size']]
    pending = roots[:]
    relation = {}
    edges = 0
    while pending:
        bpc, apc = pending.pop()
        if bpc in relation:
            assert relation[bpc] == apc, ('inconsistent relation', hex(bpc), hex(apc), hex(relation[bpc]))
            continue
        relation[bpc] = apc
        bw, aw = word(before, bpc), word(after, apc)
        bs, az = size(before, bpc), size(after, apc)
        assert bs == az
        def add(b, a):
            nonlocal edges
            if not (before['boot'] <= b < before['boot'] + before['size']):
                assert b == a, ('external target changed', hex(bpc), hex(apc), hex(b), hex(a))
                assert b in (0, before['boot'] - 4), ('unexpected external target', hex(bpc), hex(b))
                edges += 1
                return
            pending.append((b, a))
            edges += 1
        if bw & 0xf000 in (0xc000, 0xd000):
            assert bw & 0xf000 == aw & 0xf000
            add(bpc + 2 + 2 * signed(bw & 0xfff, 12), apc + 2 + 2 * signed(aw & 0xfff, 12))
            if bw & 0xf000 == 0xd000:
                add(bpc + 2, apc + 2)
        elif bw & 0xfc00 in (0xf000, 0xf400):
            assert bw & 0xfc07 == aw & 0xfc07
            add(bpc + 2 + 2 * signed((bw >> 3) & 127, 7), apc + 2 + 2 * signed((aw >> 3) & 127, 7))
            add(bpc + 2, apc + 2)
        else:
            assert before['body'][bpc-before['boot']:bpc-before['boot']+bs] == after['body'][apc-after['boot']:apc-after['boot']+bs], ('different ordinary instruction', hex(bpc), hex(apc), hex(bw), hex(aw))
            if bw in (0x9508, 0x9518):
                continue
            assert bw not in (0x9409, 0x9509), 'Indirect control transfer requires an explicit target proof'
            assert bw & 0xfe0e not in (0x940c, 0x940e), 'Absolute control transfer requires target decoding'
            add(bpc + bs, apc + az)
            if bw & 0xfc00 == 0x1000 or bw & 0xfc08 in (0xfc00, 0xfe00) or bw & 0xff00 in (0x9900, 0x9b00):
                add(bpc + bs + size(before, bpc + bs), apc + az + size(after, apc + az))
    inverse = {}
    for bpc, apc in relation.items():
        inverse.setdefault(apc, []).append(bpc)
    merges = [sorted(v) for v in inverse.values() if len(v) > 1]
    expected = sorted([before['symbols']['usb_rx_terminal_early_reject'], before['symbols']['usb_rx_terminal_reject']])
    assert merges == [expected], ('unexpected instruction sharing', merges)
    # Every instruction reached through the two qualifiers has an equal-cost
    # corresponding opcode. Both short branch outcomes have matching timing.
    result = dict(before_sha256=before['sha256'], after_sha256=after['sha256'],
                  before_bytes=before['size'], after_bytes=after['size'],
                  named_roots=len(roots), related_instructions=len(relation),
                  successor_edges=edges, merged_baseline_pcs=[hex(x) for x in expected],
                  shared_candidate_pc=hex(after['symbols']['usb_rx_terminal_reject']),
                  every_path_added_clocks=0, removed_bytes=before['size']-after['size'])
    result['instruction_map'] = {str(k): v for k, v in sorted(relation.items())}
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Completed report exists; select a new output path')
    before,after=load(args.before),load(args.after)
    assert before['boot']==after['boot']
    result=cfg_equivalence(before,after)
    assert result['removed_bytes']==2
    for art in (before,after):
        assert hashlib.sha256(art['bin'].read_bytes()).hexdigest()==art['sha256']
        assert hashlib.sha256(art['obj'].read_bytes()).hexdigest()==art['elf_sha256']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:value for key,value in result.items() if key!='instruction_map'}))


if __name__=='__main__':main()
