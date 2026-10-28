#!/usr/bin/env python3
"""Reproduce historical USB observations without hardware or firmware changes."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

sys.dont_write_bytecode = True
from model import ROOT, h, compact_artifact, upstream_artifact
import compact_cases


def main():
    """Select pinned historical images and write observations to ignored output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-tail-matrix', action='store_true',
                        help='Also run all 6120 valid-CRC DATA ending/partial-tail observations')
    parser.add_argument('--upstream-artifact', type=Path,
                        help='Also audit a separately prepared pinned official v2.6 metadata JSON')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/historical_usb/results.json')
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((ROOT / 'build/historical_usb').resolve()):
        raise ValueError('Audit output must stay under ignored build/historical_usb')
    compact = compact_artifact()
    print('Auditing exact compact 3.0:', compact['size'], 'bytes;', compact['sha256'], flush=True)
    model_sources = [Path(h.__file__), ROOT / 'tests35/avr_cycles.py',
                     h.BACKEND / 'tests27/waveform_model.py', Path(h.dec.__file__),
                     Path(h.dec.__file__).with_name('emulator_diff_test.py'),
                     Path(h.dec.__file__).with_name('test_vusb_timing.py')]
    model_hashes = {path.relative_to(ROOT.parent).as_posix() if path.is_relative_to(ROOT.parent) else path.name:
                    hashlib.sha256(path.read_bytes()).hexdigest() for path in model_sources}
    report = dict(purpose='Historical observations, not modern USB compliance expectations',
                  hardware_accessed=False, model='Shared tests35 AVR opcodes and synchronized GPIO at 16 MHz',
                  model_source_sha256=model_hashes,
                  limitations=['Digital simulation excludes analog thresholds, oscillator drift and board qualification',
                               'Incoming numeric DATA CRC16 omission was an explicit historical exception; no other USB exception is inferred'],
                  compact30=dict(boot=hex(compact['boot']), bytes=compact['size'], sha256=compact['sha256'],
                                 provenance=compact['provenance'],
                                 control=compact_cases.token_control(compact),
                                 raw=compact_cases.raw_cases(compact, args.full_tail_matrix)))
    if args.upstream_artifact:
        import upstream_cases
        upstream = upstream_artifact(args.upstream_artifact)
        print('Auditing pinned official v2.6:', upstream['size'], 'bytes;', upstream['sha256'], flush=True)
        report['upstream26'] = dict(boot=hex(upstream['boot']), bytes=upstream['size'], sha256=upstream['sha256'],
                                    provenance=upstream['provenance'], observations=upstream_cases.audit(upstream))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Historical observations written to', args.output, flush=True)
    print('Protocol defects in this report do not count as passing modern USB tests.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
