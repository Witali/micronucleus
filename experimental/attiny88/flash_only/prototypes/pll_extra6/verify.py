"""Read-only opcode verification against the repository's unchanged CPU model."""
from pathlib import Path
from types import SimpleNamespace
from collections import Counter
import argparse,hashlib,json,os,sys
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--firmware-root',type=Path,required=True,help='Existing experimental/attiny88/flash_only directory')
parser.add_argument('--suite',choices=('controls','full','payloads','fractional','fractional_min'),default='controls')
args=parser.parse_args();fo=args.firmware_root.resolve();attiny=fo.parent
pins=json.loads((HERE/'model-inputs.json').read_text())
sealed=json.loads((HERE/'bundle-manifest.json').read_text())
sealed_digest=hashlib.sha256((HERE/'bundle-manifest.json').read_bytes()).hexdigest()
build_report=json.loads((HERE/'build-report.json').read_text())
def integrity():
    def check(path,digest,kind):
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,(kind,str(path))
    check(HERE/'bundle-manifest.json',sealed_digest,'Bundle manifest changed during suite')
    for relative,digest in sealed['files'].items():check(HERE/relative,digest,'Offline source/manifest changed')
    for relative,digest in pins.items():check(attiny/relative,digest,'Independent model input changed')
    for relative,digest in build_report['files'].items():check(HERE/'build'/relative,digest,'Emitted source/ELF/manifest changed')
integrity()
os.environ['MICRONUCLEUS_TEST_MODEL_ROOT']=str(attiny/'compact')
sys.path.insert(0,str(fo))
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_usb_crossover import single_crossover
from tests35.rx_jitter_patterns import corners
from observe import run,configure
assert Path(h.__file__).resolve()==fo/'tests35/ep0_model.py','Model imported from unexpected checkout'
def artifact(path):
    a=json.loads(path.read_text())
    for k in ('bin','obj'):a[k]=HERE/a[k]
    a['body']=a['bin'].read_bytes()
    assert hashlib.sha256(a['body']).hexdigest()==a['sha256']
    return a
o=SimpleNamespace(h=h,bind=bind,core=SimpleNamespace(artifact=artifact))
a=configure(o,HERE/'build/artifact.json')
rows=[];first_trace=None
def case(group,packet,wave,entry,**context):
    global first_trace
    r=run(o,packet,wave,entry)
    rows.append(dict(group=group,packet=packet.hex(),entry=entry,context=context,**r))
    if r['errors'] and first_trace is None:first_trace=dict(group=group,packet=packet.hex(),entry=entry,context=context,**run(o,packet,wave,entry,True))
    if len(rows)%1000==0:print(json.dumps(dict(progress=len(rows),failures=sum(bool(x['errors']) for x in rows))),flush=True)
def pristine(packet,rate,sign):return h.Wave(packet,rate=rate,jitter=lambda i,l:sign*(.55 if l==h.J else -.55))
ENTRIES=(5,5.25,8,8.5,16,24,24.75,32,38,38.5,39)
FRACTIONS=(1/21,20/21)
def controls():
    packets=[h.data_packet(bytes([v])*8,pid=pid) for pid in (195,75) for v in (0,255,239)]
    packets += [h.token(pid) for pid in (225,105,45)]+[bytes([pid]) for pid in (210,90,30)]
    for packet in packets:
        for entry in (8,39):case('clean',packet,h.Wave(packet),entry)
def full():
    for packet in (h.data_packet(bytes([255])*8),bytes([0xd2])):
        for rate in (1499250,1500000,1500750):
            for sign in (-1,0,1):
                for left in (0,6):
                    for right in (0,6):
                        for lf in FRACTIONS:
                            for rf in FRACTIONS:
                                for entry in ENTRIES:
                                    wave=pristine(packet,rate,sign)
                                    single_crossover(wave,6,width=3.36,fraction=rf,observed=right)
                                    single_crossover(wave,5,width=3.36,fraction=lf,observed=left)
                                    case('sync_adjacent5_6',packet,wave,entry,rate=rate,sign=sign,observed=(left,right),fractions=(lf,rf))
            for corner,wave in enumerate(corners(h.Wave(packet,rate=rate))):
                for entry in ENTRIES:case('sync_edge_jitter',packet,wave,entry,rate=rate,corner=corner)
    packet=h.data_packet(bytes([255])*8)
    for rate in (1499250,1500000,1500750):
        for sign in (-1,0,1):
            wave=pristine(packet,rate,sign)
            edges=[i for i in range(8,len(wave.bits)) if wave.levels[i]!=wave.levels[i-1]]
            for observed in (0,6):
                for at in edges:
                    for fraction in FRACTIONS:
                        for entry in (5,8,16,24,32,38):
                            incoming=single_crossover(pristine(packet,rate,sign),at,width=3.36,fraction=fraction,observed=observed)
                            case('data_single',packet,incoming,entry,rate=rate,sign=sign,observed=observed,index=at,fraction=fraction)
                for fraction in FRACTIONS:
                    incoming=pristine(packet,rate,sign)
                    for at in reversed(edges):single_crossover(incoming,at,width=3.36,fraction=fraction,observed=observed)
                    for entry in (5,8,16,24,32,38):case('data_all_edges',packet,incoming,entry,rate=rate,sign=sign,observed=observed,fraction=fraction)
def payloads():
    for value in range(256):
        packet=h.data_packet(bytes([value]))
        for entry in (8,38.5):case('all_one_byte_values',packet,h.Wave(packet),entry,value=value)
    packets=[h.data_packet(bytes([v])*8,pid=pid) for pid in (195,75) for v in (0,255,170,85,191,21,159)]
    packets += [h.token(pid) for pid in (225,105,45)]+[bytes([210])]
    for packet in packets:
        for rate in (1499250,1500000,1500750):
            for sign in (-1,0,1):
                for entry in (5,8,16,24,32,38.5,39):case('payload_token_rates',packet,pristine(packet,rate,sign),entry,rate=rate,sign=sign)
    for value in (0,21,159):
        packet=h.data_packet(bytes([value])*8);wave=h.Wave(packet)
        edges=[i for i in range(8,len(wave.bits)) if wave.levels[i]!=wave.levels[i-1]]
        for index in [*edges,None]:
            for fraction in FRACTIONS:
                for entry in (8,16,38):
                    incoming=h.Wave(packet)
                    for edge in ([index] if index is not None else reversed(edges)):single_crossover(incoming,edge,width=3.36,fraction=fraction)
                    case('payload981',packet,incoming,entry,value=value,index=index,fraction=fraction)
    for kind,payload,rate,sign,entry,index,fraction in (
        ('next_stuffed_transition',bytes([239])*8,1500750,-1,8,82,FRACTIONS[1]),
        ('current_transition',bytes([239])*7+b'\xdb',1499250,1,5,81,FRACTIONS[0])):
        packet=h.data_packet(payload);wave=pristine(packet,rate,sign)
        single_crossover(wave,index,width=3.36,fraction=fraction)
        case(kind,packet,wave,entry,index=index,fraction=fraction,rate=rate,sign=sign)
    packet=h.data_packet(bytes(8));wave=pristine(packet,1500750,1)
    single_crossover(wave,13,width=3.36,fraction=FRACTIONS[1]);single_crossover(wave,12,width=3.36,fraction=FRACTIONS[0])
    case('adjacent_different',packet,wave,8)
def fractional(minimum=False):
    for value in (0,21,85,159,239,255):
        packet=h.data_packet(bytes([value])*8)
        for rate in (1499250,1500000,1500750):
            for sign in (-1,0,1):
                for entry in (5,8,16,24,32,38.5,39):
                    for extension in range(16):
                        wave=pristine(packet,rate,sign)
                        if minimum:
                            wave.boundaries[-2]=wave.boundaries[-3]+10.72
                            wave.boundaries[-1]=wave.boundaries[-2]+wave.period
                        for at in (-3,-2,-1):wave.boundaries[at]+=extension/16*wave.period
                        wave.end=wave.boundaries[-1]
                        case('fractional_min' if minimum else 'fractional',packet,wave,entry,value=value,rate=rate,sign=sign,extension=extension/16)
def fractional_min():fractional(True)
try:globals()[args.suite]()
finally:integrity()
bad=[r for r in rows if r['errors']]
for row in bad:
    errors=row['errors']
    assert len(errors)==2 and {e['kind'] for e in errors}=={'reject','count'},('Unexpected failure type',row)
    rejection=next(e for e in errors if e['kind']=='reject')
    count=next(e for e in errors if e['kind']=='count')
    assert rejection['name'].endswith('_unfunded'),('Unexpected rejection',row)
    assert row['stop']==dict(kind='reject',name=rejection['name']),('Rejection stop mismatch',row)
    assert count['got']==row['bits']<count['wanted']==len(bytes.fromhex(row['packet']))*8,('Expected short count',row)
summary=dict(bytes=a['size'],sha256=a['sha256'],suite=args.suite,cases=len(rows),failures=len(bad),
    entry_sreg_t=0,
    groups=dict(Counter(r['group'] for r in rows)),failure_groups=dict(Counter(r['group'] for r in bad)),
    error_kinds=dict(Counter(e['kind'] for r in bad for e in r['errors'])),first=bad[:4],
    scope='Offline component: actual acquisition/PID, each DATA bit, 0..6 tail ones and EOF tag. No packet admission, SRAM publication or ACK claim.')
(HERE/'build'/f'{args.suite}-results.json').write_text(json.dumps(dict(summary=summary,rows=rows),indent=2)+'\n')
(HERE/'build'/f'{args.suite}-first-failure.json').write_text(json.dumps(first_trace,indent=2)+'\n')
expected=json.loads((HERE/'expected-results.json').read_text())[args.suite]
assert (len(rows),len(bad))==(expected['cases'],expected['failures']),('Snapshot behavior changed',summary)
assert summary['groups']==expected['groups'],('Case groups changed',summary)
assert summary['failure_groups']==expected['failure_groups'],('Failure groups changed',summary)
integrity()
print(json.dumps(summary,indent=2),flush=True)
