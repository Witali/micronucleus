"""Build a same-size complete saved-phase PID7 guard as a separately sealed experiment.

The existing PLL prototype and its recorded failures remain immutable. Run
this with the normal LLVM/GNU AVR tools on PATH after building that prototype.
Generated files are restricted to a fresh directory below Flash-only/build.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys

BASE_BUNDLE='5cfd7684fcd8f95246d8f8ee467c08e8220db1b6f7cdebd368a81c95574b7a46'
BASE_BODY='d668eb3e8b59ecd8a641d77b4a00d38b45326efe9dd607c7d1b0d298b1c1999b'
NEW_BODY='8058c9de0496cf5fcb163d6f4fb453943da61bc29042c4a419c32e2147041147'
OLD='''    ifioset USBIN, USBMINUS
    rjmp hybrid_bad_pid_line
    andi shift, (255 ^ (1 << 7))
    eor r18, r16
    ldi r20, 2
    nop
    in r19, USBIN
    nop
    rjmp rx_p2_K_r{run}
'''
NEW='''    ifioset USBIN, USBMINUS
    rjmp hybrid_bad_pid_line
    andi r17, 6
    cpse r17, r21
    rjmp hybrid_bad_pid_line
    andi shift, (255 ^ (1 << 7))
    in r19, USBIN
    eor r18, r16
    rjmp rx_p2_K_r{run}
'''


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output-dir',type=Path,default=Path('build/pll-pid-guard-centered'))
    args=parser.parse_args();fo=args.firmware_root.resolve()
    base=fo/'prototypes/pll_extra6';allowed=(fo/'build').resolve()
    out=(fo/args.output_dir).resolve()
    assert allowed.is_relative_to(fo),'The build root must stay inside Flash-only'
    assert out.is_relative_to(allowed) and out!=allowed,'Output must be below Flash-only/build'
    assert not out.exists(),'Use a new output directory; existing evidence is never overwritten'
    manifest=base/'bundle-manifest.json'
    assert sha(manifest)==BASE_BUNDLE,'The original sealed source bundle changed'
    originals={manifest:BASE_BUNDLE}
    files=json.loads(manifest.read_text())['files']
    for relative,digest in files.items():
        source=(base/relative).resolve()
        assert source.is_relative_to(base) and sha(source)==digest,('Original source changed',relative)
        originals[source]=digest
    model_pins=json.loads((base/'model-inputs.json').read_text())
    for relative,digest in model_pins.items():
        path=fo.parent/relative
        assert sha(path)==digest,('Independent model changed',relative)
        originals[path]=digest
    # Pin the actual baseline symbols and bytes used for geometry comparison.
    base_report=json.loads((base/'build-report.json').read_text())
    for relative,digest in base_report['files'].items():
        path=base/'build'/relative
        assert path.is_file() and sha(path)==digest,('Build the original prototype first',relative)
        originals[path]=digest
    baseline=json.loads((base/'build/artifact.json').read_text())
    assert baseline['sha256']==BASE_BODY and baseline['size']==5634
    tool=Path(__file__).resolve();tool_digest=sha(tool)
    out.mkdir(parents=True)
    for relative in files:
        target=out/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(base/relative,target)
    composer=(out/'compose.py').read_text()

    # Keep the genuinely sampled phase independent of the J constant. The
    # entry MOV occurs after acquisition, at the same paid three-clock slot.
    anchor='# The final raw SET predecessor cannot be a valid complemented PID.'
    assert composer.count(anchor)==1
    composer=composer.replace(anchor,"""assert text.count('#define phase x3')==1
text=text.replace('#define phase x3','#define phase r17')
old_padding='pll128_pid0_sample:\\n    ifioset USBIN, USBMINUS\\n    ori shift, 1\\n    rjmp .+0\\n    rjmp .+0\\n    rjmp .+0\\n    rjmp .+0\\n    nop\\n'
new_padding='pll128_pid0_sample:\\n    ifioset USBIN, USBMINUS\\n    ori shift, 1\\n    rjmp .+0\\n    rjmp .+0\\n    lpm r23, Z\\n    rjmp .+0\\n'
assert text.count(old_padding)==1
text=text.replace(old_padding,new_padding)
"""+anchor)
    old_start="text=text.replace(needle,'pll128_pid_start:\\n    rjmp .+0\\n    ldi r21, 4\\n')"
    new_start="text=text.replace(needle,'pll128_pid_start:\\n    mov r17, r20\\n    ldi r20, 2\\n    ldi r21, 4\\n')"
    assert composer.count(old_start)==1
    composer=composer.replace(old_start,new_start)
    # Carry from CPI survives the intervening NOP and IN. Select the
    # run one paid slot earlier so both branches observe full phase at+1.
    old_run='''    andi shift, (255 ^ (3 << 6))
    cpi shift, 32
    nop
    nop
    in phase, USBIN
    brcs hybrid_run3_pad
    nop
    nop
'''
    new_run='''    andi shift, (255 ^ (3 << 6))
    cpi shift, 32
    nop
    brcs hybrid_run3_pad
    nop
    in phase, USBIN
    rjmp .+0
'''
    assert composer.count(old_run)==1
    composer=composer.replace(old_run,new_run)
    old_run3='hybrid_run3_pad:\n    nop\n'
    new_run3='hybrid_run3_pad:\n    in phase, USBIN\n    rjmp .+0\n'
    assert composer.count(old_run3)==1
    composer=composer.replace(old_run3,new_run3)
    assert composer.count(OLD)==1,'Reviewed final-one template no longer matches'
    (out/'compose.py').write_text(composer.replace(OLD,NEW),newline='\n')
    inputs=json.loads((out/'inputs.json').read_text())
    assert inputs['expected_body_sha256']==BASE_BODY and inputs['expected_bytes']==5634
    inputs['expected_body_sha256']=NEW_BODY
    inputs['provenance']['pid7_centered_phase_guard']=dict(parent_body=BASE_BODY,parent_bundle=BASE_BUNDLE,builder_sha256=tool_digest)
    write_json(out/'inputs.json',inputs)
    expected=json.loads((out/'expected-results.json').read_text())
    for summary in expected.values():
        assert summary['sha256']==BASE_BODY
        summary['sha256']=NEW_BODY
        summary['name']='pll-pid-guard-centered'
        summary['parent_first']=summary.pop('first',[])
    write_json(out/'expected-results.json',expected)

    def command(*argv):
        try:return subprocess.check_output(argv,cwd=out,text=True,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:print(exc.output);raise

    command(sys.executable,'build.py')
    artifact=json.loads((out/'build/artifact.json').read_text())
    assert artifact['size']==5634 and artifact['sha256']==NEW_BODY
    assert artifact['symbols'].keys()==baseline['symbols'].keys()
    changes={name:artifact['symbols'][name]-value for name,value in baseline['symbols'].items()
             if artifact['symbols'][name]!=value}
    assert changes=={'pll128_pid0_sample':2,'hybrid_pid7_run2':-2,'hybrid_run3_pad':-2},('Unexpected symbol geometry change',changes)
    assert artifact['boot']+artifact['size']<=8192
    command('avr-gcc','-mmcu=attiny88','-DLED_MODE=NONE',f"-DBOOT_AT={artifact['boot']}",
        '-I','inputs/vendor','-x','assembler-with-cpp','-c','build/candidate.S','-o','build/gnu.reloc.o')
    command('avr-ld','-m','avr25','--defsym=__TEXT_REGION_LENGTH__=0x10000','-Ttext=0',
        '-e','bootloader_start','-o','build/gnu.elf','build/gnu.reloc.o')
    command('avr-objcopy','-O','binary','-j','.text','build/gnu.elf','build/gnu.full.bin')
    gnu=(out/'build/gnu.full.bin').read_bytes()[artifact['boot']:]
    llvm=(out/'build/candidate.body.bin').read_bytes()
    assert gnu==llvm and hashlib.sha256(gnu).hexdigest()==NEW_BODY,'GNU/LLVM body mismatch'
    shutil.copyfile(out/'build/build-report.json',out/'build-report.json')
    provenance=dict(parent_bundle_sha256=BASE_BUNDLE,parent_body_sha256=BASE_BODY,
        body_sha256=NEW_BODY,size=5634,boot=artifact['boot'],builder_sha256=tool_digest,
        symbol_address_changes=changes,other_symbol_addresses_unchanged=True,gnu_llvm_body_identical=True,
        change='Full saved-phase K plus current D-minus. Last phase observation is centered+1clock onbothrun2/run3; guard/EXTRA/FIRST clocks unchanged. Paid phase transfer and equal-time padding keep word count.',
        qualification='Build and geometry only; component still has documented unfinished DATA rejections and no full protocol owner.')
    write_json(out/'derivation.json',provenance)
    shutil.copyfile(tool,out/'derive.py')
    relative_model=os.path.relpath(fo,out).replace('\\','/')
    (out/'README.md').write_text(f'''# Centered full-phase PID7 guard experiment

Derived from the unchanged sealed PLL prototype `{BASE_BODY}`.
Body:5634 bytes at0x0800,SHA256 `{NEW_BODY}`. GNU/LLVM bytes and every
linked symbol changes are checked exactly: PID0 label+2bytes and two
run-selection labels-2bytes. GPIO guard/FIRST calendars stay unchanged.

After acquisition, a paid MOV transfers the real phase from R20 to R17,
and R20/R21 become J/K constants. Every PLL phase read now uses R17.
The final-one path retains current D-minus-low and requires a centered
full phase sample to equal K. Run selection moves before the sample, giving
both supported run classes phase+1clock in the existing paid window. A late next-DATA transient can therefore
remain acceptable without inferring a missing PID bit from SE0 or SE1.
EXTRA remains at+6 and next FIRST at+10. Equal five-clock LPM/RJMP padding
pays the added startup word. R17 and R23 are explicit RX scratch; R0,
live X, context Z and external sample calendars remain protected.
No table, word-count growth, fixture phase injection or model change is used.

Run from this directory:

```sh
python3 verify.py --firmware-root {relative_model} --suite controls
python3 verify.py --firmware-root {relative_model} --suite full
python3 verify.py --firmware-root {relative_model} --suite payloads
python3 verify.py --firmware-root {relative_model} --suite fractional
python3 verify.py --firmware-root {relative_model} --suite fractional_min
```

The copied verifier reproduces documented snapshot behavior, including261
and165 unfinished DATA rejections. It does not claim complete USB correctness.
The external PID-prefix probe must separately report zero incompleteD2 EOF
tags. All sources and generated evidence remain inside this isolated build.
''',newline='\n')
    names=[*files,'derivation.json','derive.py']
    write_json(out/'bundle-manifest.json',dict(files={name:sha(out/name) for name in names}))
    for path,digest in originals.items():assert sha(path)==digest,('Original input changed during build',str(path))
    assert sha(tool)==tool_digest,'Builder changed during build'
    print(json.dumps(dict(output=str(out),**provenance),indent=2))


if __name__=='__main__':main()
