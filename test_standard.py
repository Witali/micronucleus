#!/usr/bin/env python3
"""Compare actual AVR standard-request dispatch machine instructions.

This deliberately stops at the shared reply helpers. It tests changes to the
USB request jump graph without claiming physical bus/timing verification.
"""
from pathlib import Path
from check_build import build
from test_dispatch import disasm
import re
ROOT=Path(__file__).resolve().parent
DIR=ROOT/'variants/strict_usb_optimized'
STOPS={'usb_reply_empty','usb_reply_use_scratch_buffer','usb_reply_set_pointer'}



def disasm_q(obj):
    """LLVM 17 AVR disassembler loses q[5:3] in LDD/STD pretty-print.

    Decode the actual 16-bit machine word to obtain the real displacement.
    """
    opmap=disasm(obj)
    import subprocess
    txt=subprocess.check_output(['llvm-objdump','-d',str(obj)],text=True)
    for line in txt.splitlines():
        m=re.match(r'^\s*([0-9a-f]+):\s+([0-9a-f]{2})\s+([0-9a-f]{2})\s+',line)
        if not m:continue
        pc=int(m[1],16)
        if pc not in opmap:continue
        op,args=opmap[pc]
        if op not in ('ldd','std'):continue
        instruction=int(m[2],16)|(int(m[3],16)<<8)
        q=(instruction&0x07)|((instruction>>7)&0x18)|((instruction>>8)&0x20)
        opmap[pc]=(op,re.sub(r'Y\+\d+', f'Y+{q}',args))
    return opmap

def execute(art, opmap, request, descriptor, config, value):
    syms=art['symbols']
    stop={syms[k]:k for k in STOPS}
    pc=syms['usb_standard_dispatch']
    reg=[0]*32
    reg[25]=request
    ram={25:value, 26:descriptor,21:config}
    Z=0
    write=[]
    for i in range(55):
        if pc in stop:
            return stop[pc],tuple(reg[k] for k in (18,19,24,25)),tuple(write)
        if pc not in opmap:
            raise AssertionError(('invalid_pc',hex(pc)))
        op,args=opmap[pc]
        nextpc=pc+2
        if op=='ldd':
            match=re.match(r'r(\d+), Y\+(\d+)',args)
            assert match,(op,args)
            reg[int(match[1])]=ram.get(int(match[2]),0)
        elif op=='std':
            match=re.match(r'Y\+(\d+), r(\d+)',args)
            assert match,(op,args)
            off,v=int(match[1]),reg[int(match[2])]
            ram[off]=v
            write.append((off,v))
        elif op=='cpi':
            r,k=args.split(', ')
            Z=int(reg[int(r[1:])]==int(k,0))
        elif op=='ldi':
            r,k=args.split(', ')
            reg[int(r[1:])]=int(k,0)
        elif op=='cpse':
            x,y=args.split(', ')
            if reg[int(x[1:])]==reg[int(y[1:])]:
                nextpc+=2
        elif op in ('breq','brne'):
            jump=(Z==1) if op=='breq' else (Z==0)
            if jump: nextpc+=int(args.replace('.',''),0)
        elif op=='rjmp':
            nextpc+=int(args.replace('.',''),0)
        else:
            raise AssertionError((hex(pc),op,args))
        pc=nextpc
    raise AssertionError(('long_handler',hex(pc),request))


def test():
    n=0
    for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        old=build(DIR/'micronucleus_t88_pass18d.S',mode)
        new=build(DIR/'micronucleus_t88_pass19d.S',mode)
        a=disasm_q(old['obj']);b=disasm_q(new['obj'])
        per=0
        for req in range(256):
            for descriptor in (0,1,2,3,7,255):
                for config,value in ((0,0),(1,19),(255,100)):
                    left=execute(old,a,req,descriptor,config,value)
                    right=execute(new,b,req,descriptor,config,value)
                    assert left==right,(mode,req,descriptor,config,value,left,right)
                    per+=1
        n+=per
        print('PASS',mode,per,'standard request dispatch combinations')
    print('PASS total',n)

if __name__=='__main__':test()
