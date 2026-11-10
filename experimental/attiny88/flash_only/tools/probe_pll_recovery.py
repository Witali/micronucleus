"""Preserve actual centered PID acquisition plus the compact shared DATA graph.

Build only into a fresh Flash-only/build directory. Original sealed packages,
independent CPU/wire models and previous reports are never rewritten. This
correctness reference is not a complete packet owner or selectable firmware.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--centered-dir', type=Path, default=Path('build/pll-pid-guard-centered'))
    parser.add_argument('--output-dir', type=Path, default=Path('build/pll-shared-recovery'))
    parser.add_argument('--package-root', type=Path, help='Optional alternate location of the pinned shared-generator package')
    args = parser.parse_args()
    fo = args.firmware_root.resolve()
    base = (fo / args.centered_dir).resolve()
    allowed = (fo / 'build').resolve()
    out = (fo / args.output_dir).resolve()
    package = args.package_root.resolve() if args.package_root else fo / 'prototypes/pll_shared_recovery'
    assert allowed.is_relative_to(fo) and base.is_relative_to(allowed) and base != allowed
    assert out.is_relative_to(allowed) and out != allowed and not out.exists(), 'Use a fresh output directory below Flash-only/build'
    package_manifest = package / 'package-manifest.json'
    package_files = json.loads(package_manifest.read_text())['files']
    original = {package_manifest: sha(package_manifest)}
    for relative, digest in package_files.items():
        path = (package / relative).resolve()
        assert path.is_relative_to(package) and sha(path) == digest, ('Generator package changed', relative)
        original[path] = digest
    layout = json.loads((package / 'layout.json').read_text())
    manifest = base / 'bundle-manifest.json'
    original[manifest] = sha(manifest)
    files = json.loads(manifest.read_text())['files']
    for relative, digest in files.items():
        path = (base / relative).resolve()
        assert path.is_relative_to(base) and sha(path) == digest, ('Centered source changed', relative)
        original[path] = digest
    assert sha(base / 'compose.py') == layout['centered_compose_sha256'], 'Unexpected centered guard composer'
    model_pins = json.loads((base / 'model-inputs.json').read_text())
    for relative, digest in model_pins.items():
        path = (fo.parent / relative).resolve()
        assert path.is_relative_to(fo.parent) and sha(path) == digest, ('Independent model changed', relative)
        original[path] = digest
    base_report = json.loads((base / 'build-report.json').read_text())
    for relative, digest in base_report['files'].items():
        path = (base / 'build' / relative).resolve()
        assert path.is_relative_to(base / 'build') and sha(path) == digest, ('Build the centered experiment first', relative)
        original[path] = digest
    baseline = json.loads((base / 'build/artifact.json').read_text())
    assert (baseline['size'], baseline['boot'], baseline['sha256']) == (5634, 2048, layout['centered_body_sha256'])
    tool = Path(__file__).resolve()
    original[tool] = sha(tool)
    out.mkdir(parents=True)
    for name in ('compose.py', 'build.py', 'observe.py', 'verify.py', 'model-inputs.json', 'LICENSE_GPL-2.0.txt'):
        shutil.copyfile(base / name, out / name)
    inputs = json.loads((base / 'inputs.json').read_text())
    for relative in inputs['files']:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / relative, target)
    generation = out / 'layout'
    generation.mkdir()
    shutil.copyfile(package / 'core_generator.py', generation / 'core_generator.py')
    write_json(generation / 'seed-layout.json', dict(block_layout=layout['block_layout']))
    generator = (package / 'core_generator.py').read_text()
    assert sha(package / 'core_generator.py') == layout['original_generator_sha256']
    anchor = '    return cost\npreferred=tuple(root_blocks)'
    insertion = '''    for at, target in PREFIX_REFERENCES:
        tg, off = labels[target]
        span = (PREFIX_DELTA - at - 2) // 2 + starts[tg] + off
        cost += max(0, span - 2047)**2 + max(0, -2048 - span)**2
    return cost
preferred=tuple(json.loads((HERE/'seed-layout.json').read_text())['block_layout'])'''
    assert generator.count(anchor) == 1
    generator = generator.replace(anchor, insertion)
    generator = generator.replace('HERE=Path(__file__).resolve().parent', 'HERE=Path(__file__).resolve().parent\nPREFIX_DELTA=' + repr(layout['graph_delta']) + '\nPREFIX_REFERENCES=' + repr([tuple(pair) for pair in layout['prefix_references']]), 1)
    (generation / 'generator.py').write_text(generator, newline='\n')

    def command(*argv):
        try:
            return subprocess.check_output(argv, cwd=out, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            print(exc.output)
            raise

    command(sys.executable, str(generation / 'generator.py'))
    assert sha(generation / 'extra6-mandatory-zero.S') == layout['expected_source_sha256']
    assert sha(generation / 'extra6-mandatory-zero-manifest.json') == layout['expected_manifest_sha256']
    shutil.copyfile(generation / 'extra6-mandatory-zero.S', out / 'inputs/extra6.S')
    shutil.copyfile(generation / 'extra6-mandatory-zero-manifest.json', out / 'inputs/extra6-manifest.json')
    composer = (out / 'compose.py').read_text()
    anchor = "graph=source.read_text();graph=graph[graph.index('rx_p1_J_r2_inline_0_second_zero:'):]"
    assert composer.count(anchor) == 1
    composer = composer.replace(anchor, "graph=source.read_text();graph=graph.split('    rjmp rx_p0_K_r1\\n',1)[1]")
    composer = composer.replace('dict(boot=0x800,', 'dict(boot=0x200,')
    (out / 'compose.py').write_text(composer, newline='\n')
    inputs['boot'] = layout['boot']
    inputs['expected_bytes'] = layout['composed_bytes']
    inputs['expected_body_sha256'] = layout['composed_body_sha256']
    for relative in inputs['files']:
        inputs['files'][relative] = sha(out / relative)
    # The copied PLL provenance describes its old frozen DATA component.
    # Preserve that ancestry without presenting its hash as this graph's body.
    inherited_decoder = inputs['provenance'].pop('decoder_body_sha256')
    inputs['provenance']['parent_frozen_decoder_body_sha256'] = inherited_decoder
    inputs['provenance']['shared_recovery'] = dict(
        centered_body_sha256=baseline['sha256'], original_core_body_sha256=layout['original_core_body'],
        original_generator_sha256=layout['original_generator_sha256'], package_manifest_sha256=sha(package_manifest),
        generated_decoder_source_sha256=layout['expected_source_sha256'], generated_decoder_manifest_sha256=layout['expected_manifest_sha256'],
        builder_sha256=sha(tool), change='Genuinely shared cold handlers; fixed intact-cluster placement for actual PID roots.')
    write_json(out / 'inputs.json', inputs)
    # Keep the independent observer and waveform/case generation unchanged.
    # Replace only the historical expected-rejection policy with a strict gate.
    verifier = (out / 'verify.py').read_text()
    start = verifier.index('for row in bad:\n')
    end = verifier.index('summary=dict(', start)
    verifier = verifier[:start] + verifier[end:]
    start = verifier.index("expected=json.loads((HERE/'expected-results.json').read_text())[args.suite]")
    end = verifier.index('integrity()\nprint(json.dumps(summary,indent=2)', start)
    verifier = verifier[:start] + "expected_cases={'controls':24,'full':9984,'payloads':2627,'fractional':6048,'fractional_min':6048}\nassert len(rows)==expected_cases[args.suite],('Positive corpus changed',summary)\nassert not bad,('Valid packet reception failed',summary)\n" + verifier[end:]
    (out / 'verify.py').write_text(verifier, newline='\n')
    command(sys.executable, 'build.py')
    artifact = json.loads((out / 'build/artifact.json').read_text())
    assert (artifact['boot'], artifact['size'], artifact['sha256']) == (layout['boot'], layout['composed_bytes'], layout['composed_body_sha256'])
    assert artifact['boot'] + artifact['size'] <= 8192
    command('avr-gcc', '-mmcu=attiny88', '-DLED_MODE=NONE', f'-DBOOT_AT={artifact["boot"]}', '-I', 'inputs/vendor', '-x', 'assembler-with-cpp', '-c', 'build/candidate.S', '-o', 'build/gnu.o')
    command('avr-ld', '-m', 'avr25', '--defsym=__TEXT_REGION_LENGTH__=0x2000', '-Ttext=0', '-e', 'bootloader_start', '-o', 'build/gnu.elf', 'build/gnu.o')
    command('avr-objcopy', '-O', 'binary', '-j', '.text', 'build/gnu.elf', 'build/gnu.whole.bin')
    whole = (out / 'build/gnu.whole.bin').read_bytes()
    body = (out / 'build/candidate.body.bin').read_bytes()
    assert whole[:artifact['boot']] == bytes(artifact['boot']) and whole[artifact['boot']:] == body, 'GNU/LLVM bytes differ'
    gnu_symbols = {}
    for row in command('avr-nm', '-n', 'build/gnu.elf').splitlines():
        fields = row.split()
        if len(fields) == 3:
            gnu_symbols[fields[2]] = int(fields[0], 16)
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
    assert pc == artifact['boot'] + artifact['size'] <= 8192
    for name, at in labels.items():
        assert artifact['symbols'][name] == gnu_symbols[name] == at, ('Source/LLVM/GNU symbol mismatch', name)
    for at, op, target in edges:
        offset = at - artifact['boot']
        word = int.from_bytes(body[offset:offset + 2], 'little')
        if op in ('rjmp', 'rcall'):
            assert word & 0xf000 == (0xc000 if op == 'rjmp' else 0xd000)
            value, width = word & 4095, 12
        else:
            assert word & 0xfc00 in (0xf000, 0xf400)
            value, width = (word >> 3) & 127, 7
        displacement = value - (1 << width) if value & (1 << (width - 1)) else value
        assert at + 2 + displacement * 2 == labels[target], ('Wrapped/truncated encoded edge', at, op, target)
    write_json(out / 'edge-audit.json', dict(bytes=len(body), boot=artifact['boot'], end_exclusive=pc,
        labels=len(labels), instructions=instructions, named_relative_edges=len(edges), wrapped_edges=0,
        gnu_llvm_body_identical=True, body_sha256=artifact['sha256']))
    shutil.copyfile(out / 'build/build-report.json', out / 'build-report.json')
    write_json(out / 'layout-provenance.json', layout)
    shutil.copyfile(tool, out / 'derive.py')
    relative_fo = os.path.relpath(fo, out).replace('\\', '/')
    (out / 'README.md').write_text(f'''# Actual PLL plus shared DATA receiver

Offline correctness reference: {artifact['size']} bytes at 0x{artifact['boot']:04x},
SHA-256 `{artifact['sha256']}`. GNU/LLVM bytes, physical fit, all relative
source edges and pinned source/model provenance are checked. Sources derive
from the centered8058 prefix and frozen6192 shared graph; no maintained source,
observer, model or previous evidence is modified. There is no full framing,
packet publication/count owner, recovery-J, ACK or complete USB claim.
This exact reference remains incomplete: 92/13464 combined SYNC/first-DATA-edge
cases miss acquisition handoff. The separate expanded probe must retain those
failures; the strict original positive suites do not replace it.

Run `python3 verify.py --firmware-root {relative_fo} --suite controls`, then
`full`, `payloads`, `fractional` and `fractional_min`. All 24731 positive
observations must pass. Every positive rejection fails; no snapshot expected
rejection is accepted. Negative prefix/combined-edge probes remain separate.
''', newline='\n')
    names = [str(p.relative_to(out)).replace('\\', '/') for directory in ('inputs', 'layout') for p in (out / directory).rglob('*') if p.is_file()]
    names += ['compose.py', 'build.py', 'observe.py', 'verify.py', 'model-inputs.json', 'LICENSE_GPL-2.0.txt', 'inputs.json', 'build-report.json', 'edge-audit.json', 'layout-provenance.json', 'derive.py', 'README.md']
    write_json(out / 'bundle-manifest.json', dict(files={name: sha(out / name) for name in sorted(names)}))
    for path, digest in original.items():
        assert sha(path) == digest, ('Original source/model/evidence changed', str(path))
    print(json.dumps(dict(output=str(out), boot=artifact['boot'], bytes=artifact['size'], sha256=artifact['sha256'], gnu_identical=True, positive_policy='zero errors and exact corpus counts', original_inputs_unchanged=True), indent=2))


if __name__ == '__main__':
    main()
