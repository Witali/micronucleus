"""Verify only the PC/T-typed receive-entry component, not a USB loader."""
from pathlib import Path
from collections import Counter
import argparse,copy,hashlib,json,sys
sys.dont_write_bytecode=True

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=HERE.parents[2],
                    help='Flash-only root; the default is the installed repository layout')
args=parser.parse_args()
ROOT=args.root.resolve()
sys.path.insert(0,str(ROOT))
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import from_bits
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_usb_crossover import single_crossover
from tests35.test_ep0_token_timeout import Joined
from fixtures import FIXTURES

output=ROOT/'build/typed_entry_component'
build_dir=output/'entry'
build_dir.mkdir(parents=True,exist_ok=True)
(build_dir/'micronucleus_t88_compact.S').write_text((HERE/'entry_probe.S').read_text())
ART=h.build(source=build_dir.relative_to(ROOT).as_posix(),boot=0x1800)
assert ART['size']==154
assert ART['sha256']=='caba7bb6fc8de651156c64956be8740a19f5362562cd12c5f405f38648461b01'
bind(ART)

def outside(value):return (value&1)|((value&62)<<2)

class NoisyPins(h.SynchronizedPinIO):
    def __init__(self,cpu,wave,noise):
        super().__init__(cpu,wave)
        self.noise=noise;self.read_count=0
    def get(self,address,default=0):
        value=super().get(address,default)
        if address==9:
            value|=outside((self.noise+17*self.read_count)&63)
            self.read_count+=1
        return value

def physical(packet,rate,sign):
    wave=h.Wave(packet,rate=rate,jitter=lambda i,l:sign*(.55 if l==h.J else -.55))
    end=wave.boundaries[-3]
    wave.boundaries[-2]=end+10.72
    wave.boundaries[-1]=end+10.72+wave.period
    wave.end=wave.boundaries[-1]
    wave.pin_edges=[];before=h.J
    for when,line in zip(wave.boundaries,wave.levels):
        if (before^line)&4:wave.pin_edges.append(when)
        before=line
    interval_errors(wave)
    return wave

def data_positions(packet):
    run=0;at=0;positions=[]
    for byte in b'\x80'+packet:
        for bitn in range(8):
            bit=(byte>>bitn)&1
            if at>=8:positions.append(at)
            at+=1;run=run+1 if bit else 0
            if run==6:at+=1;run=0
    return positions

def context_from(row):
    context=dict(row)
    context['packet']=bytes.fromhex(row['packet'])
    context['wave']=physical(context['packet'],row['rate'],row['sign'])
    context['logical']=data_positions(context['packet'])
    return context

def execute(context,wave=None,legal=True):
    bind(ART)
    wave=wave or context['wave']
    first=context['first']
    is_six=context['kind']=='prior_six'
    cpu=h.CPU(ART,wave,first if is_six else first-1)
    cpu.pc=cpu.labels['typed_six_entry' if is_six else 'typed_five_setup']
    cpu.r[:]=context['registers'];cpu.io=NoisyPins(cpu,wave,13)
    expected_T=None if is_six else int(context['wave'].bits[context['physical']])
    initial_T=1 if is_six else 1-expected_T
    cpu.setflag(6,initial_T)  # Poison each exported class with the opposite flag.

    initial=cpu.r[:];memory=bytes(cpu.m);stack=cpu.raw_stack[:]
    stops={cpu.labels[name]:name for name in ('rejected','initial_eop','pending_eop',
           'phase2_eop','prior_six_consumed','prior_six_zero_consumed','joined_next_phase0')}
    for _ in range(250):
        if cpu.pc in stops:
            name=stops[cpu.pc]
            if legal:
                if context['kind']=='prior_six':
                    assert name in ('prior_six_consumed','prior_six_zero_consumed'),name
                    assert cpu.r[18]==context['history']
                    assert cpu.flag(6)==initial_T,'Actual-six entry changed its caller T'

                    expected=[0,2]
                else:
                    assert name=='joined_next_phase0',('legal path stopped',context['kind'],name)
                    at=context['logical'].index(context['physical'])
                    n=2 if context['wave'].bits[context['physical']] else 3
                    expected_bits=[context['wave'].bits[index] for index in context['logical'][at:at+n]]
                    history=context['history']
                    for bit in expected_bits:history=(history>>1)|(bit<<7)
                    assert cpu.r[18]==history,('rolling byte',cpu.r[18],history,expected_bits)
                    assert abs(cpu.t-(first+32))<1e-7,('join clock',cpu.t,first+32)
                    assert cpu.flag(6)==expected_T,('clock32 T marker',cpu.flag(6),expected_T)

                    expected=[0,2,10,12,21,23]
                read_clocks=[round(t+.5-h.SynchronizedPinIO.get.__globals__['APERTURE']-first,7)
                             for t,pc,level,cell in cpu.io.samples]
                assert read_clocks==expected,('capture clocks',read_clocks,expected)
            else:
                assert name=='rejected',('malformed first frame not rejected',name)
            live=[*range(16),20,21,22,23,24,25,26,27,28,29,30,31]
            assert all(cpu.r[i]==initial[i] for i in live)
            assert bytes(cpu.m)==memory and cpu.raw_stack==stack and not cpu.bus_events
            return dict(stop=name,time=cpu.t,history=cpu.r[18],T=cpu.flag(6),expected_T=expected_T if legal else None,samples=[(t,level) for t,pc,level,cell in cpu.io.samples])
        cpu.step()
    raise AssertionError('Entry component instruction bound')

contexts=[context_from(row) for row in FIXTURES]
rows=[];failures=[];counts=Counter()
for context in contexts:
    kind=context['kind'];p=context['physical'];wave=context['wave']
    variants=[(None,None,None)]
    edges=[index for index in range(p,min(p+3,len(wave.bits)))
           if wave.levels[index]!=wave.levels[index-1]]
    variants += [(edge,observed,fraction) for edge in edges for observed in (0,6)
                 for fraction in (1e-6,1/21,.5,20/21,1-1e-6)]
    for edge,observed,fraction in variants:
        incoming=wave if edge is None else single_crossover(copy.deepcopy(wave),edge,
                                  width=3.36,fraction=fraction,observed=observed)
        key=dict(kind=kind,rate=context['rate'],sign=context['sign'],origin=context['origin'],
                 physical=p,edge=edge,observed=observed,fraction=fraction)
        try:
            outcome=execute(context,incoming)
            row=dict(key,passed=True,stop=outcome['stop'],T=outcome['T'])
        except AssertionError as error:
            row=dict(key,passed=False,error=str(error));failures.append(row)
        counts[kind]+=1;rows.append(row)
assert counts==dict(fresh_one=567,fresh_zero=837,prior_six=297,cooldown_five=297)

context=next(context for context in contexts if context['kind']=='fresh_one' and
             context['rate']==1500000 and context['sign']==0 and context['origin_index']==2)
assert context['packet']==bytes.fromhex('c302c17e') and context['physical']==38
bad=from_bits(context['wave'].bits[:39],rate=1500000,width=10.72)
token=h.Wave(h.token(0x2d),rate=1500000,start=bad.boundaries[-2]+2*bad.period)
joined=Joined(bad,token)
negative=execute(context,joined,legal=False)
negative.update(next_sop=token.start,observations_during_next_token=sum(t>=token.start for t,level in negative['samples']))
assert negative['stop']=='rejected' and negative['time']<token.start
assert negative['observations_during_next_token']==0
t_counts=Counter(str(row['T']) for row in rows if row['passed'] and row['stop']=='joined_next_phase0')
assert t_counts==dict({'0':837,'1':864})
report=dict(bytes=ART['size'],sha256=ART['sha256'],counts=dict(counts),failures=len(failures),
            first_failures=failures[:4],clock32_T_counts=dict(t_counts),negative_guard=negative,
            fixtures_sha256=hashlib.sha256((HERE/'fixtures.py').read_bytes()).hexdigest(),
            scope='Synthetic PC-typed entry contracts only; no ordinary-caller or complete-USB integration.',rows=rows)
(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:value for key,value in report.items() if key!='rows'},indent=2))
raise SystemExit(bool(failures))
