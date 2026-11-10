"""Check adjacent-crossover token tails through actual component acquisition.

This checks the generic bit-receiver component, before protocol dispatch.
An overlong token is an invalid USB packet but still has a definite wire bit
stream: it cannot become a three-byte prefix plus a premature EOF-ready tag.
No bus response, transaction ownership or complete USB qualification is claimed.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import hashlib
import importlib.util
import json
import os
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    fo, root = args.firmware_root.resolve(), args.experiment.resolve()
    if args.output:
        assert not args.output.exists(), 'Use a fresh report path'
    pins = {Path(__file__).resolve(): sha(Path(__file__).resolve())}
    for manifest, directory in ((root / 'bundle-manifest.json', root),
                                (root / 'build-report.json', root / 'build')):
        pins[manifest] = sha(manifest)
        for relative, digest in json.loads(manifest.read_text())['files'].items():
            path = (directory / relative).resolve()
            assert path.is_relative_to(directory)
            pins[path] = digest
    model = root / 'model-inputs.json'
    for relative, digest in json.loads(model.read_text()).items():
        path = (fo.parent / relative).resolve()
        assert path.is_relative_to(fo.parent)
        pins[path] = digest
    for path, digest in pins.items():
        assert sha(path) == digest, ('Input changed', str(path))
    # Use the existing independent observer, not an experiment-specific oracle.
    observer_source = fo / 'prototypes/pll_extra6/observe.py'
    assert sha(root / 'observe.py') == sha(observer_source)
    pins[observer_source] = sha(observer_source)
    os.environ['MICRONUCLEUS_TEST_MODEL_ROOT'] = str(fo.parent / 'compact')
    sys.path.insert(0, str(fo))
    from tests35 import ep0_model as h
    from tests35.ep0_cases import bind
    from tests35.test_usb_crossover import single_crossover
    from tests35.test_rx_crossover_asymmetric import signal_witnesses, interval_errors
    for name in ('test_usb_crossover.py', 'test_rx_crossover_asymmetric.py'):
        path = fo / 'tests35' / name
        pins[path] = sha(path)
    spec = importlib.util.spec_from_file_location('token_tail_observer', observer_source)
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)
    art = json.loads((root / 'build/artifact.json').read_text())
    for key in ('obj', 'bin'):
        path = Path(art[key])
        art[key] = path if path.is_absolute() else root / path
    art['body'] = art['bin'].read_bytes()
    assert sha(art['bin']) == art['sha256']
    o = SimpleNamespace(h=h, bind=bind, core=SimpleNamespace(artifact=lambda path: art))
    observer.configure(o, root / 'build/artifact.json')
    signal_witnesses()
    token = h.token(0x69)
    prefix = len(h.Wave(token).bits)
    cases, controls, failures = 0, 0, []
    for tail in range(0, 256, 4):
        packet = token + bytes([tail])
        for rate in (1499250, 1500000, 1500750):
            for sign in (-1, 0, 1):
                for entry in (5, 8, 16, 24, 32, 38):
                    for injected in (False, True):
                        wave = h.Wave(packet, rate=rate, jitter=lambda i, line: sign * (.55 if line == h.J else -.55))
                        interval_errors(wave)
                        if injected:
                            single_crossover(wave, prefix + 1, width=3.36, fraction=20/21)
                            single_crossover(wave, prefix, width=3.36, fraction=1/21)
                            cases += 1
                        else:
                            controls += 1
                        result = observer.run(o, packet, wave, entry)
                        # The generic component must preserve every wire bit;
                        # protocol rejection of its four-byte length is later.
                        if result['errors'] or result['bits'] != 32:
                            failures.append(dict(tail=tail, rate=rate, sign=sign,
                                                 entry=entry, injected=injected, **result))
    assert cases == controls == 3456
    for path, digest in pins.items():
        assert sha(path) == digest, ('Input changed during corpus', str(path))
    report = dict(cases=cases, pristine_controls=controls, failures=failures,
                  bytes=art['size'], body_sha256=art['sha256'],
                  qualification_passed=not failures,
                  scope='Generic component bit/count/EOF preservation; no protocol or bus-response claim.')
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({**report, 'failures': len(failures)}, indent=2), flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
