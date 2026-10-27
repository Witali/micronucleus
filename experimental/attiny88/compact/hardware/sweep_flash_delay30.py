#!/usr/bin/env python3
"""Opt-in Flash quiet-time sweep on the already installed guarded application.

No firmware upload, RESET-page write, EEPROM write or bootloader replacement.
Stop at the first short-delay error; restore all test pages with 15 ms waits.
Sub-10 ms trials are diagnostic and never become a production recommendation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hardware.benchmark30 import (Compact, PAGES, FLASH_TEST_BYTES, ROOT, base,
                                  find_device, outside_scratch, read_scratch,
                                  save_json, scratch_bytes, verify)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-writes', action='store_true', required=True)
    parser.add_argument('--private-dir', type=Path, required=True)
    parser.add_argument('--loader-backup', type=Path, required=True,
                        help='Previously verified full8192-byte Flash backup')
    parser.add_argument('--expected-eeprom', type=Path, required=True)
    parser.add_argument('--python-libs', required=True)
    parser.add_argument('--dll', required=True)
    args = parser.parse_args()
    directory = base.private_destination(args.private_dir)
    if (directory / 'report.json').exists():
        raise base.BenchmarkError('Use a fresh sweep directory')
    sys.path.insert(0, args.python_libs)
    import usb.core
    import usb.util
    import usb.backend.libusb0
    backend = usb.backend.libusb0.get_backend(find_library=lambda _: args.dll)
    device = find_device(usb, backend, 0x0391, seconds=3)
    adapter = Compact(device, writable=True)
    adapter.timeout_ms = 800
    adapter.connect()
    flash = adapter.read(0, 0, 8192)
    verify(adapter.read(0, 0, 8192), flash, 'Repeated sweep preflight')
    eeprom = args.expected_eeprom.read_bytes()
    verify(adapter.read(1, 0, 64), eeprom, 'Original EEPROM')
    verify(flash[0x1b00:], args.loader_backup.read_bytes()[0x1b00:], 'Original loader')
    verify(scratch_bytes(flash), b'\xff' * FLASH_TEST_BYTES, 'Initially erased free Flash')
    metadata = json.loads((ROOT / 'build/benchmark30/manifest.json').read_text())
    size = metadata['body_bytes']
    if hashlib.sha256(flash[0x1000:0x1000 + size]).hexdigest() != metadata['body_sha256']:
        raise base.BenchmarkError('Installed guarded code differs from its checked build')
    (directory / 'flash-before.bin').write_bytes(flash)
    report = dict(passed=False, diagnostic_levels_ms=[12, 10, 8, 7, 6, 5],
                  bytes_per_trial=FLASH_TEST_BYTES, pages_per_trial=len(PAGES),
                  rows=[], restoration={}, errors=[],
                  scope='Same-board diagnostic; less than10ms does not meet the conservative5ms deferred-start plus4.5ms SPM budget.')
    save_json(directory / 'report.json', report)

    def trial(delay, number):
        """Use different data every trial; time completed operations before readback."""
        adapter.flash_wait_ms = delay
        adapter.meter.rows.clear()
        adapter.meter.measure('flash.erase', FLASH_TEST_BYTES,
                              lambda: [adapter.erase_page(at) for at in PAGES])
        verify(read_scratch(adapter), b'\xff' * FLASH_TEST_BYTES, 'Erased Flash')
        pattern = random.Random(0x30A000 + number).randbytes(FLASH_TEST_BYTES)
        adapter.meter.measure('flash.program', FLASH_TEST_BYTES,
                              lambda: [adapter.write_page(at, pattern[index * 64:(index + 1) * 64])
                                       for index, at in enumerate(PAGES)])
        verify(read_scratch(adapter), pattern, 'Programmed Flash')
        row = dict(delay_ms=delay, trial=number, passed=True,
                   payload_sha256=hashlib.sha256(pattern).hexdigest(),
                   measurements=list(adapter.meter.rows))
        report['rows'].append(row)
        save_json(directory / 'report.json', report)
        program = row['measurements'][1]
        print(f'PASS {delay}ms: {FLASH_TEST_BYTES} bytes / {len(PAGES)} pages, '
              f'program {program["wall_seconds"]:.3f}s, {program["bytes_per_second"]:.1f}B/s', flush=True)

    try:
        for number, delay in enumerate(report['diagnostic_levels_ms']):
            try:
                trial(delay, number)
            except Exception as error:
                report['rows'].append(dict(delay_ms=delay, trial=number, passed=False,
                                           error=type(error).__name__ + ': ' + str(error)))
                print(f'STOP {delay}ms: failed; returning to15ms recovery waits', flush=True)
                time.sleep(.05)
                break
        conservative = [row['delay_ms'] for row in report['rows'] if row['passed'] and row['delay_ms'] >= 10]
        if conservative:
            selected = min(conservative)
            for repeat in range(2):
                trial(selected, 100 + repeat)
            report['confirmed_wait_ms'] = selected
        report['passed'] = bool(conservative)
    except Exception as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        adapter.flash_wait_ms = 15
        time.sleep(.05)
        try:
            for at in PAGES:
                adapter.erase_page(at)
            verify(read_scratch(adapter), b'\xff' * FLASH_TEST_BYTES, 'Restored test pages')
            report['restoration']['scratch_erased'] = True
        except Exception as error:
            report['errors'].append('Scratch cleanup: ' + str(error))
        try:
            final = adapter.read(0, 0, 8192)
            verify(outside_scratch(final), outside_scratch(flash), 'All8192 bytes outside scratch')
            report['restoration']['all_protected_flash_verified'] = True
        except Exception as error:
            report['errors'].append('Protected Flash: ' + str(error))
        try:
            verify(adapter.read(1, 0, 64), eeprom, 'Unchanged EEPROM')
            report['restoration']['eeprom_unchanged'] = True
        except Exception as error:
            report['errors'].append('EEPROM check: ' + str(error))
        if report['errors']:
            report['passed'] = False
        save_json(directory / 'report.json', report)
        usb.util.dispose_resources(device)
    print(json.dumps(dict(passed=report['passed'], confirmed_wait_ms=report.get('confirmed_wait_ms'),
                          observed_passing_waits_ms=sorted({row['delay_ms'] for row in report['rows'] if row['passed']}),
                          restoration=report['restoration'], errors=report['errors']), indent=2), flush=True)
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
