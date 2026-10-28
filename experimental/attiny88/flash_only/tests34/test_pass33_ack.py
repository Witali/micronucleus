#!/usr/bin/env python3
"""Execute relevant linked AVR opcode paths, independent from source-text assertions.
Not a USB waveform/electrical simulator. No physical device is accessed.
"""
from __future__ import annotations
import sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R))
from check_build import build
from tests.avr_exec import AVRExec

CTX_TX_LENGTH=15; CTX_NEW_DEVICE_ADDRESS=19; CTX_DEVICE_ADDRESS=12; CTX_MSG_LENGTH=0
USB_PID_NAK=0x5a
class CPU:
    def __init__(self,art):
        self.x=AVRExec(art)
        self.sym=art['symbols'];self.r=[0]*32;self.mem={};self.Z=0;self.C=0;self.S=0;self.io={};self.trace=[]
        self.r[28]=self.r[30]=0;self.r[29]=self.r[31]=1
        self.calls=[]
    def run(self,start,ends,limit=100):
        pc=self.sym[start];targets={self.sym[e]:e for e in ends}
        for _ in range(limit):
            if pc in targets:return targets[pc]
            op,arg,size=self.x.ins.get(pc) or self.x.decode_missing(pc)
            if arg=='<unknown>':op,arg,size=self.x.decode_missing(pc)
            self.trace.append((pc,op,arg))
            a=[q.strip() for q in arg.split(',')];q=pc+size
            if op in ('ldd','std'):
                # LLVM 18 objdump renders AVR displacement q incorrectly;
                # recover all 6 bits from the compiled instruction word.
                w=int.from_bytes(self.x.art['body'][pc-self.x.art['boot']:pc-self.x.art['boot']+2],'little')
                off=(w&7)|((w>>7)&24)|((w>>8)&32)
                k=1 if op=='ldd' else 0
                a[k]=a[k].split('+')[0]+'+'+str(off)
            def rn(s):assert s[0]=='r',s;return int(s[1:])
            def ld(s):
                kind,d=s.split('+');idx=self.r[28] + (self.r[29]<<8) if kind=='Y' else self.r[30]+(self.r[31]<<8)
                return self.mem.get(idx+int(d,0),0)
            def st(s,v):
                kind,d=s.split('+');idx=self.r[28] + (self.r[29]<<8) if kind=='Y' else self.r[30]+(self.r[31]<<8)
                self.mem[idx+int(d,0)]=v&255
            if op=='cpi':
                d=rn(a[0]);src=self.r[d];k=int(a[1],0);v=(src-k)&255
                self.Z=int(v==0);self.C=int(src<k);self.S=int(bool(v&128) ^ bool(((src^k)&(src^v)&0x80)))
            elif op=='subi':
                d=rn(a[0]);src=self.r[d];imm=int(a[1],0);v=(src-imm)&255
                self.r[d]=v;self.Z=int(v==0);self.C=int(src<imm);self.S=int(bool(v&128) ^ bool(((src^imm)&(src^v)&0x80)))
            elif op=='tst':
                self.Z=int(self.r[rn(a[0])]==0);self.S=int(bool(self.r[rn(a[0])]&0x80))
            elif op=='mov':self.r[rn(a[0])]=self.r[rn(a[1])]
            elif op=='movw':
                destination,source=rn(a[0]),rn(a[1])
                self.r[destination:destination+2]=self.r[source:source+2]
            elif op=='clr':self.r[rn(a[0])]=0;self.Z=1
            elif op=='eor':
                d=rn(a[0]);self.r[d]^=self.r[rn(a[1])];self.Z=int(self.r[d]==0)
            elif op=='ldi':self.r[rn(a[0])]=int(a[1],0)&255
            elif op=='ldd':self.r[rn(a[0])]=ld(a[1])
            elif op=='std':st(a[0],self.r[rn(a[1])])
            elif op in ('breq','brne','brbs','brbc','brge','brlt'):
                if op=='breq':take=bool(self.Z)
                elif op=='brne':take=not self.Z
                elif op=='brge':take=not self.S
                elif op=='brlt':take=bool(self.S)
                else:
                    bit=int(a[0],0);flag={0:self.C,1:self.Z,4:self.S}[bit];take=bool(flag) if op=='brbs' else not flag
                if take:q+=int(a[-1].replace('.',''),0)
            elif op=='rjmp':q+=int(arg.replace('.',''),0)
            elif op=='rcall':
                self.calls.append(q)
                q+=int(arg.replace('.',''),0)
            elif op=='ret':
                assert self.calls,'Return without a matching call'
                q=self.calls.pop()
            elif op=='sbrc':
                if not self.r[rn(a[0])]&1<<int(a[1],0):q+=self.x.size_at(q)
            else:raise AssertionError((hex(pc),op,arg))
            pc=q
        raise AssertionError(('no stop',start,hex(pc),self.trace[-12:]))
