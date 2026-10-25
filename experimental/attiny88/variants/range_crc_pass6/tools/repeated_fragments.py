#!/usr/bin/env python3
"""Look for exact repeated instruction sequences outside low-level USB_handler.

Conservative: labels and branches break blocks, so this does not propose
unsafe relocations, and semantic equivalence is not inferred from text.
"""
from pathlib import Path
import re,collections
P=Path(__file__).resolve().parents[1]/'source/micronucleus_t88_plus.S'
lines=P.read_text().splitlines()
blocks=[]; block=[];in_critical=False
for i,line in enumerate(lines,1):
    x=line.split('/*')[0].strip()
    if x=='USB_handler:':
        in_critical=True
    if x=='usb_program_page:':
        in_critical=False
    if in_critical: continue
    if not x or x.startswith(('*','//','#','.')): continue
    if x.endswith(':'):
        if block: blocks.append(block)
        block=[]
        continue
    if re.match(r'^(?:rjmp|jmp|icall|ret|rcall|br\w+|cpse|sbic|sbis|sbrc|sbrs)\b',x):
        if block:blocks.append(block)
        block=[]
        continue
    if re.match(r'^[a-z]{2,7}(?:\s|$)',x):block.append((i,x))
    else:
        if block:blocks.append(block)
        block=[]
if block:blocks.append(block)

for n in (2,3,4,5):
    found=collections.defaultdict(list)
    for block in blocks:
        for ix in range(0,len(block)-n+1):
            seq=tuple(v[1] for v in block[ix:ix+n]);found[seq].append(block[ix][0])
    common={s:locs for s,locs in found.items() if len(locs)>1}
    print(f'{n} consecutive instructions: {len(common)} exact repeated patterns')
    for seq,locs in sorted(common.items(),key=lambda kv:len(kv[1]),reverse=True)[:5]:
        m=len(locs)
        # All instructions 2 bytes; RCALL 2 bytes / RET 2 bytes.
        benefit=2*n*(m-1)-2*(m+1)
        print(f'  lines={locs}, occurrences={m}, size benefit={benefit} bytes before save/restore; seq={seq}')
print('NOTE: These are source-text matches only; equivalent fragments with different registers are not detected.')
print('Do not extract code from USB_handler or setup critical paths without cycle-level proof.')
