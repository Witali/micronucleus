"""Small instruction-level AVR executor for selected non-USB bitstream paths.
Not a peripheral/USB simulator. Uses decoded actual instructions from LLVM.
"""
from pathlib import Path
import sys
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P))
from test_read_previous import decode,regnum

class AVRExec:
    def __init__(self,art):
        self.art=art
        self.ins=decode(art['obj'])
        # Some LLVM/AVR builds incorrectly merge perfectly legal 16-bit
        # MOVW / SPM and a following instruction into a 32-bit <unknown>.
        # Decode those words from the actual .text section, not source text.
        repairs={}
        for pc,(op,arg,n) in list(self.ins.items()):
            if n<3 or arg!='<unknown>':continue
            region=art['body'][pc-art['boot']:pc-art['boot']+4]
            if len(region)!=4:continue
            local={}
            undecodable=False
            for i in (0,2):
                word=region[i]|(region[i+1]<<8)
                at=pc+i
                if (word&0xff00)==0x0100:
                    d=2*((word>>4)&15);sr=2*(word&15)
                    local[at]=('movw',f'r{d}, r{sr}',2)
                elif (word&0xf000)==0xe000:
                    d=16+((word>>4)&15);k=((word>>4)&0xf0)|(word&15)
                    local[at]=('ldi',f'r{d}, {hex(k)}',2)
                elif (word & 0xfe08) in (0xfc00,0xfe00):
                    sr=(word>>4)&31; bit=word&7
                    local[at]=('sbrs' if word&0x0200 else 'sbrc',f'r{sr}, {bit}',2)
                elif (word & 0xff00) in (0x9600,0x9700):
                    reg=24+2*((word>>4)&3);imm=((word>>2)&0x30)|(word&15)
                    local[at]=('sbiw' if word&0x100 else 'adiw',f'r{reg}, {imm}',2)
                elif (word&0xfe0f) in (0x9403,0x940a):
                    local[at]=('inc' if word&0xf==3 else 'dec',f'r{(word>>4)&31}',2)
                elif (word&0xfc00)==0x2c00:
                    d=(word>>4)&31;sr=(word&15)|((word>>5)&16)
                    local[at]=('mov',f'r{d}, r{sr}',2)
                elif word==0x95e8:
                    local[at]=('spm','',2)
                elif (word&0xf000)==0xc000:
                    offset=word&0x0fff
                    if offset&0x800:offset-=4096
                    local[at]=('rjmp',('.+' if offset>=0 else '.-')+str(abs(offset)*2),2)
                else:
                    undecodable=True
                    break
            if not undecodable:
                del self.ins[pc]
                repairs.update(local)
        self.ins.update(repairs)
        self.sym=art['symbols']
        self.r=[0]*32
        self.ram={}
        self.io={}
        self.C=0;self.Z=0
        self.spms=[];self.io_events=[];self.stack=[];self.steps=[]
        self.pc=None

    def decode_missing(self,pc):
        if not self.art['boot']<=pc<self.art['boot']+len(self.art['body']):
            raise AssertionError(('missing opcode outside body',hex(pc)))
        off=pc-self.art['boot'];word=int.from_bytes(self.art['body'][off:off+2],'little')
        if word==0x95e8:return ('spm','',2)
        if (word&0xfe0f) in (0x9403,0x940a):
            return ('inc' if word&0xf==3 else 'dec',f'r{(word>>4)&31}',2)
        if (word&0xfc00)==0x2c00:
            d=(word>>4)&31;source=(word&15)|((word>>5)&16)
            return ('mov',f'r{d}, r{source}',2)
        if word==0x9508:return ('ret','',2)
        if word==0:return ('nop','',2)
        if (word&0xff00)==0x0100:
            d=2*((word>>4)&15);source=2*(word&15)
            return ('movw',f'r{d}, r{source}',2)
        if (word&0xf800) in (0xb000,0xb800):
            reg=(word>>4)&0x1f;io=((word>>5)&0x30)|(word&15)
            return ('out' if (word&0xf800)==0xb800 else 'in',
                    (f'{hex(io)}, r{reg}' if (word&0xf800)==0xb800 else f'r{reg}, {hex(io)}'),2)
        if (word&0xfc00)==0x2400:
            d=(word>>4)&0x1f;sr=(word&15)|((word>>5)&0x10)
            return ('eor',f'r{d}, r{sr}',2)
        if (word&0xff00) in (0x9600,0x9700):
            reg=24+2*((word>>4)&3);imm=((word>>2)&0x30)|(word&15)
            return ('adiw' if word&0x100==0 else 'sbiw',f'r{reg}, {imm}',2)
        if (word&0xf000)==0xe000:
            d=16+((word>>4)&15);imm=((word>>4)&0xf0)|(word&15)
            return ('ldi',f'r{d}, {hex(imm)}',2)
        if (word&0xfe08) in (0xfc00,0xfe00):
            reg=(word>>4)&31; bit=word&7
            return ('sbrs' if word&0x0200 else 'sbrc', f'r{reg}, {bit}',2)
        if (word&0xf000)==0xc000:
            imm=word&0xfff
            if imm&0x800:imm-=4096
            return ('rjmp',('.+' if imm>=0 else '.-')+str(abs(imm)*2),2)
        raise AssertionError(('unrecognized actual AVR word',hex(pc),hex(word)))

    def size_at(self,pc):
        if pc not in self.ins:self.ins[pc]=self.decode_missing(pc)
        return self.ins[pc][2]

    def addrZ(self):return self.r[30]+(self.r[31]<<8)
    def addrY(self):return self.r[28]+(self.r[29]<<8)
    def reg(self,t):return self.r[regnum(t)]

    def run(self,entry,stop=(),limit=200):
        self.pc=self.sym[entry] if isinstance(entry,str) else entry
        ends={self.sym[x] for x in stop if x in self.sym}
        for _ in range(limit):
            if self.pc in ends:return 'stop'
            if self.pc not in self.ins or self.ins[self.pc][1]=='<unknown>':
                self.ins[self.pc]=self.decode_missing(self.pc)
            op,arg,size=self.ins[self.pc]
            args=[x.strip() for x in arg.split(',')]
            q=self.pc+size
            self.steps.append((self.pc,op,arg))
            if op=='nop':pass
            elif op=='ldi':self.r[regnum(args[0])]=int(args[1],0)&255
            elif op=='mov':self.r[regnum(args[0])]=self.reg(args[1])
            elif op=='movw':
                d,s=regnum(args[0]),regnum(args[1]);self.r[d:d+2]=self.r[s:s+2]
            elif op=='ldd':
                if args[1].startswith('Y+'):
                    self.r[regnum(args[0])]=self.ram.get(int(args[1].split('+')[1]),0)
                elif args[1]=='Z+0':
                    assert self.addrZ()<32
                    self.r[regnum(args[0])]=self.r[self.addrZ()]
                else:raise AssertionError((op,arg))
            elif op=='std':
                assert args[0].startswith('Y+'),(op,arg)
                self.ram[int(args[0].split('+')[1])]=self.reg(args[1])
            elif op=='tst':self.Z=int(self.reg(args[0])==0)
            elif op=='cpi' or op=='cp' or op=='cpc':
                x=self.reg(args[0]); y=int(args[1],0) if op=='cpi' else self.reg(args[1]);prevC=self.C if op=='cpc' else 0;prevZ=self.Z
                self.C=int(x<y+prevC);self.Z=int((x-y-prevC)&255==0 and (op!='cpc' or prevZ))
            elif op=='andi':
                d=regnum(args[0]);self.r[d]&=int(args[1],0);self.Z=int(self.r[d]==0)
            elif op=='or':
                d=regnum(args[0]);self.r[d]|=self.reg(args[1]);self.Z=int(self.r[d]==0)
            elif op=='eor':
                d=regnum(args[0]);self.r[d]^=self.reg(args[1]);self.Z=int(self.r[d]==0)
            elif op=='lsl':
                d=regnum(args[0]);self.C=self.r[d]>>7;self.r[d]=(self.r[d]<<1)&255;self.Z=int(self.r[d]==0)
            elif op=='rol':
                d=regnum(args[0]);newC=self.r[d]>>7;self.r[d]=((self.r[d]<<1)|self.C)&255;self.C=newC;self.Z=int(self.r[d]==0)
            elif op in ('adiw','sbiw'):
                d=regnum(args[0]);w=self.r[d]+(self.r[d+1]<<8);off=int(args[1],0)
                w=(w+off if op=='adiw' else w-off)&0xffff
                self.r[d:d+2]=[w&255,w>>8];self.Z=int(w==0)
            elif op=='subi':
                d=regnum(args[0]);x=self.r[d];v=int(args[1],0);self.r[d]=(x-v)&255;self.C=int(x<v);self.Z=int(self.r[d]==0)
            elif op=='sub':
                d=regnum(args[0]);x=self.r[d];v=self.reg(args[1]);self.r[d]=(x-v)&255;self.C=int(x<v);self.Z=int(self.r[d]==0)
            elif op=='add':
                d=regnum(args[0]);x=self.r[d];v=self.reg(args[1]);self.r[d]=(x+v)&255;self.C=int(x+v>255);self.Z=int(self.r[d]==0)
            elif op=='inc':
                d=regnum(args[0]);self.r[d]=(self.r[d]+1)&255;self.Z=int(self.r[d]==0)
            elif op=='dec':
                d=regnum(args[0]);self.r[d]=(self.r[d]-1)&255;self.Z=int(self.r[d]==0)
            elif op=='ld':
                assert args[1]=='Z',(op,arg)
                self.r[regnum(args[0])]=self.r[self.addrZ()]
            elif op=='out':
                io=int(args[0],0);v=self.reg(args[1]);self.io[io]=v;self.io_events.append(('out',io,v))
            elif op=='in':
                self.r[regnum(args[0])]=self.io.get(int(args[1],0),0)
            elif op=='sbi':
                io=int(args[0],0);bit=int(args[1],0);self.io[io]=self.io.get(io,0)|(1<<bit)
                self.io_events.append(('sbi',io,bit))
            elif op=='spm':
                self.spms.append((self.io.get(0x37),self.addrZ(),self.r[0]|(self.r[1]<<8)))
            elif op in ('sbrc','sbrs'):
                v=self.reg(args[0])&(1<<int(args[1],0))
                if (op=='sbrc' and not v) or (op=='sbrs' and v):q+=self.size_at(q)
            elif op in ('sbic','sbis'):
                v=self.io.get(int(args[0],0),0)&(1<<int(args[1],0))
                if (op=='sbic' and not v) or (op=='sbis' and v):q+=self.size_at(q)
            elif op=='cpse':
                if self.reg(args[0])==self.reg(args[1]):q+=self.size_at(q)
            elif op in ('breq','brne','brlo','brsh','brbc','brbs'):
                if op=='breq':test=bool(self.Z)
                elif op=='brne':test=not self.Z
                elif op=='brlo':test=bool(self.C)
                elif op=='brsh':test=not self.C
                else:
                    bit=int(args[0],0);v=self.C if bit==0 else self.Z
                    test=(v==(1 if op=='brbs' else 0))
                if test:q+=int(args[-1].replace('.',''),0)
            elif op=='rjmp':q+=int(arg.replace('.',''),0)
            elif op=='rcall':
                self.stack.append(q);q+=int(arg.replace('.',''),0)
            elif op=='ret':
                if not self.stack:return 'ret'
                q=self.stack.pop()
            else:raise AssertionError((entry,hex(self.pc),op,arg))
            self.pc=q
        raise AssertionError((entry,'limit',hex(self.pc),self.steps[-5:]))
