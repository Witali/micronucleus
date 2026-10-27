#!/usr/bin/env python3
"""Exercise compiled AVR instructions of the unified 8-byte Flash/EEPROM request.

This is a deterministic USB-control handler / address-boundary model, NOT a
physical V-USB test. LLVM AVR disassembler LDD/STD displacements are re-decoded
from the original instruction word to avoid its misleading Y+q display.
"""
from pathlib import Path
from check_build import build
import subprocess,re,random
ROOT=Path(__file__).resolve().parent
S=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass19d.S'


def decode(obj):
    out=subprocess.check_output(['llvm-objdump','-d',str(obj)],text=True)
    instr={}
    for line in out.splitlines():
        mat=re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*([a-z][a-z0-9]*)\s*(.*)$',line)
        if not mat: continue
        pc=int(mat[1],16);raw=bytes.fromhex(mat[2]);op=mat[3].lower();args=mat[4].strip()
        if op in ('ldd','std') and ('Y+' in args):
            word=raw[0]|raw[1]<<8
            q=(word&7)|((word>>7)&24)|((word>>8)&32)
            args=re.sub(r'Y\+\d+',f'Y+{q}',args)
        instr[pc]=(op,args,len(raw))
    return instr


def regnum(tok):
    assert tok.startswith('r'),tok
    return int(tok[1:])


def execute(art,ins,adr,length=8,index=0,pending=0,eepe=False):
    sym=art['symbols']; pc=sym['memory_read']; final=sym['usb_rx_release_buffer'];
    regs=[0]*32;regs[8]=pending
    ram={25:adr&255,26:(adr>>8)&255,27:index&255,28:(index>>8)&255,29:length&255,30:(length>>8)&255,0:0,16:0x55,17:0xaa}
    carry=0;zero=0; skip=0
    for j in range(90):
        if pc==final:
            return ram.get(0,0),ram.get(16),ram.get(17),regs[2],j
        if pc not in ins:raise AssertionError(('pc',hex(pc),hex(adr),length,index))
        op,args,sz=ins[pc];parts=[x.strip() for x in args.split(',')];nextpc=pc+sz
        if op=='ldd':
            off=int(parts[1].split('+')[1]);regs[regnum(parts[0])]=ram.get(off,0)
        elif op=='std':
            off=int(parts[0].split('+')[1]);ram[off]=regs[regnum(parts[1])]
        elif op=='ldi':regs[regnum(parts[0])]=int(parts[1],0)
        elif op=='mov':regs[regnum(parts[0])]=regs[regnum(parts[1])]
        elif op in ('or','ori'):
            rd=regnum(parts[0]); val=regs[regnum(parts[1])] if op=='or' else int(parts[1],0)
            regs[rd]=(regs[rd]|val)&255;zero=int(regs[rd]==0)
        elif op=='tst':zero=int(regs[regnum(parts[0])]==0)
        elif op in ('cp','cpi','cpc'):
            av=regs[regnum(parts[0])]; bv=regs[regnum(parts[1])] if op!='cpi' else int(parts[1],0)
            bc=carry if op=='cpc' else 0;oldZ=zero
            carry=int(av < bv+bc)
            res=(av-bv-bc)&255
            zero=int(res==0 and (op!='cpc' or oldZ==1))
        elif op=='sbic':
            # only EECR.EEPE in the read handler
            assert (int(parts[0],0),int(parts[1],0))==(0x1f,1),(pc,op,args)
            if not eepe:
                nextpc+=ins[nextpc][2]
        elif op=='sbrc':
            if not (regs[regnum(parts[0])] & (1<<int(parts[1],0))):nextpc+=ins[nextpc][2]
        elif op in ('breq','brne','brlo','brsh','brbc','brbs'):
            if op=='breq':condition=(zero==1)
            elif op=='brne':condition=(zero==0)
            elif op=='brlo':condition=(carry==1)
            elif op=='brsh':condition=(carry==0)
            else:
                flag=int(parts[0],0)
                assert flag in (0,1),(pc,op,parts)
                value=carry if flag==0 else zero
                condition=(value==(1 if op=='brbs' else 0))
            if condition:nextpc+=int(parts[-1].replace('.',''),0)
        elif op=='rjmp':nextpc+=int(args.replace('.',''),0)
        elif op=='cpse':
            if regs[regnum(parts[0])]==regs[regnum(parts[1])]:nextpc+=ins[nextpc][2]
        else:
            raise AssertionError(('unsupported',hex(pc),op,args))
        pc=nextpc
    raise AssertionError(('loop',hex(adr),length,index,pc))


def test():
    n=0
    for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        art=build(S,mode=mode,boot=0x1ac0);d=decode(art['obj']);APP_LIMIT=0x1ac0-4
        # All 16-bit addresses, including aliases and both ends of EEPROM.
        adrs=range(65536) if mode=='NONE' else [*range(0x0,0x250,7),*range(0x1a80,0x1ba0),*range(0x7ffc,0x8060)]
        for addr in adrs:
            accepted=(0<=addr<=APP_LIMIT-8) or (0x8000<=addr<=0x8038)
            out=execute(art,d,addr)
            if accepted:
                assert out[:4]==(8,addr&255,((addr>>8)&255 if addr<0x8000 else 0),2 if addr&0x8000 else 0),(mode,hex(addr),out)
            else:
                assert out[0]==0,(mode,hex(addr),out)
            n+=1
        for addr in [0,1,0x1ab4,0x1ab5,0x8000,0x8038,0x8039,0x803f,0xffff]:
            for length in [0,1,4,7,9,255,256,264,0x1008]:
                assert execute(art,d,addr,length=length)[0]==0,(mode,addr,length)
                n+=1
            for index in [1,0x100,0xffff]:
                assert execute(art,d,addr,index=index)[0]==0,(mode,addr,index)
                n+=1
            if 0x8000<=addr<=0x8038:
                for queued,eepe in ((1,False),(0,True),(3,True)):
                    assert execute(art,d,addr,pending=queued,eepe=eepe)[0]==0,(mode,addr,queued,eepe)
                    n+=1
        print('PASS',mode,'USB memory address / length / mode tests')
    print('PASS total',n,'executions of actual AVR instructions')

if __name__=='__main__':test()
