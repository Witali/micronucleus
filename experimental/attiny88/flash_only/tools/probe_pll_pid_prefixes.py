"""Probe incomplete-PID EOF ambiguity in the offline PLL experiment.

Run from the repository with the existing experiment already built. This
starts the real USB_handler at a normal cooperative entry; no CPU registers,
PC, phase or handoff clock are supplied by the probe. EOF is a component tag,
not demonstrated ACK retirement, transmission, or full USB qualification.
Default exit is nonzero for incomplete-prefix D2+EOF or failed valid controls.
--expect-known-failure is explicit snapshot reproduction, not qualification.
"""
from pathlib import Path
from types import SimpleNamespace
from collections import Counter
import argparse,hashlib,importlib.util,json,os,sys

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--experiment',type=Path)
    parser.add_argument('--suite',choices=('truncated','whole-prefix','held-se1','eop-se1'),default='truncated')
    parser.add_argument('--expect-known-failure',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();fo=args.firmware_root.resolve()
    sealed=fo/'prototypes/pll_extra6';experiment=(args.experiment or sealed).resolve()
    ap=experiment/'build/artifact.json'
    if not ap.exists():ap=experiment/'artifact.json'
    artifact=json.loads(ap.read_text())
    for key in ('obj','bin'):
        value=artifact[key]
        if os.name=='nt' and value.startswith('/mnt/c/'):value='C:/'+value[7:]
        path=Path(value);artifact[key]=path if path.is_absolute() else experiment/path
    artifact['body']=artifact['bin'].read_bytes()
    assert hashlib.sha256(artifact['body']).hexdigest()==artifact['sha256']
    pins={}
    def pin(path,expected=None):
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert expected is None or digest==expected,('Input integrity',str(path))
        pins[path]=digest
    pin(Path(__file__).resolve())
    pin(sealed/'bundle-manifest.json')
    for relative,digest in json.loads((sealed/'bundle-manifest.json').read_text())['files'].items():pin(sealed/relative,digest)
    for relative,digest in json.loads((sealed/'model-inputs.json').read_text()).items():pin(fo.parent/relative,digest)
    for path in (ap,ap.with_name('manifest.json'),artifact['obj'],artifact['bin']):pin(path)
    if experiment==sealed:
        for relative,digest in json.loads((sealed/'build-report.json').read_text())['files'].items():pin(sealed/'build'/relative,digest)
    else:
        # Derived experiments must pin their generation sources as well as
        # the emitted ELF/body; a changed template is a different experiment.
        derived_manifest=experiment/'bundle-manifest.json'
        if derived_manifest.is_file():
            pin(derived_manifest)
            for relative,digest in json.loads(derived_manifest.read_text())['files'].items():
                source=(experiment/relative).resolve()
                assert source.is_relative_to(experiment),'Derived manifest path escapes experiment'
                pin(source,digest)
            report=json.loads((experiment/'build-report.json').read_text())
            for relative,digest in report['files'].items():pin(ap.parent/relative,digest)
        for name in ('vusb_phy.inc','source.json'):
            if (ap.parent/name).exists():pin(ap.parent/name)
    os.environ['MICRONUCLEUS_TEST_MODEL_ROOT']=str(fo.parent/'compact');sys.path.insert(0,str(fo))
    from tests35 import ep0_model as h
    from tests35.ep0_cases import bind
    from tests35.phy_model import from_bits
    for name in ('test_ack_pid_prefix.py','test_ack_empty_pid.py','phy_model.py'):pin(fo/'tests35'/name)
    spec=importlib.util.spec_from_file_location('sealed_pll_observer',sealed/'observe.py')
    observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
    o=SimpleNamespace(h=h,bind=bind,core=SimpleNamespace(artifact=lambda p:artifact))
    observer.configure(o,ap)
    def run(wave,entry):
        bind(artifact);cpu=h.CPU(artifact,wave,entry);handoff=None;shift_count=0
        for _ in range(6000):
            if cpu.pc in o.FIRSTS and handoff is None:
                handoff=dict(time=cpu.t,assembled_pid=cpu.r[18],entry=o.FIRSTS[cpu.pc]['name'])
            if cpu.pc in o.EOPS or cpu.pc in o.REJECTS or cpu.pc==0xfffe:
                result=dict(handoff=handoff,eof_tag=cpu.pc in o.EOPS,graph_shifts=shift_count,
                    stop=o.EOPS.get(cpu.pc,{}).get('name',o.REJECTS.get(cpu.pc,'returned')),time=cpu.t)
                result['recent_samples']=cpu.io.samples[-12:]
                return result
            shift_count+=int(cpu.pc in o.SHIFTS);cpu.step()
        raise AssertionError('Component exceeded instruction bound')
    def wave_for(bits,rate,width,sign):
        # Unchanged construction in tests35/test_ack_pid_prefix.py:19..33.
        wave=from_bits(bits,rate=rate,width=width)
        for i,line in enumerate(wave.levels[:-3]):wave.boundaries[i]+=sign*(.55 if line==h.J else -.55)
        wave.pin_edges=[];before=h.J
        for when,line in zip(wave.boundaries,wave.levels):
            if (before^line)&4:wave.pin_edges.append(when)
            before=line
        return wave
    sync=h.Wave(b'').bits;assert sync==[0,0,0,0,0,0,0,1]
    counts=Counter();by_length={};first=None
    def cases(length,pattern,category):
        nonlocal first
        bits=sync+[(pattern>>i)&1 for i in range(length)]
        for rate in (1499250,1500000,1500750):
            for width in (10.72,64/3,24):
                for sign in (-1,0,1):
                    wave=wave_for(bits,rate,width,sign)
                    for entry in (5,8,16,24,32,38):
                        row=run(wave,entry);d2=bool(row['handoff'] and row['handoff']['assembled_pid']==0xd2)
                        counts[category+'_cases']+=1
                        if category=='valid':counts['valid_control_failures']+=int(not(d2 and row['eof_tag']))
                        else:
                            counts['assembled_d2_handoffs']+=int(d2)
                            counts['incomplete_d2_eof_tags']+=int(d2 and row['eof_tag'])
                            counts['d2_handoffs_eventually_rejected']+=int(d2 and not row['eof_tag'])
                            group=by_length.setdefault(str(length),Counter());group['cases']+=1
                            group['assembled_d2_handoffs']+=int(d2);group['incomplete_d2_eof_tags']+=int(d2 and row['eof_tag'])
                            if d2 and row['eof_tag'] and first is None:
                                first=dict(physical_pid_bits=length,pattern=pattern,rate=rate,width=width,sign=sign,
                                    entry=entry,eop_se0=wave.boundaries[-3],recovery_j=wave.boundaries[-2],**row)
    def held_se1():
        nonlocal first
        # A full ACK whose last physical PID symbol is held SE1 is malformed.
        # Keep original raw waves and all eleven real cooperative entry times.
        for rate in (1499250,1500000,1500750):
            for sign in (-1,0,1):
                for entry in (5,5.25,8,8.5,16,24,24.75,32,38,38.5,39):
                    wave=h.Wave(bytes([0xd2]),rate=rate,
                        jitter=lambda i,line:sign*(.55 if line==h.J else -.55))
                    assert len(wave.bits)==16
                    wave.levels[15]=6
                    wave.pin_edges=[];previous=h.J
                    for when,line in zip(wave.boundaries,wave.levels):
                        if (previous^line)&4:wave.pin_edges.append(when)
                        previous=line
                    row=run(wave,entry)
                    d2=bool(row['handoff'] and row['handoff']['assembled_pid']==0xd2)
                    counts['held_se1_cases']+=1
                    counts['malformed_se1_d2_eof_tags']+=int(d2 and row['eof_tag'])
                    if d2 and row['eof_tag'] and first is None:
                        first=dict(malformed='held_SE1_at_PID7',rate=rate,sign=sign,entry=entry,**row)

    def eop_se1():
        nonlocal first
        # Seven real PID bits followed by observed SE1 inside an otherwise
        # SE0 EOP must not become a complete D2. The pulses are malformed
        # physical inputs, not waived numeric DATA-CRC errors.
        bits=sync+[(0xd2>>i)&1 for i in range(7)]
        for rate in (1499250,1500000,1500750):
            for sign in (-1,0,1):
                for entry in (5,5.25,8,8.5,16,24,24.75,32,38,38.5,39):
                    for offset in (.125,2.125,4.125):
                        wave=wave_for(bits,rate,64/3,sign)
                        at=len(wave.levels)-3;start=wave.boundaries[at]
                        wave.boundaries[at+1:at+1]=[start+offset,start+offset+3.36]
                        wave.levels[at+1:at+1]=[6,0]
                        wave.labels[at+1:at+1]=['bad-SE1','SE0-resume']
                        wave.pin_edges=[];previous=h.J
                        for when,line in zip(wave.boundaries,wave.levels):
                            if (previous^line)&4:wave.pin_edges.append(when)
                            previous=line
                        row=run(wave,entry)
                        d2=bool(row['handoff'] and row['handoff']['assembled_pid']==0xd2)
                        counts['eop_se1_cases']+=1
                        counts['malformed_eop_se1_d2_eof_tags']+=int(d2 and row['eof_tag'])
                        if d2 and row['eof_tag'] and first is None:
                            first=dict(malformed='observed_SE1_in_incomplete_PID_EOP',rate=rate,sign=sign,
                                entry=entry,eop_start=start,se1_start=start+offset,**row)

    # All suites retain empty-PID and complete genuine ACK controls.
    cases(0,0,'empty');cases(8,0xd2,'valid')
    if args.suite=='held-se1':held_se1()
    elif args.suite=='eop-se1':eop_se1()
    else:
        for length in range(1,8):
            patterns=range(1<<length) if args.suite=='whole-prefix' else (0xd2&((1<<length)-1),)
            for pattern in patterns:cases(length,pattern,'prefix')
    for path,digest in pins.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,('Input changed during suite',str(path))
    failed=bool(counts['incomplete_d2_eof_tags'] or counts['valid_control_failures'] or
                counts['malformed_se1_d2_eof_tags'] or counts['malformed_eop_se1_d2_eof_tags'])
    result=dict(suite=args.suite,bytes=artifact['size'],sha256=artifact['sha256'],
        total_cases=sum(counts[k] for k in ('empty_cases','valid_cases','prefix_cases','held_se1_cases','eop_se1_cases')),
        tool_sha256=pins[Path(__file__).resolve()],
        elf_sha256=hashlib.sha256(artifact['obj'].read_bytes()).hexdigest(),counts=dict(counts),by_physical_pid_length=by_length,
        qualification_passed=not failed,snapshot_reproduction=args.expect_known_failure,
        input_integrity='Source/model/manifest/body/ELF checked before and after suite',first_incomplete_d2_eof=first,
        scope='Incomplete-PID or malformed held-SE1 framing ambiguity at decoded-D2 plus component EOF-ready tag. Provisional handoffs that later reject are counted separately. No protocol owner, ACK release, bus response or full USB qualification is demonstrated.')
    status=int(failed)
    if args.expect_known_failure:
        expected_prefix=41148 if args.suite=='whole-prefix' else 1134
        reproduced=(artifact['sha256']=='d668eb3e8b59ecd8a641d77b4a00d38b45326efe9dd607c7d1b0d298b1c1999b'
            and counts['prefix_cases']==expected_prefix and counts['empty_cases']==162 and counts['valid_cases']==162
            and counts['assembled_d2_handoffs']==270 and counts['incomplete_d2_eof_tags']==108
            and not counts['valid_control_failures'])
        result['known_failure_snapshot_matches']=reproduced;status=0 if reproduced else 1
    output=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(output)
    print(output,end='');return status

if __name__=='__main__':raise SystemExit(main())
