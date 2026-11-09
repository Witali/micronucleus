"""Independent emitted-word/carry/publication audit of root's frozen unit fixture."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
EXPECTED='1db596fefa080b8fe016284bd0792cd132d231ba7d55c33fbf1de63f0c4504aa'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--firmware-root',type=Path,default=Path('../..'),
                    help='flash_only directory, relative to this script directory')
parser.add_argument('--output-dir',type=Path,default=HERE/'build')
ARGS=parser.parse_args()
FLASH=(HERE/ARGS.firmware_root).resolve()
SNAP=ARGS.output_dir.resolve()
assert (FLASH/'tests35/ep0_model.py').is_file(),('Invalid --firmware-root',str(FLASH))
subprocess.check_output([sys.executable,str(HERE/'build.py'),'--output-dir',str(SNAP)],
                        stderr=subprocess.STDOUT)
sys.path.insert(0,str(FLASH))
from tests35 import ep0_model as h
from tests35.ep0_cases import bind

def freeze():
    art=json.loads((SNAP/'artifact.json').read_text())
    for name,expected in art['source_hashes'].items():
        assert hashlib.sha256((SNAP/name).read_bytes()).hexdigest()==expected
    art.update(obj=SNAP/'publication.elf',bin=SNAP/'publication.bin')
    art['body']=art['bin'].read_bytes()
    assert art['boot']==0 and art['size']==len(art['body'])==4328
    assert hashlib.sha256(art['body']).hexdigest()==art['sha256']==EXPECTED
    return art,json.loads((SNAP/'manifest.json').read_text())

ART,MAN=freeze()
FIRST={ART['symbols'][name]:state for name,state in MAN['firsts'].items()}
STOPS={ART['symbols'][name]:(name,state) for name,state in MAN['stops'].items()}
TAGS={ART['symbols'][name]:reason for name,reason in MAN['tags'].items()}
STORES={ART['symbols'][name] for name in MAN['stores']}

def control():
    # Reassemble exact source with the independent GNU assembler driver.
    subprocess.check_output(['avr-gcc','-mmcu=attiny88','-DBOOT_AT=0','-x','assembler-with-cpp',
                             '-c',str(SNAP/'publication.S'),'-o',str(SNAP/'rebuilt.o')],stderr=subprocess.STDOUT)
    subprocess.check_output(['avr-ld','-m','avr25','-Ttext=0','-e','bootloader_start','-o',
                             str(SNAP/'rebuilt.elf'),str(SNAP/'rebuilt.o')],stderr=subprocess.STDOUT)
    body=subprocess.check_output(['avr-objcopy','-O','binary','-j','.text',str(SNAP/'rebuilt.elf'),'/dev/stdout'])
    assert body==ART['body']
    pc=0;labels={};rows=[];counts=Counter();wraps=[]
    for raw in (SNAP/'publication.S').read_text().splitlines():
        row=raw.strip()
        if not row or row.startswith(('.', '/*', '*')):continue
        if row.endswith(':'):labels[row[:-1]]=pc
        else:rows.append((pc,row));pc+=2
    assert pc==4328 and all(ART['symbols'][k]==v for k,v in labels.items())
    for pc,row in rows:
        op,*tail=row.split(maxsplit=1)
        if op!='rjmp' and not op.startswith('br'):continue
        word=int.from_bytes(ART['body'][pc:pc+2],'little')
        val,width=(word&4095,12) if op=='rjmp' else ((word>>3)&127,7)
        delta=val-(1<<width) if val&(1<<(width-1)) else val
        target=pc+2+2*delta
        assert target%8192==labels[tail[0]]
        if target!=target%8192:wraps.append((pc,row,target))
        counts[op]+=1
    assert not wraps
    return dict(bytes=4328,instructions=len(rows),transfers=dict(counts),wrapped_edges=wraps,
                gnu_reassembly_sha256=hashlib.sha256(body).hexdigest())

class Pins(dict):
    def __init__(self,cpu,levels,noise):self.cpu,self.levels,self.noise,self.samples=cpu,levels,noise,[]
    def get(self,io,default=0):
        if io!=9:return super().get(io,default)
        assert self.cpu.t in self.levels,('unscheduled IN',self.cpu.t)
        value=self.levels[self.cpu.t]
        self.samples.append((self.cpu.t,value))
        return value|((self.noise+43*len(self.samples))&0xf9)

def shifted(value,bit):return (value>>1)|(bit<<7)

def case(name,byte,bits,carry,noise,initial_t,bad=None,first_se1=False):
    cfg=MAN['entries'][name]
    p,line,run,bit=(cfg[k] for k in ('phase','line','run','bit'))
    prior=h.J if line=='J' else h.K
    now=prior if bit else prior^6
    history=0x80;histories=[byte];origins=[0];states=[(p,line,run)]
    values=[now];next_run=run+1 if bit else 0
    for newbit in bits:
        origins.append(origins[-1]+(10 if states[-1][0]==0 else 11))
        states.append(((states[-1][0]+1)%3,'J' if now==h.J else 'K',next_run))
        if next_run==6:
            assert not newbit
            now^=6;next_run=0
        else:
            if newbit:next_run+=1
            else:now^=6;next_run=0
            history=shifted(history,newbit)
        values.append(now);histories.append(history)
    origins.append(origins[-1]+(10 if states[-1][0]==0 else 11))
    states.append(((states[-1][0]+1)%3,'J' if now==h.J else 'K',next_run));values.append(now)
    levels={at+d:value for at,value in zip(origins,values) for d in (0,2,6)}
    if bad=='first':levels[0]=0
    if bad=='second':levels[2]=0
    if first_se1:levels[0]=6
    cpu=h.CPU(ART,h.Wave(b''),0);cpu.pc=ART['symbols'][name]
    cpu.r[:]=[(31*i+17)&255 for i in range(32)]
    cpu.r[1]=0;cpu.r[18]=((byte<<1)&255)|carry;cpu.r[19]=prior
    cpu.r[20:22]=[h.J,h.K];cpu.r[28:30]=[0x16,1];cpu.setflag(6,initial_t)
    initial=cpu.r[:];memory=bytes(cpu.m);stack=cpu.raw_stack[:]
    cpu.io=Pins(cpu,levels,noise);first_index=0;stores=[]
    for _ in range(120):
        if cpu.pc in TAGS:
            assert bad is not None,('unexpected tag',name,TAGS[cpu.pc])
            assert not stores and bytes(cpu.m)==memory and cpu.word(28)==0x116
            assert cpu.flag(6)==initial_t and cpu.raw_stack==stack and not cpu.bus_events
            return 'negative'
        if cpu.pc in STOPS:
            stop_name,stop=STOPS[cpu.pc]
            assert bad is None
            assert cpu.t==origins[first_index]
            assert tuple(stop[k] for k in ('phase','line','run'))==states[first_index]
            if carry:
                assert len(stores)==1 and cpu.word(28)==0x117 and cpu.m[0x116]==byte
                assert cpu.r[23]==byte and cpu.r[18]==histories[first_index-1]
                # LDI seeds preserve the old completion C=1; the first real
                # following shift clears it. PC must carry this distinction.
                prefix=stop['prefix']
                expected_c=1 if prefix.startswith(('seed_','retain_')) else 0
                assert cpu.flag(0)==expected_c,('C lifetime',stop_name,prefix,cpu.flag(0),expected_c)
            else:
                assert not stores and cpu.word(28)==0x116 and bytes(cpu.m)==memory
                assert cpu.r[18]==shifted((byte<<1)&255,bit) and cpu.flag(0)==0
            live=list(range(16))+list(range(20,23))+list(range(24,28))+[30,31]
            assert all(cpu.r[i]==initial[i] for i in live)
            assert cpu.flag(6)==initial_t and cpu.raw_stack==stack and not cpu.bus_events
            assert cpu.m[:0x116]==memory[:0x116] and cpu.m[0x117:]==memory[0x117:]
            # Every ordinary 1 classifier retains the dense SECOND/EXTRA pair.
            for i,at in enumerate(origins[:first_index]):
                if states[i][2]!=6 and values[i]==(h.J if states[i][1]=='J' else h.K):
                    assert (at+2,values[i]) in cpu.io.samples and (at+6,values[i]) in cpu.io.samples
            return 'complete' if carry else 'not_full'
        if cpu.pc in FIRST:
            assert cpu.t==origins[first_index]
            state=FIRST[cpu.pc]
            assert tuple(state[k] for k in ('phase','line','run'))==states[first_index]
            first_index+=1
        if cpu.pc in STORES:
            stores.append(dict(time=cpu.t,pc=cpu.pc,value=cpu.r[23],carry=cpu.flag(0)))
            assert carry and cpu.r[23]==byte
        cpu.step()
    raise AssertionError(('instruction bound',name))

def file_hashes(root,names):
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}


def model_hashes():
    result={}
    for module in tuple(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            path=Path(file).resolve()
            if path.is_relative_to(FLASH.parent) and path.is_file():
                result[str(path.relative_to(FLASH.parent))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(result.items()))


def main():
    bind(ART)
    source_pins=file_hashes(HERE,('generate.py','build.py','verify.py'))
    artifact_pins=file_hashes(SNAP,('publication.S','manifest.json','publication.elf',
                                   'publication.bin','artifact.json'))
    model_pins=model_hashes()
    ctl=control();counts=Counter();failures=[]
    for name,cfg in MAN['entries'].items():
        for byte in range(256):
            if byte>>7!=cfg['bit']:continue
            run=0
            for at in range(6,-1,-1):
                if not ((byte>>at)&1):break
                run+=1
            if run!=cfg['run']:continue
            for a in (0,1):
                if cfg['bit'] and cfg['run']==5 and a:continue
                following=cfg['run']+2 if cfg['bit'] and a else (1 if a else 0)
                for b in (0,1):
                    if following==6 and b:continue
                    for carry in (0,1):
                        for noise in (0,0xf9):
                            for initial_t in (0,1):
                                try:counts[case(name,byte,(a,b),carry,noise,initial_t)]+=1
                                except (AssertionError,KeyError) as error:
                                    failures.append(dict(name=name,byte=byte,bits=[a,b],carry=carry,noise=noise,
                                                         initial_t=initial_t,error=str(error)))
        example=(0x80 if cfg['bit'] else 0)|(((1<<cfg['run'])-1)<<(7-cfg['run']))
        bad='second' if cfg['bit'] else 'first'
        for noise in (0,0xf9):
            for initial_t in (0,1):
                try:counts[case(name,example,(0,0),1,noise,initial_t,bad=bad)]+=1
                except (AssertionError,KeyError) as error:
                    failures.append(dict(name=name,bad=bad,initial_t=initial_t,error=str(error)))
    result=dict(sha256=EXPECTED,control=ctl,counts=dict(counts),failure_count=len(failures),failures=failures,
                scope='Independent raw-GPIO unit schedule audit only: incomplete entry set; no EOP/publication eligibility, packet bound, SYNC, or protocol admission proof')
    assert file_hashes(HERE,source_pins)==source_pins,'Package source changed during audit'
    assert file_hashes(SNAP,artifact_pins)==artifact_pins,'Linked artifact changed during audit'
    assert model_hashes()==model_pins,'Independent model changed during audit'
    result['source_hashes']=source_pins
    result['generated_hashes']=ART['source_hashes']
    result['artifact_hashes']=artifact_pins
    result['model_hashes']=model_pins
    (SNAP/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='failures'},indent=2),flush=True)
    print(json.dumps(failures[:5],indent=2),flush=True)
    assert not failures
    assert counts==dict(complete=15936,not_full=15936,negative=224),counts

if __name__=='__main__':main()
