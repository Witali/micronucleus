#!/usr/bin/env python3
"""Read-only actual-opcode audit of the fixed V2 receive-byte CRC budget.

Uses an unstuffed all-zero payload: inserted USB stuff bits cannot be relied
on to provide work time. This audit does not modify a receiver or use USB.
"""
import argparse
from dataclasses import dataclass,asdict
import json
from pathlib import Path

import verify_streaming as verifier


@dataclass
class Instruction:
    at:int
    pc:int
    op:str
    operands:str
    cycles:int
    target:int|None


def category(ins):
    operands=ins.operands.replace(' ','')
    if ((ins.op=='eor' and operands in ('r30,r24','r30,r20'))
        or (ins.op=='mov' and operands=='r24,r25')
        or (ins.op=='ldi' and operands.startswith('r31,'))
        or ins.op=='lpm'):
        return 'crc'
    if ins.op=='nop' or (ins.op=='rjmp' and ins.target==ins.pc+2):
        return 'padding'
    return 'non_crc'


def audit(manifest):
    build=verifier.load_build(manifest)
    trace=[];original=verifier.TraceCPU.step
    def traced(cpu):
        at,pc=cpu.t,cpu.pc
        ins=original(cpu)
        trace.append(Instruction(at,pc,ins.op,ins.operands,cpu.t-at,getattr(ins,'target',None)))
        return ins
    verifier.TraceCPU.step=traced
    try:
        payload=bytes(8)
        packet=b'\xc3'+payload+verifier.crc16(payload)
        _,cpu,pins=verifier.receive(build,packet,0)
    finally:
        verifier.TraceCPU.step=original
    bit_pcs={cpu.labels[f'stream_bit{bit}']:bit for bit in range(8)}
    samples=[(at,source[1],source[2]) for at,pc,index,within,source,level in pins.reads
             if pc in bit_pcs and source[0]=='data']
    starts=[(at,byte) for at,byte,bit in samples if bit==0]
    rows=[];per_bit=[]
    for (start,byte),(end,next_byte) in zip(starts,starts[1:]):
        if not 1<=byte<=7:continue
        assert next_byte==byte+1
        instructions=[ins for ins in trace if start<=ins.at<end]
        row={'byte':byte,'period':end-start,
             **{kind:sum(ins.cycles for ins in instructions if category(ins)==kind)
                for kind in ('crc','padding','non_crc')}}
        rows.append(row)
        points=[(at,bit) for at,number,bit in samples if number==byte]
        assert len(points)==8 and [bit for at,bit in points]==list(range(8))
        for (at,bit),next_at in zip(points,[point[0] for point in points[1:]]+[end]):
            part=[ins for ins in instructions if at<=ins.at<next_at]
            per_bit.append({'byte':byte,'bit':bit,'period':next_at-at,
                **{kind:sum(ins.cycles for ins in part if category(ins)==kind)
                   for kind in ('crc','padding','non_crc')}})
    assert {row['period'] for row in rows}=={85,86}
    assert {row['crc'] for row in rows}=={11}
    assert {row['non_crc'] for row in rows}=={71}
    assert {row['padding'] for row in rows}=={3,4}
    source=verifier.PROTOTYPE/'source/streaming_rx_v2.inc'
    lines=source.read_text().splitlines()
    bits=[]
    for bit in range(8):
        part=[row for row in per_bit if row['bit']==bit]
        bits.append({'bit':bit,'source_line':lines.index(f'stream_bit{bit}:')+1,
            'period_range':[min(row['period'] for row in part),max(row['period'] for row in part)],
            'crc_cycles':part[0]['crc'],
            'useful_non_crc_cycles':part[0]['non_crc'],
            'unconditional_padding':min(row['padding'] for row in part),
            'conditional_padding_max':max(row['padding'] for row in part)-min(row['padding'] for row in part),
            'regular_crc_slots':part[0]['crc']+min(row['padding'] for row in part)})
    available=sum(row['regular_crc_slots'] for row in bits)
    assert available==14
    first=[ins for ins in trace if starts[0][0]<=ins.at<starts[1][0]]
    return {'sha256':build['sha256'],'source':'prototypes/streaming_crc16/source/streaming_rx_v2.inc',
        'bytes':rows,'bits':bits,'crc_pipeline_cycles':11,
        'useful_non_crc_cycles':71,'unconditional_padding_cycles':3,
        'direct_replacement_crc_cycles':available,
        'crc_instructions':[asdict(ins) for ins in first if category(ins)=='crc'],
        'scope':[
            'A fixed byte updater must fit the 85-cycle path, not only an average over stuffed inputs.',
            'Bit 2 has one extra NOP only on the long fractional-correction path; it is not free on every byte.',
            'Bit 3 RJMP is the byte-loop control, included in useful non-CRC work.',
            'Replacing the existing CRC and unconditional delays leaves slots 0,0,0,2,3,4,3,2 across bits 0..7.',
            'This is a bound for the unchanged sampler/control flow, not a universal impossibility theorem for a redesigned PHY.',
            'Register preservation, lookup-address placement, stuffing cooldowns and EOP cleanup need separate integration proofs.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=verifier.PROTOTYPE/'build/streaming-v2/manifest.json')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();report=audit(args.manifest)
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
