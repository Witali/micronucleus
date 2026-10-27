#!/usr/bin/env python3
"""Measure the modular candidate; fail a requested fit gate on any overflow."""
import argparse
from pathlib import Path
from check_build import build, run

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source/micronucleus_t88_compact.S'
MODES = ('NONE', 'ACTIVE_HIGH', 'ACTIVE_LOW')
# Measured savings against the deployed e405ea7 release, at the same placement.
# Keep host USB_PROFILES tied to the deployed firmware27 geometry/reference size.
CANDIDATE_SAVINGS = {'NONE': 54, 'ACTIVE_HIGH': 54, 'ACTIVE_LOW': 54}


def checked_build(mode='NONE', boot=0x1C00):
    artifact = build(SOURCE, mode, boot)
    undefined = run(['llvm-nm', '--undefined-only', str(artifact['obj'])])
    assert not undefined.strip(), 'Undefined AVR operands: ' + undefined
    return artifact


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot', type=lambda s: int(s, 0), default=0x1C00)
    parser.add_argument('--all-led', action='store_true')
    parser.add_argument('--require-fit', action='store_true')
    args = parser.parse_args()
    overflow = False
    for mode in MODES if args.all_led else ('NONE',):
        result = checked_build(mode, args.boot)
        capacity = 8192 - args.boot
        overflow |= result['size'] > capacity
        print(f"{mode}: {result['size']} bytes at {args.boot:#06x}; "
              f"capacity {capacity}; over budget {max(0, result['size'] - capacity)}; "
              f"SHA256 {result['sha256']}")
    if args.require_fit and overflow:
        raise SystemExit('FAIL: candidate does not fit the requested Flash region')
