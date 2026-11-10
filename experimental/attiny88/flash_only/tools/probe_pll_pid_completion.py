"""Retire the late PID pin poll after the centered full-K completeness proof.

Derive a fresh offline component from probe_pll_recovery.py's pinned 7346-byte
reference. The three last-PID-one paths retain their original two-clock slot
and EXTRA/FIRST calendars. No maintained firmware, observer or model is edited.
This is a receiver component, not a selectable firmware or packet owner.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

OLD_BODY = '56e8816afe4b42e1a472992eeabe78478bc082e5a6e53d494ec1b58b343a5611'
NEW_BODY = '8d07720c576bf59f2974a9f971567f8d35b39c897adc96e2144c5e8981f437fb'
COMPOSER = '86afc4b0be7c0f8b3d2629659d194e3397a56b5e2ae516426fdbdc175219a812'
VERIFIER = 'a69103ab63370d26276ab9fecd4a27a0bfd9f96067d9254c4f726d1c2e83f60c'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--reference-dir', type=Path, default=Path('build/pll-shared-recovery'))
    parser.add_argument('--output-dir', type=Path, default=Path('build/pll-pid-complete'))
    args = parser.parse_args()
    fo = args.firmware_root.resolve()
    allowed = (fo / 'build').resolve()
    base = (fo / args.reference_dir).resolve()
    out = (fo / args.output_dir).resolve()
    assert base.is_relative_to(allowed) and base != allowed
    assert out.is_relative_to(allowed) and out != allowed and not out.exists(), 'Use a fresh Flash-only/build directory'
    original = {}

    def pin(path, expected=None):
        digest = sha(path)
        assert expected is None or digest == expected, ('Original input changed', str(path))
        original[path] = digest

    manifest = base / 'bundle-manifest.json'
    pin(manifest)
    files = json.loads(manifest.read_text())['files']
    for relative, digest in files.items():
        path = (base / relative).resolve()
        assert path.is_relative_to(base)
        pin(path, digest)
    pin(base / 'compose.py', COMPOSER)
    pin(base / 'verify.py', VERIFIER)
    for relative, digest in json.loads((base / 'model-inputs.json').read_text()).items():
        path = (fo.parent / relative).resolve()
        assert path.is_relative_to(fo.parent)
        pin(path, digest)
    parent_report = json.loads((base / 'build-report.json').read_text())
    for relative, digest in parent_report['files'].items():
        path = (base / 'build' / relative).resolve()
        assert path.is_relative_to(base / 'build')
        pin(path, digest)
    parent = json.loads((base / 'build/artifact.json').read_text())
    assert (parent['boot'], parent['size'], parent['sha256']) == (512, 7346, OLD_BODY)
    tool = Path(__file__).resolve()
    pin(tool)
    out.mkdir(parents=True)
    for relative in files:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / relative, target)
    # Patch the single generating template, not just an emitted assembly file.
    # A valid centered full-pin K sample proves PID7. The later D-minus poll
    # can already fall inside the next valid DATA transition's SE1 crossover.
    composer = (out / 'compose.py').read_text()
    before = "return f'''{label}:\n    ifioset USBIN, USBMINUS\n    rjmp hybrid_bad_pid_line\n    andi r17, 6\n"
    after = "return f'''{label}:\n    rjmp .+0\n    andi r17, 6\n"
    assert composer.count(before) == 1
    (out / 'compose.py').write_text(composer.replace(before, after), newline='\n')
    inputs = json.loads((out / 'inputs.json').read_text())
    inputs['expected_bytes'], inputs['expected_body_sha256'] = 7340, NEW_BODY
    for relative in inputs['files']:
        inputs['files'][relative] = sha(out / relative)
    provenance = dict(parent_body_sha256=OLD_BODY, parent_bundle_sha256=sha(manifest),
        parent_composer_sha256=COMPOSER, strict_verifier_sha256=VERIFIER, builder_sha256=sha(tool),
        change='Three late D-minus guards become equal-two-clock RJMPs; centered full saved-K proof and subsequent GPIO clocks remain.')
    inputs['provenance']['pid_completion'] = provenance
    write_json(out / 'inputs.json', inputs)

    def command(*argv):
        try:
            return subprocess.check_output(argv, cwd=out, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            print(exc.output)
            raise

    command(sys.executable, 'build.py')
    artifact = json.loads((out / 'build/artifact.json').read_text())
    assert (artifact['boot'], artifact['size'], artifact['sha256']) == (512, 7340, NEW_BODY)
    # Certify that composition changed exactly the reviewed three guard pairs.
    expected = (base / 'build/vusb_phy.inc').read_text()
    for label in ('pll128_bit7AfterClr', 'hybrid_pid7_run2', 'hybrid_pid7_run3'):
        before = f'{label}:\n    ifioset USBIN, USBMINUS\n    rjmp hybrid_bad_pid_line\n'
        assert expected.count(before) == 1
        expected = expected.replace(before, f'{label}:\n    rjmp .+0\n')
    assert (out / 'build/vusb_phy.inc').read_text() == expected
    assert sha(out / 'verify.py') == VERIFIER, 'The strict positive oracle must remain unchanged'
    command('avr-gcc', '-mmcu=attiny88', '-DLED_MODE=NONE', '-DBOOT_AT=512', '-I', 'inputs/vendor', '-x', 'assembler-with-cpp', '-c', 'build/candidate.S', '-o', 'build/gnu.o')
    command('avr-ld', '-m', 'avr25', '--defsym=__TEXT_REGION_LENGTH__=0x2000', '-Ttext=0', '-e', 'bootloader_start', '-o', 'build/gnu.elf', 'build/gnu.o')
    command('avr-objcopy', '-O', 'binary', '-j', '.text', 'build/gnu.elf', 'build/gnu.whole.bin')
    whole = (out / 'build/gnu.whole.bin').read_bytes()
    body = (out / 'build/candidate.body.bin').read_bytes()
    assert whole[:512] == bytes(512) and whole[512:] == body, 'GNU/LLVM bytes differ'
    gnu_symbols = {}
    for row in command('avr-nm', '-n', 'build/gnu.elf').splitlines():
        fields = row.split()
        if len(fields) == 3:
            gnu_symbols[fields[2]] = int(fields[0], 16)
    # Check physical fit and actual encoded destinations; source ranges alone
    # could miss an accidentally wrapped or truncated linker displacement.
    labels, edges, pc, instructions = {}, [], 0, 0
    for raw in (out / 'build/preprocessed.S').read_text().splitlines():
        row = raw.strip()
        if not row or row.startswith(('#', '/*', '*', '//')):
            continue
        if row.endswith(':'):
            labels[row[:-1]] = pc
            continue
        if row.startswith('.org '):
            pc = int(row.split()[1], 0)
            continue
        if row.startswith('.'):
            continue
        op, *rest = row.split(None, 1)
        assert op not in ('jmp', 'call', 'lds', 'sts'), ('Unexpected two-word instruction', row)
        if op in ('rjmp', 'rcall') and not rest[0].strip().startswith('.'):
            edges.append((pc, op, rest[0].strip()))
        elif op.startswith('br'):
            edges.append((pc, op, rest[0].split(',')[-1].strip()))
        pc += 2
        instructions += 1
    assert pc == 512 + 7340 <= 8192
    for name, at in labels.items():
        assert artifact['symbols'][name] == gnu_symbols[name] == at, ('Source/LLVM/GNU symbol mismatch', name)
    for at, op, target in edges:
        word = int.from_bytes(body[at - 512:at - 510], 'little')
        if op in ('rjmp', 'rcall'):
            assert word & 0xf000 == (0xc000 if op == 'rjmp' else 0xd000)
            value, width = word & 4095, 12
        else:
            assert word & 0xfc00 in (0xf000, 0xf400)
            value, width = (word >> 3) & 127, 7
        displacement = value - (1 << width) if value & (1 << (width - 1)) else value
        assert at + 2 + displacement * 2 == labels[target], ('Wrapped/truncated encoded edge', at, op, target)
    write_json(out / 'edge-audit.json', dict(bytes=7340, boot=512, end_exclusive=pc,
        labels=len(labels), instructions=instructions, named_relative_edges=len(edges), wrapped_edges=0,
        gnu_llvm_body_identical=True, body_sha256=NEW_BODY))
    shutil.copyfile(out / 'build/build-report.json', out / 'build-report.json')
    shutil.copyfile(base / 'derive.py', out / 'parent-derive.py')
    shutil.copyfile(tool, out / 'derive.py')
    write_json(out / 'pid-completion-provenance.json', provenance)
    relative_fo = os.path.relpath(fo, out).replace('\\', '/')
    (out / 'README.md').write_text(f'''# Centered PID completeness without the late pin poll

Offline receiver component: 7340 bytes at 0x0200, SHA-256 `{NEW_BODY}`.
Only the three final-one current-D-minus guard pairs changed into two-clock
RJMPs. The centered full saved-K check remains, and EXTRA/FIRST GPIO calendars
are preserved. This removes the known valid next-DATA SE1 rejection and saves
six bytes. GNU/LLVM bytes, source/encoded relative edges and physical fit are
checked. There is no packet publication, protocol owner, ACK or full USB claim.

Run `python3 verify.py --firmware-root {relative_fo} --suite controls`, then
`full`, `payloads`, `fractional`, `fractional_min`: all 24731 cases must pass,
with unchanged strict oracle and exact corpus counts. The separate absolute
combined SYNC/first-DATA-edge probe must pass all 13464; a comparison that only
rejects newly introduced failures is insufficient. Keep the whole-prefix,
held-SE1, EOP-SE1 and adjacent-token negative gates unchanged. Diagnostic K/J
pulses have no automatic mandatory rejection assertion based on Wave.bits.
''', newline='\n')
    names = sorted(set(files) | {'parent-derive.py', 'pid-completion-provenance.json'})
    write_json(out / 'bundle-manifest.json', dict(files={name: sha(out / name) for name in names}))
    for path, digest in original.items():
        assert sha(path) == digest, ('Original source/model/evidence changed', str(path))
    print(json.dumps(dict(output=str(out), bytes=7340, boot=512, sha256=NEW_BODY,
        generated_phy_sha256=sha(out / 'build/vusb_phy.inc'), elf_sha256=sha(out / 'build/candidate.elf'),
        bundle_manifest_sha256=sha(out / 'bundle-manifest.json'), original_inputs_unchanged=True,
        strict_verifier_unchanged=True, gnu_llvm_body_identical=True), indent=2))


if __name__ == '__main__':
    main()
