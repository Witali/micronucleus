"""Offline AVR build using frozen inputs; never select this image as firmware."""
from pathlib import Path
import hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent
def command(*args):
    try:return subprocess.check_output(args,cwd=HERE,text=True,stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:print(exc.output);raise
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
inputs=json.loads((HERE/'inputs.json').read_text())
for relative,digest in inputs['files'].items():assert sha(HERE/relative)==digest,('Frozen input changed',relative)
command(sys.executable,'compose.py')
out=HERE/'build';boot=inputs['boot']
flags=['-target','avr','-mmcu=attiny88','-DLED_MODE=NONE',f'-DBOOT_AT={boot}','-I','inputs/vendor','-x','assembler-with-cpp']
command('clang',*flags,'-c','build/candidate.S','-o','build/candidate.reloc.o')
command('avr-ld','-m','avr25','--defsym=__TEXT_REGION_LENGTH__=0x10000','-Ttext=0','-e','bootloader_start','-o','build/candidate.elf','build/candidate.reloc.o')
assert 'R_AVR_' not in command('llvm-objdump','-r','build/candidate.elf')
assert not command('llvm-nm','--undefined-only','build/candidate.elf').strip()
command('llvm-objcopy','-O','binary','-j','.text','build/candidate.elf','build/whole.bin')
blob=(out/'whole.bin').read_bytes();assert blob[:boot]==bytes(boot)
body=blob[boot:];(out/'candidate.body.bin').write_bytes(body)
assert len(body)==inputs['expected_bytes'] and boot+len(body)<=8192
assert sha(out/'candidate.body.bin')==inputs['expected_body_sha256'],'Emitted code differs from reported snapshot'
symbols={}
for row in command('llvm-nm','-n','build/candidate.elf').splitlines():
    f=row.split()
    if len(f)==3:symbols[f[2]]=int(f[0],16)
artifact=dict(boot=boot,size=len(body),sha256=sha(out/'candidate.body.bin'),obj='build/candidate.elf',bin='build/candidate.body.bin',symbols=symbols)
(out/'artifact.json').write_text(json.dumps(artifact,indent=2)+'\n')
command('clang',*flags,'-E','build/candidate.S','-o','build/preprocessed.S')
# The current independent executor does not model ATtiny88 modulo-PC wrapping.
# Require unwrapped source edges for coverage by this tool. Valid hardware PC
# wrapping is not inherently a linker or firmware defect.
pc=0;labels={};edges=[];instructions=0
for raw in (out/'preprocessed.S').read_text().splitlines():
    row=raw.strip()
    if not row or row.startswith(('#','/*','*','//')):continue
    if row.endswith(':'):labels[row[:-1]]=pc;continue
    if row.startswith('.org '):pc=int(row.split()[1],0);continue
    if row.startswith('.'):continue
    op,*rest=row.split(None,1)
    if op in ('rjmp','rcall'):
        target=rest[0].strip()
        if not target.startswith('.'):edges.append((pc,target,2048))
    elif op.startswith('br'):edges.append((pc,rest[0].split(',')[-1].strip(),64))
    assert op not in ('jmp','call','lds','sts'),('Unexpected two-word instruction',row)
    pc+=2;instructions+=1
for label,value in labels.items():assert symbols[label]==value,('Source/ELF label mismatch',label)
for at,target,limit in edges:
    span=(labels[target]-at-2)//2
    assert -limit<=span<limit,('Wrapped source edge outside executor coverage',at,target,span)
report=dict(boot=boot,bytes=len(body),body_sha256=artifact['sha256'],elf_sha256=sha(out/'candidate.elf'),
    generated_phy_sha256=sha(out/'vusb_phy.inc'),labels=len(labels),instructions=instructions,relative_edges=len(edges),
    rjmp_max_span=max(abs((labels[t]-p-2)//2) for p,t,n in edges if n==2048),
    branch_max_span=max(abs((labels[t]-p-2)//2) for p,t,n in edges if n==64),
    clang=command('clang','--version').splitlines()[0],avr_ld=command('avr-ld','--version').splitlines()[0])
report['files']={name:sha(out/name) for name in ('candidate.S','vusb_phy.inc','source.json','manifest.json',
    'candidate.elf','candidate.body.bin','artifact.json')}
(out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
