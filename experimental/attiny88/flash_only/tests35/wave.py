#!/usr/bin/env python3
"""Test actual linked AVR RX opcodes with independent ideal Low-Speed ACK waveforms.
Finite digital model, not an electrical USB test. No hardware writes.
"""
from __future__ import annotations
from pathlib import Path
import sys,math
from bisect import bisect_right
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_build import build
from tests.avr_exec import AVRExec

J,K,SE0=2,4,0
PERIOD=32/3

def encoded_wave(packet, sop, period=PERIOD):
    seq=bytes([0x80])+bytes(packet)
    bits=[(b>>k)&1 for b in seq for k in range(8)]
    levels=[];times=[];line=J;ones=0
    for i,b in enumerate(bits):
        if ones==6:
            line=K if line==J else J
            levels.append(line);times.append(sop+len(levels[:-1])*period)
            ones=0
        if b==0:line=K if line==J else J
        times.append(sop+(i+sum(bits[:i+1].count(1) for _ in []))*period) # no stuffing in ACK
        levels.append(line)
        ones=ones+1 if b else 0
    assert len(bits)==16 and ones<6 and len(times)==16
    end=sop+len(bits)*period
    times += [end, end+2*period]
    levels += [SE0,J]
    return times,levels

class Sim:
    def __init__(self,art,sop=0,period=PERIOD,phase=0):
        self.a=art;self.d=AVRExec(art);self.r=[0]*32;self.m=bytearray(512)
        self.r[29]=1;self.r[31]=1;self.r[2]=12
        self.r[21]=0xA0
        self.m[0x100+15]=12;self.m[0x100+12]=0;self.m[0x100+19]=0x18
        self.io={0x1b:0,0x09:2}
        self.t=phase;self.sop=sop;self.phase=phase
        self.times,self.levels=encoded_wave([0xD2],sop,period)
        self.events=[]
        for t,v in zip(self.times,self.levels):
            before=self.pin(t-1e-4)
            if ((before^v)&4)!=0:self.events.append(t+3)
        self.clear=-1e10
        self.flags={'C':0,'Z':0,'N':0,'V':0,'S':0,'T':0,'H':0}
        self.pc=art['symbols']['USB_handler'];self.stack=[];self.trace=[]
        self.accepted=False;self.ret=False;self.steps=0;self.spm_hit=None;self.phy_entries=[];self.stop_on_context=True;self.simulate_spm_halt=False
    def pin(self,t):
        i=bisect_right(self.times,t)-1
        return self.levels[i] if i>=0 else J
    def reg(self,s):assert s.startswith('r'),s;return int(s[1:])
    def rd(self,s):return self.r[self.reg(s)]
    def stat(self,v,over=0,carry=None):
        self.flags['N']=int(bool(v&128));self.flags['Z']=int(v==0);self.flags['V']=int(bool(over));
        self.flags['S']=self.flags['N']^self.flags['V']
        if carry is not None:self.flags['C']=int(bool(carry))
    def read_io(self,adr):
        if adr==9:return self.pin(self.t-.5+1e-6)
        if adr==0x1b:return 4 if any(self.clear < x <= self.t for x in self.events) else 0
        return self.io.get(adr,0)
    def write_io(self,adr,v,bit=None):
        if adr==0x1b:
            if v&4:self.clear=self.t+(2 if bit is not None else 1)
        else:self.io[adr]=v
    def exec(self):
        if self.pc==self.a['symbols']['USB_handler']:self.phy_entries.append(self.t)
        if self.pc==self.a['symbols']['usb_rx_accept_ack']:
            self.accepted=True;return 'ack'
        if self.stop_on_context and self.pc==self.a['symbols']['usb_return_context']:
            self.ret=True;return 'return'
        if self.steps>1500:return 'timeout'
        maybe=self.d.ins.get(self.pc)
        if maybe is not None:
            op,args,size=maybe
        else:
            word=int.from_bytes(self.a['body'][self.pc-self.a['boot']:self.pc-self.a['boot']+2],'little')
            if word==0x920f:op,args,size='push','r0',2
            elif word==0x900f:op,args,size='pop','r0',2
            elif (word&0xfc00) in (0xf000,0xf400):
                op='brbs' if (word&0xfc00)==0xf000 else 'brbc'
                off=(word>>3)&127
                if off&64:off-=128
                args=f'{word&7}, .{off*2:+d}';size=2
            else:op,args,size=self.d.decode_missing(self.pc)
        if args=='<unknown>':
            word=int.from_bytes(self.a['body'][self.pc-self.a['boot']:self.pc-self.a['boot']+2],'little')
            if word==0x920f:op,args,size='push','r0',2
            elif word==0x900f:op,args,size='pop','r0',2
            else:raise AssertionError((hex(self.pc),hex(word)))
        pc=self.pc;self.pc=pc+size;aa=[x.strip() for x in args.split(',')];c=1
        self.trace.append((round(self.t,2),hex(pc),op,args,self.flags.copy(),self.r[23]))
        r=self.r;f=self.flags
        if op in ('ldi','mov','movw','clr','eor','and','andi','ori','tst','cpi','subi','cp','cpc','inc','dec','neg','lsl','lsr','rol','ror','sub','add','cpse'):
            if op=='ldi':r[self.reg(aa[0])]=int(aa[1],0)&255
            elif op=='mov':r[self.reg(aa[0])]=self.rd(aa[1])
            elif op=='movw':
                d,s=self.reg(aa[0]),self.reg(aa[1]);r[d:d+2]=r[s:s+2]
            elif op=='clr':r[self.reg(aa[0])]=0;self.stat(0)
            elif op in ('eor','and','andi','ori'):
                d=self.reg(aa[0]);v=r[d];w=int(aa[1],0) if op in ('andi','ori') else self.rd(aa[1]);
                r[d]={'eor':lambda:v^w,'and':lambda:v&w,'andi':lambda:v&w,'ori':lambda:v|w}[op]()
                self.stat(r[d])
            elif op=='tst':self.stat(self.rd(aa[0]))
            elif op in ('cp','cpc'):
                v=self.rd(aa[0]);w=self.rd(aa[1]);prevZ=f['Z'];incarry=f['C'] if op=='cpc' else 0
                z=(v-w-incarry)&255
                self.stat(z,((v^w)&(v^z)&128)!=0,v<w+incarry)
                if op=='cpc':f['Z'] &= prevZ
            elif op in ('cpi','subi','sub'):
                d=self.reg(aa[0]);v=r[d];w=int(aa[1],0) if op!='sub' else self.rd(aa[1]);z=(v-w)&255
                if op!='cpi':r[d]=z
                self.stat(z,((v^w)&(v^z)&128)!=0,v<w)
            elif op in ('inc','dec','neg'):
                d=self.reg(aa[0]);v=r[d];z={'inc':(v+1)&255,'dec':(v-1)&255,'neg':(-v)&255}[op];r[d]=z
                self.stat(z,(op=='inc' and v==127) or (op=='dec' and v==128) or (op=='neg' and v==128), (v!=0) if op=='neg' else None)
            elif op in ('lsl','lsr','ror','rol','add'):
                d=self.reg(aa[0]);v=r[d];w=self.rd(aa[1]) if op=='add' else v
                if op in ('lsl','rol','add'):
                    carry=f['C'] if op=='rol' else 0
                    wide=v+w+carry
                    z=wide&255;newC=int(wide>255)
                    over=bool((~(v^w)&(v^z)&128))
                else:
                    newC=v&1;z=(v>>1)|((f['C'] if op=='ror' else 0)<<7)
                    over=bool((z>>7)^newC)
                r[d]=z;self.stat(z,over,newC)
            elif op=='cpse':
                if self.rd(aa[0])==self.rd(aa[1]):
                    c=2;self.pc+=self.d.size_at(self.pc)
        elif op in ('brne','breq','brsh','brlo','brmi','brpl','brge','brlt','brbs','brbc','brts','brtc'):
            cond={'brne':lambda: not f['Z'],'breq':lambda:f['Z'],'brsh':lambda:not f['C'],'brlo':lambda:f['C'],'brmi':lambda:f['N'],'brpl':lambda:not f['N'],'brge':lambda:not f['S'],'brlt':lambda:f['S'],'brts':lambda:f['T'],'brtc':lambda:not f['T'],'brbs':lambda:f[{0:'C',1:'Z',2:'N',3:'V',4:'S',6:'T'}[int(aa[0],0)]],'brbc':lambda:not f[{0:'C',1:'Z',2:'N',3:'V',4:'S',6:'T'}[int(aa[0],0)]]}[op]()
            if cond:self.pc+=int(aa[-1].replace('.',''),0);c=2
        elif op=='rjmp':self.pc+=int(args.replace('.',''),0);c=2
        elif op=='rcall':self.stack.append(self.pc);self.pc+=int(args.replace('.',''),0);c=3
        elif op=='ret':
            c=4
            if self.stack:self.pc=self.stack.pop()
            else:self.ret=True
        elif op=='push':c=2;self.stack.append(self.rd(aa[0]))
        elif op=='pop':c=2;r[self.reg(aa[0])]=self.stack.pop()
        elif op=='in':r[self.reg(aa[0])]=self.read_io(int(aa[1],0))
        elif op=='out':self.write_io(int(aa[0],0),self.rd(aa[1]))
        elif op=='sbi':self.write_io(int(aa[0],0),1<<int(aa[1],0),bit=int(aa[1],0));c=2
        elif op in ('sbis','sbic'):
            v=self.read_io(int(aa[0],0))&(1<<int(aa[1],0))
            if (op=='sbis' and v) or (op=='sbic' and not v):
                c=2;self.pc+=self.d.size_at(self.pc)
        elif op in ('sbrc','sbrs'):
            v=self.rd(aa[0])&(1<<int(aa[1],0))
            if (op=='sbrc' and not v) or (op=='sbrs' and v):
                c=2;self.pc+=self.d.size_at(self.pc)
        elif op=='ldd':
            d=self.reg(aa[0]);p,disp=aa[1].split('+');addr=(r[28]+(r[29]<<8) if p=='Y' else r[30]+(r[31]<<8))+int(disp,0)
            # AVR displacement workaround using real instruction word
            word=int.from_bytes(self.a['body'][pc-self.a['boot']:pc-self.a['boot']+2],'little')
            off=(word&7)|((word>>7)&24)|((word>>8)&32)
            addr=(r[28]+(r[29]<<8) if p=='Y' else r[30]+(r[31]<<8))+off
            r[d]=self.m[addr];c=2
        elif op=='std':
            p,disp=aa[0].split('+')
            word=int.from_bytes(self.a['body'][pc-self.a['boot']:pc-self.a['boot']+2],'little')
            off=(word&7)|((word>>7)&24)|((word>>8)&32)
            addr=(r[28]+(r[29]<<8) if p=='Y' else r[30]+(r[31]<<8))+off
            self.m[addr]=self.rd(aa[1]);c=2
        elif op=='st':
            assert aa[0]=='Y+';addr=r[28]+(r[29]<<8);self.m[addr]=self.rd(aa[1]);addr+=1;r[28]=addr&255;r[29]=addr>>8;c=2
        elif op=='bst':f['T']=int(bool(self.rd(aa[0])&(1<<int(aa[1],0))))
        elif op=='bld':
            d=self.reg(aa[0]);bit=int(aa[1],0);r[d]=(r[d]&~(1<<bit))|(f['T']<<bit)
        elif op in ('adiw','sbiw'):
            d=self.reg(aa[0]);v=r[d]+(r[d+1]<<8);k=int(aa[1],0)
            n=(v+k if op=='adiw' else v-k)&0xffff
            r[d:d+2]=[n&255,n>>8]
            f['Z']=int(n==0)
            f['N']=int(bool(n&0x8000));f['V']=int(bool(((~v)&n&0x8000) if op=='adiw' else (v&(~n)&0x8000)))
            f['S']=f['N']^f['V'];f['C']=int((v+k)>0xffff) if op=='adiw' else int(v<k)
            c=2
        elif op=='or':
            d=self.reg(aa[0]);r[d]|=self.rd(aa[1]);self.stat(r[d])
        elif op=='spm':
            self.spm_hit=(self.t,r[3],r[30]+(r[31]<<8));c=(50_000 if self.simulate_spm_halt and r[3] in (3,5) else 4)
        elif op=='cbi':
            addr=int(aa[0],0);self.io[addr]=self.io.get(addr,0)&~(1<<int(aa[1],0));c=2
        elif op=='ld':
            assert aa[1]=='Z+',aa
            addr=r[30]+(r[31]<<8);r[self.reg(aa[0])]=self.m[addr];addr+=1;r[30:32]=[addr&255,addr>>8];c=2
        elif op=='nop':pass
        else:raise AssertionError((hex(pc),op,args))
        self.t+=c;self.steps+=1
        return 'ret' if self.ret else 'continue'
    def run(self,limit=2000):
        for _ in range(limit):
            z=self.exec()
            if z!='continue':return z
            if self.t>1400:return 'timeout'
        return 'timeout'

def run_sweep():
    arts=[]
    for led,boot in [('NONE',0x1c00),('ACTIVE_HIGH',0x1bc0),('ACTIVE_LOW',0x1bc0)]:
        a=build('source/micronucleus_t88_compact.S',mode=led,boot=boot)
        # Model starts at packet handler entry, relative to ACK SOP.
        ok=[];bad=[]
        for phase in (0,1/3,2/3):
            for delay in range(0,52):
                sim=Sim(a,sop=0,phase=delay+phase)
                result=sim.run()
                entry=(delay,phase,result,sim.pc,sim.t,sim.steps,sim.r[23],sim.m[0x10f])
                if result=='ack':ok.append(entry)
                else:bad.append(entry)
        print(led,'success',len(ok),'fail',len(bad),'min success',min(x[0] for x in ok) if ok else None,'max',max(x[0] for x in ok) if ok else None)
        print('  fail examples',bad[:12]);print('  gap failures',[(d, [x[1] for x in bad if x[0]==d]) for d in range(0,52) if any(x[0]==d for x in bad)][:16])
        arts.append((led,ok,bad))
    return arts
if __name__=='__main__':run_sweep()
