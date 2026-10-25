#!/usr/bin/env python3
"""Relocate strict USB into ordinary application space for a reversible trial.

The diagnostic copy allows full Flash reads for a local backup. Its USB bit
engine is unchanged. No original bootloader page is touched by this builder.
"""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location('strict_builder', ROOT.parent / 'build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    spec2 = importlib.util.spec_from_file_location('updater_builder', ROOT / 'build.py')
    updater = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(updater)
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    source = (ROOT.parent / 'variants/strict_usb_1328/micronucleus_t88_plus_strict.S').read_text()
    front, tail = source.split('flash_read:\n', 1)
    start = tail.index('    /* All byte counts')
    stop = tail.index('flash_valid:\n')
    check = '''    /* Diagnostic-only full-Flash bound: start < 8192, end <= 8192. */
    cpi     r19, 0x20
    brlo    diagnostic_start_ok
    rjmp    ee_empty
diagnostic_start_ok:
    movw    r30, r18
    add     r30, r24
    adc     r31, r1
    cpi     r31, 0x20
    brlo    flash_valid
    brne    diagnostic_reject
    tst     r30
    breq    flash_valid
diagnostic_reject:
    rjmp    ee_empty
'''
    diagnostic = front + 'flash_read:\n' + tail[:start] + check + tail[stop:]
    asm = build / 'rehearsal.S'
    asm.write_text(diagnostic)
    body, symbols = module.compile_asm(asm, 0x1000, 'rehearsal_1000')
    assert 0x1000 + len(body) < 6650
    lines = [updater.record(0, (0xc03f).to_bytes(2,'little')),
             updater.record(0x80, (0xc000|((0x1000-0x80-2)//2)).to_bytes(2,'little'))]
    lines += [updater.record(0x1000+i,body[i:i+16]) for i in range(0,len(body),16)]
    lines.append(updater.record(0,b'',1))
    (build / 'rehearsal.hex').write_text('\n'.join(lines)+'\n')
    print('PASS: strict USB diagnostic body',len(body),'bytes at 0x1000; end',hex(0x1000+len(body)))
    print('Original bootloader at 0x1A00 is outside all application HEX records.')


if __name__ == '__main__':
    main()
