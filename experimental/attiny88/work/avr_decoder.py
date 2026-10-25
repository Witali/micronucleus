#!/usr/bin/env python3
"""Disassembler for classic AVR subset, preserving each instruction and exact target."""
import sys,struct,re
from dataclasses import dataclass
from pathlib import Path

START=0x1a40
CODE_START=0x1a6e
raw=Path(sys.argv[1] if len(sys.argv)>1 else '/mnt/data/micronucleus_t88_optimization/reference/t88_default_upstream.bin').read_bytes()

@dataclass
class Insn:
    address:int
    words:tuple
    op:str
    operands:str
    target:int|None=None
    size:int=2
    unknown:bool=False
    def asm(self,labels):
        return (self.op+' '+(labels.get(self.target,f'0x{self.target:x}') if self.target is not None else self.operands)).strip()

def signed(v,b): return v-(1<<b) if v&(1<<(b-1)) else v

def decode(a):
    off=a-START
    w=int.from_bytes(raw[off:off+2],'little'); w2=int.from_bytes(raw[off+2:off+4],'little') if off+3<len(raw) else None
    def o(op,operand='',target=None,size=2): return Insn(a, (w,) if size==2 else (w,w2),op,operand,target,size)
    # explicit 4-byte instructions before two-byte ones
    if w&0xfe0f in (0x9000,0x9200):
        op='lds' if (w&0xfe0f)==0x9000 else 'sts'; reg=(w>>4)&31
        return o(op, f'r{reg}, 0x{w2:04x}' if op=='lds' else f'0x{w2:04x}, r{reg}',size=4)
    if w&0xfe0e in (0x940c,0x940e):
        targ=((w&1)<<16)|((w&0x1f0)<<13)|w2
        return o('jmp' if (w&0xfe0e)==0x940c else 'call',f'0x{targ:x}',size=4)
    if w==0: return o('nop')
    single={0x9508:'ret',0x9518:'reti',0x95a8:'wdr',0x95e8:'spm',0x95c8:'lpm',0x9409:'ijmp',0x9509:'icall',0x9478:'sei',0x94f8:'cli',0x9588:'sleep',0x95d8:'elpm',0x95f8:'spm Z+'}
    if w in single:return o(single[w])
    if w&0xf000==0xc000: return o('rjmp',target=a+2+signed(w&0xfff,12)*2)
    if w&0xf000==0xd000: return o('rcall',target=a+2+signed(w&0xfff,12)*2)
    if w&0xfc00 in (0xf000,0xf400):
        return o('brbs' if (w&0xfc00)==0xf000 else 'brbc',f'{w&7},',target=a+2+signed((w>>3)&0x7f,7)*2)
    if w&0xf000 in (0x3000,0x4000,0x5000,0x6000,0x7000,0xe000):
        op={0x3000:'cpi',0x4000:'sbci',0x5000:'subi',0x6000:'ori',0x7000:'andi',0xe000:'ldi'}[w&0xf000]
        return o(op, f'r{16+(w>>4&15)}, 0x{((w>>4)&0xf0)|(w&15):02x}')
    if w&0xfc00 in (0x0000,0x0400,0x0800,0x0c00,0x1000,0x1400,0x1800,0x1c00,0x2000,0x2400,0x2800,0x2c00):
        if w&0xff00==0x0100:
            return o('movw',f'r{2*((w>>4)&15)}, r{2*(w&15)}')
        op={0x0400:'cpc',0x0800:'sbc',0x0c00:'add',0x1000:'cpse',0x1400:'cp',0x1800:'sub',0x1c00:'adc',0x2000:'and',0x2400:'eor',0x2800:'or',0x2c00:'mov'}.get(w&0xfc00)
        if op:return o(op,f'r{w>>4&31}, r{(w&15)|((w>>5)&16)}')
    if w&0xff00 in (0x9600,0x9700):
        return o('adiw' if w&0xff00==0x9600 else 'sbiw', f'r{24+((w>>4&3)<<1)}, {((w>>2)&0x30)|(w&15)}')
    if w&0xff00 in (0x9800,0x9900,0x9a00,0x9b00):
        return o({0x9800:'cbi',0x9900:'sbic',0x9a00:'sbi',0x9b00:'sbis'}[w&0xff00],f'0x{(w>>3)&0x1f:x}, {(w&7)}')
    if w&0xf800 in (0xb000,0xb800):
        p=(w&15)|((w>>5)&0x30); reg=(w>>4)&31
        return o('in' if w&0xf800==0xb000 else 'out',f'r{reg}, 0x{p:x}' if w&0xf800==0xb000 else f'0x{p:x}, r{reg}')
    for mask,pattern,op in [
        (0xfe0f,0x900f,'pop'),(0xfe0f,0x920f,'push'),
        (0xfe0f,0x9400,'com'),(0xfe0f,0x9401,'neg'),(0xfe0f,0x9402,'swap'),
        (0xfe0f,0x9403,'inc'),(0xfe0f,0x9405,'asr'),(0xfe0f,0x9406,'lsr'),
        (0xfe0f,0x9407,'ror'),(0xfe0f,0x940a,'dec'),
        (0xfe0f,0x9004,'lpm'),(0xfe0f,0x9005,'lpm'),
    ]:
        if w&mask==pattern:
            reg=(w>>4)&31
            if op=='lpm':return o('lpm',f'r{reg}, Z'+('+' if w&1 else ''))
            return o(op, f'r{reg}')
    if w&0xfe08 in (0xfc00,0xfe00,0xf800,0xfa00):
        return o({0xfc00:'sbrc',0xfe00:'sbrs',0xf800:'bld',0xfa00:'bst'}[w&0xfe08], f'r{(w>>4)&31}, {w&7}')
    if w&0xff8f in (0x9408,0x9488):return o('bset' if w&0xff8f==0x9408 else 'bclr',f'{(w>>4)&7}')
    # load/store direct X/Y/Z ± syntax
    memreg={0x900c:'X',0x900d:'X+',0x900e:'-X',0x9008:'Y',0x9009:'Y+',0x900a:'-Y',0x9000:'Z',0x9001:'Z+',0x9002:'-Z',
            0x920c:'X',0x920d:'X+',0x920e:'-X',0x9208:'Y',0x9209:'Y+',0x920a:'-Y',0x9200:'Z',0x9201:'Z+',0x9202:'-Z'}
    wr=w&0xfe0f
    if wr in memreg:
        op='ld' if (wr&0x200)==0 else 'st'; reg=(w>>4)&31
        return o(op,f'r{reg}, {memreg[wr]}' if op=='ld' else f'{memreg[wr]}, r{reg}')
    if w&0xd208 in (0x8000,0x8008,0x8200,0x8208):
        q=((w>>8)&0x20)|((w>>7)&0x18)|(w&7)
        op='ldd' if not (w&0x200) else 'std'; mem='Y' if w&8 else 'Z'; reg=(w>>4)&31
        return o(op,f'r{reg}, {mem}+{q}' if op=='ldd' else f'{mem}+{q}, r{reg}')
    if w&0xff0f==0x9204:return o('xch',f'Z, r{(w>>4)&31}')
    return Insn(a,(w,),'WORD',f'0x{w:04x}',unknown=True)

ins=[]
a=CODE_START
while a<START+len(raw):
    i=decode(a);ins.append(i);a+=i.size
unknown=[x for x in ins if x.unknown]
if unknown:print('UNKNOWN ',[(hex(x.address),hex(x.words[0])) for x in unknown],file=sys.stderr)
# collect internal branch targets
labels={x.target:f'L{x.target:04x}' for x in ins if x.target is not None and CODE_START<=x.target<START+len(raw)}
# specialized marked routine starts
routines={0x1a40:'bootloader_start',0x1a6e:'startup',0x1a8c:'usb_crc16_append',0x1ab8:'USB_handler',0x1cce:'usb_program_page',0x1cec:'main',0x1f80:'main_tail'}
labels.update(routines)
with open('/mnt/data/micronucleus_t88_asm/work/original_decoded.S','w') as f:
    f.write('/* Original Micronucleus t88_default 16 MHz - derived from official precompiled firmware.\n')
    f.write(' * Independent readable assembler reconstruction. Binary-equivalent reference build.\n')
    f.write(' * Copyright original Micronucleus contributors; GPL-2.0-or-later.\n */\n')
    f.write('.section .text\n.org 0x1a40\n.global bootloader_start\nbootloader_start:\n')
    f.write('    rjmp startup\n')
    # USB configuration and descriptors stored immediately before startup
    f.write('/* Micronucleus device-info and USB descriptors in program memory. */\n')
    for j in range(2,CODE_START-START,8):
        bs=raw[j:min(j+8,CODE_START-START)];f.write(f'    .byte '+', '.join(f'0x{b:02x}' for b in bs)+f'  /* {START+j:04x} */\n')
    for x in ins:
        if x.address in labels: f.write('\n'+labels[x.address]+':\n')
        if x.address == 0x1ebe:
            f.write('    .word 0xcdbe /* RJMP to original application postscript at 0x1a3c */\n')
            continue
        arg=x.operands
        if x.target is not None:
            arg=(arg+' ' if x.op in ('brbc','brbs') else '')+labels.get(x.target, f'0x{x.target:04x}')
        f.write(f'    {x.op.lower():7s} {arg:32s} /* 0x{x.address:04x}: '+ ' '.join(f'{w:04x}' for w in x.words)+ ' */\n')
print('instructions',len(ins),'unknown',len(unknown),'labels',len(labels),'filesize',len(raw))
