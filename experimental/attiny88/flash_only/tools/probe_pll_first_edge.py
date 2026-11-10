"""Compare real PLL acquisition across combined SYNC/first-DATA crossings.

This preserves a valid-wave regression missed by the earlier separate SYNC
and DATA matrices. It reports relative component behavior, not full USB
qualification. A new lost PID handoff or a newly failed formerly clean case
returns nonzero. Neither CPU state nor handoff time is supplied by the probe.
With --require-complete, any candidate error also fails the reception gate;
an unchanged historical failure is never accepted in that mode.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse,hashlib,importlib.util,itertools,json,os,sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--experiment',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--require-complete',action='store_true',help='Require zero candidate reception errors, including pre-existing failures')
    args=parser.parse_args();fo=args.firmware_root.resolve();base=fo/'prototypes/pll_extra6'
    experiment=args.experiment.resolve();pins={}
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    def pin(path,expected=None):
        digest=sha(path);assert expected is None or digest==expected,('Input changed',str(path));pins[path]=digest
    pin(Path(__file__).resolve())
    for root in (base,experiment):
        manifest=root/'bundle-manifest.json';pin(manifest)
        for relative,digest in json.loads(manifest.read_text())['files'].items():
            source=(root/relative).resolve();assert source.is_relative_to(root)
            pin(source,digest)
        report=json.loads((root/'build-report.json').read_text())
        for relative,digest in report['files'].items():pin(root/'build'/relative,digest)
    for relative,digest in json.loads((base/'model-inputs.json').read_text()).items():pin(fo.parent/relative,digest)
    os.environ['MICRONUCLEUS_TEST_MODEL_ROOT']=str(fo.parent/'compact');sys.path.insert(0,str(fo))
    from tests35 import ep0_model as h
    from tests35.ep0_cases import bind
    from tests35.test_usb_crossover import single_crossover
    pin(fo/'tests35/test_usb_crossover.py')
    spec=importlib.util.spec_from_file_location('sealed_first_edge_observer',base/'observe.py')
    observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
    def configure(root):
        art=json.loads((root/'build/artifact.json').read_text())
        for field in ('obj','bin'):
            value=Path(art[field]);art[field]=value if value.is_absolute() else root/value
        art['body']=art['bin'].read_bytes();assert hashlib.sha256(art['body']).hexdigest()==art['sha256']
        o=SimpleNamespace(h=h,bind=bind,core=SimpleNamespace(artifact=lambda p:art))
        observer.configure(o,root/'build/artifact.json');return o
    old,new=configure(base),configure(experiment)
    entries=(5,5.25,8,8.5,16,24,24.75,32,38,38.5,39)
    fractions=(1/21,20/21)
    syncs=[None]+list(itertools.product((0,6),(0,6),fractions,fractions))
    count=0;failure=None;first_candidate_failure=None;new_missing_handoff=0;old_failed=0;new_failed=0
    for packet in (h.data_packet(bytes(8)),h.token(0xe1)):
        for sync in syncs:
            for rate,sign,observed,fraction,entry in itertools.product((1499250,1500000,1500750),(-1,0,1),(0,6),fractions,entries):
                wave=h.Wave(packet,rate=rate,jitter=lambda i,line:sign*(.55 if line==h.J else -.55))
                edge=next(i for i in range(16,len(wave.bits)) if wave.levels[i]!=wave.levels[i-1])
                # Insert later physical edges first; earlier inserts would
                # otherwise change the original edge's list index.
                single_crossover(wave,edge,width=3.36,fraction=fraction,observed=observed)
                if sync:
                    left,right,lf,rf=sync
                    single_crossover(wave,6,width=3.36,fraction=rf,observed=right)
                    single_crossover(wave,5,width=3.36,fraction=lf,observed=left)
                result=observer.run(new,packet,wave,entry)
                control=observer.run(old,packet,wave,entry)
                count+=1;old_failed+=bool(control['errors']);new_failed+=bool(result['errors'])
                new_missing_handoff+=result['handoff'] is None
                if result['errors'] and first_candidate_failure is None:
                    first_candidate_failure=dict(packet=packet.hex(),sync=sync,rate=rate,sign=sign,observed=observed,
                        fraction=fraction,entry=entry,edge=edge,boundaries=wave.boundaries,
                        candidate=observer.run(new,packet,wave,entry,True))
                if (result['handoff'] is None and control['handoff'] is not None) or (result['errors'] and not control['errors']):
                    failure=dict(packet=packet.hex(),sync=sync,rate=rate,sign=sign,observed=observed,
                        fraction=fraction,entry=entry,edge=edge,boundaries=wave.boundaries,
                        old=observer.run(old,packet,wave,entry,True),new=observer.run(new,packet,wave,entry,True))
                    break
            if failure:break
        if failure:break
    for path,digest in pins.items():assert sha(path)==digest,('Input changed during corpus',str(path))
    report=dict(cases=count,old_body=old.ART['sha256'],new_body=new.ART['sha256'],
        baseline_failed_cases=old_failed,candidate_failed_cases=new_failed,
        candidate_missing_handoff_cases=new_missing_handoff,new_regression=failure,
        first_candidate_failure=first_candidate_failure,reception_passed=new_failed==0,
        require_complete=args.require_complete,
        regression_free=failure is None,complete=count==13464,
        scope='Combined legal SYNC and first-DATA/address crossings; incomplete component failures remain reported. No full USB, publication, hardware or protocol-owner qualification.')
    output=json.dumps(report,indent=2)+'\n'
    if args.output:args.output.write_text(output)
    print(json.dumps({k:v for k,v in report.items() if k not in ('new_regression','first_candidate_failure')},indent=2),flush=True)
    if failure:print(json.dumps(dict(first_new_regression={k:failure[k] for k in ('packet','sync','rate','sign','observed','fraction','entry','edge')}),indent=2),flush=True)
    return int(failure is not None or count!=13464 or (args.require_complete and new_failed))


if __name__=='__main__':raise SystemExit(main())
