#!/usr/bin/env python3
"""Find repeated *byte-identical logical AVR instructions* in the bootloader.

Only looks for straight-line code after the timing-critical USB routines.
This is a candidate scan, not an automatic function extractor: extra jumps,
branch-entry points, register conventions, and cycle costs need further proof.
"""
from __future__ import annotations
from pathlib import Path
import collections
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import avr_decoder as dec


def symbols():
    sy={}
    for line in subprocess.check_output(['llvm-objdump','-t',str(ROOT/'build/plus_1ac0.o')],text=True).splitlines():
        m=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',line)
        if m:sy[m[2]]=int(m[1],16)
    return sy


def run():
    sy=symbols()
    dec.START=0x1AC0;dec.raw=(ROOT/'firmware/BOOTLOADER_BODY_1AC0_PLUS.bin').read_bytes()
    start=sy['flash_buffer_append_word'];end=0x1AC0+len(dec.raw)
    seq=[];pc=start
    while pc<end:
        ins=dec.decode(pc)
        assert not ins.unknown
        seq.append(ins);pc+=ins.size
    print('Code scanned (non-USB):',len(seq),'instructions,',end-start,'bytes')
    total=0
    for n in range(8,3,-1):
        groups=collections.defaultdict(list)
        for i in range(len(seq)-n+1):
            w=seq[i:i+n]
            # Avoid cross-basic-block merges: neither direct branch nor call
            # may occur inside an exact sequence proposed for a subroutine.
            if any(x.target is not None or x.op in ('ret','reti','spm','wdr') for x in w):continue
            signature=tuple((x.op, re.sub(r'\s+','',x.operands).lower()) for x in w)
            groups[signature].append(w[0].address)
        repeats=[(k,addrs) for k,addrs in groups.items() if len(addrs)>=2]
        print(f'Length {n}: {len(repeats)} candidate repeated blocks')
        for _,addrs in repeats[:8]:print('  ', ', '.join(hex(a) for a in addrs))
        total+=len(repeats)
    print('Profitable exact straight-line subroutine candidates of >=4 instructions:',total)


if __name__=='__main__':run()
