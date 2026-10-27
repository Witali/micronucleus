#!/usr/bin/env python3
"""Measure installed 2.8 versus scratch-limited 3.0; keep dumps outside Git.

Snapshot mode only reads. Compare mode deliberately writes scratch Flash and
EEPROM, restores EEPROM, installs the guarded application via the old loader,
then restores its initially erased scratch. It requires explicit opt-in flags.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host.compact_programmer27 import DEFAULT_FLASH_DELAY_MS, parse_flash_delay_ms
SPEC = importlib.util.spec_from_file_location(
    'memory_benchmark', ROOT.parent / 'block64/prototypes/memory_benchmark/host/benchmark.py')
base = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = base
SPEC.loader.exec_module(base)
PAGE, COMMON = 64, 6908
RANGES = ((0x0040, 0x0080), (0x00C0, 0x0FC0), (0x14C0, 0x1AC0))
PAGES = tuple(at for start, end in RANGES for at in range(start, end, PAGE))
FLASH_TEST_BYTES = len(PAGES) * PAGE


def is_scratch(address):
    return any(start <= address < end for start, end in RANGES)


def scratch_bytes(flash):
    return b''.join(flash[start:end] for start, end in RANGES)


def outside_scratch(flash):
    return bytes(value for address, value in enumerate(flash) if not is_scratch(address))


def read_scratch(adapter):
    return b''.join(adapter.read(0, start, end - start) for start, end in RANGES)
LOADER_SHA = 'be2035139b301739837b5a214773e0a0421404450b078d40e2bf0c02aafa77c4'


class ScratchLegacy(base.Legacy):
    """Keep proven fresh-reset cursor priming; change only writable scratch bounds."""
    def require_scratch(self, address, size):
        if not self.connected or address % PAGE or size != PAGE or not is_scratch(address):
            raise base.BenchmarkError('Flash write is outside the benchmark scratch pages')


class Compact(base.Adapter):
    """Native sequential protocol 3.0, with bounded readback completion for EEPROM."""
    flash_chunk = eeprom_chunk = 8

    def __init__(self, dev, *, writable=False, flash_wait_ms=DEFAULT_FLASH_DELAY_MS):
        super().__init__(dev)
        self.writable = writable
        self.flash_wait_ms = parse_flash_delay_ms(flash_wait_ms)
        self.completing = False

    def connect(self):
        revision = int(self.dev.bcdDevice)
        allowed = (0x0391,) if self.writable else (0x0390, 0x0391)
        if revision not in allowed:
            raise base.BenchmarkError('Wrong compact application revision')
        self.connected = True
        self.identity = dict(protocol='compact-3.0', bcdDevice=hex(revision),
                             flash_chunk=8, eeprom_chunk=8,
                             flash_program_host_settle_ms=self.flash_wait_ms)
        return self.identity

    def control(self, kind, request, value=0, index=0, data=0):
        return self.ctrl(kind, request, value, index, data, completion=self.completing)

    def select(self, address, *, eeprom=False, erase=False):
        limit = 64 if eeprom else 8192
        if not self.connected or address % 4 or not 0 <= address < limit:
            raise base.BenchmarkError('Invalid byte selector')
        if erase:
            self.require_scratch(address, PAGE)
            if eeprom:
                raise base.BenchmarkError('Flash erase cannot address EEPROM')
        self.control(0x40, 2 if erase else 1, index=address | (0x8000 if eeprom else 0), data=b'')

    def read(self, kind, address, size, chunk=None):
        limit = 8192 if kind == 0 else 64
        if kind not in (0, 1) or address % 4 or size <= 0 or address + ((size + 7) // 8) * 8 > limit:
            raise base.BenchmarkError('Invalid read range')
        if chunk not in (None, 8):
            raise base.BenchmarkError('Compact uses complete eight-byte cursor steps')
        self.select(address, eeprom=bool(kind))
        result = b''.join(self.control(0xc0, 0xb0, data=8) for _ in range((size + 7) // 8))
        return result[:size]

    def require_scratch(self, address, size):
        if not self.connected or not self.writable or address % PAGE or size != PAGE or not is_scratch(address):
            raise base.BenchmarkError('Flash mutation is outside the benchmark scratch pages')

    def erase_page(self, address):
        self.require_scratch(address, PAGE)
        self.select(address, erase=True)
        self.meter.pause(self.flash_wait_ms / 1000, 'program_settle_seconds')

    def write_page(self, address, data):
        self.require_scratch(address, len(data))
        self.select(address)
        for offset in range(0, PAGE, 4):
            block = data[offset:offset + 4]
            self.control(0x40, 3, int.from_bytes(block[:2], 'little'),
                         int.from_bytes(block[2:], 'little'), b'')
        self.meter.pause(self.flash_wait_ms / 1000, 'program_settle_seconds')

    def write_eeprom(self, data):
        if not self.connected or not self.writable or len(data) != 64:
            raise base.BenchmarkError('EEPROM write needs the guarded writable application and 64 bytes')
        for address in range(0, 64, 4):
            block = data[address:address + 4]
            self.select(address, eeprom=True)
            self.control(0x40, 3, int.from_bytes(block[:2], 'little'),
                         int.from_bytes(block[2:], 'little'), b'')
            deadline = self.meter.clock() + 1
            self.completing = True
            try:
                # Busy SELECT/READ requests are ignored by the MCU. Reselect
                # every time and confirm the matching result independently.
                while True:
                    start, offset = address & ~7, address & 7
                    try:
                        reply = self.read(1, start, 8)
                        if reply[offset:offset + 4] == block:
                            confirm = self.read(1, start, 8)
                            if confirm[offset:offset + 4] == block:
                                break
                    except base.BenchmarkError as error:
                        if not str(error).startswith('Short response'):
                            raise
                    if self.meter.clock() >= deadline:
                        raise base.BenchmarkError('EEPROM completion/readback timeout')
                    self.meter.pause(.001, 'poll_sleep_seconds')
            finally:
                self.completing = False


def verify(actual, wanted, label):
    if actual != wanted:
        raise base.BenchmarkError(label + ' differs from verified bytes')


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def find_device(usb, backend, revision, seconds=45):
    """Never choose silently between two matching devices; enumeration may be stale."""
    revisions = (revision,) if isinstance(revision, int) else revision
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        devices = list(usb.core.find(find_all=True, idVendor=0x16d0, idProduct=0x0753, backend=backend))
        if len(devices) > 1:
            raise base.BenchmarkError('Connect only one matching board')
        if devices and int(devices[0].bcdDevice) in revisions:
            device = devices[0]
            try:
                descriptor = bytes(device.ctrl_transfer(0x80, 6, 0x100, 0, 18, timeout=500))
                if len(descriptor) == 18:
                    return device
            except usb.core.USBError:
                pass
        for device in devices:
            usb.util.dispose_resources(device)
        time.sleep(.1)
    raise base.BenchmarkError('Requested firmware did not appear; reconnect USB when requested')


def measure_phase(adapter, directory, expected_flash, expected_eeprom, *, legacy=False):
    """Time completed writes separately from erase and subsequent verification."""
    directory.mkdir(exist_ok=False)
    report = dict(passed=False, identity=adapter.connect(), measurements=adapter.meter.rows,
                  flash_scratch=RANGES, flash_write_trials=1 if legacy else 3,
                  read_trials=3, eeprom_write_trials=3, restoration={}, errors=[])
    save_json(directory / 'report.json', report)
    verify(adapter.read(0, 0, COMMON), expected_flash[:COMMON], 'Preflight application')
    verify(adapter.read(1, 0, 64), expected_eeprom, 'Preflight EEPROM')
    verify(scratch_bytes(expected_flash), b'\xff' * FLASH_TEST_BYTES, 'Initially erased scratch')
    measure = adapter.meter.measure
    try:
        for trial in range(3):
            print(f'{adapter.identity["protocol"]}: read trial {trial + 1}/3', flush=True)
            verify(measure('flash.read.common', COMMON, lambda: adapter.read(0, 0, COMMON), run=trial),
                   expected_flash[:COMMON], 'Flash read')
            verify(measure('eeprom.read', 64, lambda: adapter.read(1, 0, 64), run=trial),
                   expected_eeprom, 'EEPROM read')
        for trial in range(3):
            pattern = bytes((at * 73 + 0x35 + trial * 29) & 255 for at in range(64))
            measure('eeprom.write', 64, lambda: adapter.write_eeprom(pattern), run=trial)
            verify(adapter.read(1, 0, 64), pattern, 'EEPROM write')
        adapter.write_eeprom(expected_eeprom)
        verify(adapter.read(1, 0, 64), expected_eeprom, 'Restored EEPROM before Flash')
        pattern = bytes((at * 109 + 0x27) & 255 for at in range(FLASH_TEST_BYTES))
        if legacy:
            adapter.prepare_flash(fresh_reset_confirmed=True)
        for trial in range(1 if legacy else 3):
            print(f'{adapter.identity["protocol"]}: Flash write trial {trial + 1}', flush=True)
            if not legacy:
                measure('flash.erase.scratch', len(pattern),
                        lambda: [adapter.erase_page(at) for at in PAGES], run=trial)
                verify(read_scratch(adapter), b'\xff' * len(pattern), 'Erased scratch')
            measure('flash.write.scratch', len(pattern),
                    lambda: [adapter.write_page(at, pattern[index * PAGE:(index + 1) * PAGE])
                             for index, at in enumerate(PAGES)], run=trial)
            verify(measure('flash.read.controlled', len(pattern),
                           lambda: read_scratch(adapter), run=trial), pattern, 'Flash write')
        report['passed'] = True
    except Exception as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        # Do not retry uncertain legacy data writes. Its proven abort clears a
        # known partial buffer; an ambiguous transfer instead requires RESET.
        if legacy and not report['passed'] and adapter.flash_traffic_started:
            try:
                report['restoration']['legacy_buffer_cleared'] = adapter.abort_known_buffer()
            except Exception as error:
                report['passed'] = False
                report['errors'].append('Legacy buffer cleanup: ' + str(error))
        try:
            if adapter.read(1, 0, 64) != expected_eeprom:
                if legacy and adapter.transport_ambiguous:
                    raise base.BenchmarkError('RESET required before EEPROM restoration')
                adapter.write_eeprom(expected_eeprom)
            verify(adapter.read(1, 0, 64), expected_eeprom, 'Final EEPROM')
            report['restoration']['eeprom_verified'] = True
        except Exception as error:
            report['passed'] = False
            report['errors'].append('EEPROM restoration: ' + type(error).__name__ + ': ' + str(error))
        if not legacy:
            try:
                for at in PAGES:
                    adapter.erase_page(at)
                verify(read_scratch(adapter), b'\xff' * FLASH_TEST_BYTES, 'Restored scratch')
                report['restoration']['scratch_verified'] = True
            except Exception as error:
                report['passed'] = False
                report['errors'].append('Scratch restoration: ' + type(error).__name__ + ': ' + str(error))
        try:
            final_size = COMMON if legacy else 8192
            final = adapter.read(0, 0, final_size)
            verify(outside_scratch(final), outside_scratch(expected_flash[:final_size]),
                   'Flash outside scratch')
            report['restoration']['outside_scratch_verified'] = True
        except Exception as error:
            report['passed'] = False
            report['errors'].append('Final Flash verification: ' + type(error).__name__ + ': ' + str(error))
        save_json(directory / 'report.json', report)
    if not report['passed']:
        raise base.BenchmarkError('Benchmark failed; private report has failure/restoration details')
    return report


def summarize(report):
    rows = {}
    for name in sorted({row['operation'] for row in report['measurements']}):
        samples = [row for row in report['measurements'] if row['operation'] == name]
        rows[name] = dict(samples=len(samples), bytes=samples[0]['bytes'],
                          median_seconds=statistics.median(row['wall_seconds'] for row in samples),
                          median_bytes_per_second=statistics.median(row['bytes_per_second'] for row in samples),
                          median_host_wait_seconds=statistics.median(row['program_settle_seconds'] +
                                                                      row['poll_sleep_seconds'] for row in samples),
                          median_control_transactions=statistics.median(row['control_transactions'] +
                                                                        row['completion_transactions'] for row in samples))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('snapshot', 'compare'))
    parser.add_argument('--private-dir', type=Path, required=True)
    parser.add_argument('--expected-eeprom', type=Path, required=True)
    parser.add_argument('--python-libs', required=True)
    parser.add_argument('--dll', required=True)
    parser.add_argument('--micronucleus', type=Path)
    parser.add_argument('--flash-delay-ms', type=parse_flash_delay_ms, default=DEFAULT_FLASH_DELAY_MS,
                        help='Compact Flash erase/commit wait (default: 7 ms)')
    parser.add_argument('--execute-writes', action='store_true')
    parser.add_argument('--fresh-reset-confirmed', action='store_true')
    args = parser.parse_args()
    if args.phase == 'compare' and not (args.execute_writes and args.fresh_reset_confirmed and args.micronucleus):
        parser.error('Compare requires --execute-writes, --fresh-reset-confirmed and --micronucleus')
    directory = base.private_destination(args.private_dir)
    sys.path.insert(0, args.python_libs)
    import usb.core
    import usb.util
    import usb.backend.libusb0
    backend = usb.backend.libusb0.get_backend(find_library=lambda _: args.dll)
    expected_eeprom = args.expected_eeprom.read_bytes()
    if len(expected_eeprom) != 64:
        raise base.BenchmarkError('Expected EEPROM backup must contain exactly 64 bytes')
    if args.phase == 'snapshot':
        if (directory / 'flash-before.bin').exists():
            raise base.BenchmarkError('Use a fresh snapshot directory')
        device = find_device(usb, backend, (0x0390, 0x0391), seconds=3)
        adapter = Compact(device)
        adapter.connect()
        flash = adapter.read(0, 0, 8192)
        verify(adapter.read(0, 0, 8192), flash, 'Repeated Flash snapshot')
        verify(adapter.read(1, 0, 64), expected_eeprom, 'Original EEPROM')
        verify(scratch_bytes(flash), b'\xff' * FLASH_TEST_BYTES, 'Erased scratch')
        if hashlib.sha256(flash[0x1b00:0x1b00 + 1274]).hexdigest() != LOADER_SHA:
            raise base.BenchmarkError('Installed loader is not the independently verified 2.8 binary')
        (directory / 'flash-before.bin').write_bytes(flash)
        (directory / 'eeprom-before.bin').write_bytes(expected_eeprom)
        usb.util.dispose_resources(device)
        print('PASS twice-verified private Flash backup; original EEPROM and installed2.8 loader match', flush=True)
        return

    flash = (directory / 'flash-before.bin').read_bytes()
    verify((directory / 'eeprom-before.bin').read_bytes(), expected_eeprom, 'Saved EEPROM')
    artifact = ROOT / 'build/benchmark30'
    metadata = json.loads((artifact / 'manifest.json').read_text())
    image = (artifact / 'application.hex').read_bytes()
    if hashlib.sha256(image).hexdigest() != metadata['hex_sha256']:
        raise base.BenchmarkError('Benchmark HEX changed after its protection checks')
    if (tuple(map(tuple, metadata['flash_mutation_ranges'])), metadata['bcdDevice']) != (RANGES, '0x0391'):
        raise base.BenchmarkError('Wrong benchmark memory geometry')
    from host.compact_programmer27 import parse_intel_hex
    payload = parse_intel_hex(image.decode('ascii'))
    if max(payload) >= 0x1ac0 or any(is_scratch(at) or 0xfc0 <= at < 0x1000 for at in payload):
        raise base.BenchmarkError('Application HEX overlaps a protected page')
    print('WAITING for freshly reset installed2.8 loader', flush=True)
    device = find_device(usb, backend, 0x0208)
    try:
        legacy = measure_phase(ScratchLegacy(device), directory / 'legacy', flash, expected_eeprom, legacy=True)
    finally:
        usb.util.dispose_resources(device)
    # Start immediately while the old loader remains active. The stock uploader
    # owns its native RESET/postscript patching and full-application erase.
    print('Legacy benchmark passed; uploading guarded3.0 application through retained2.8 loader', flush=True)
    start = time.perf_counter()
    upload = subprocess.run([str(args.micronucleus), '--run', '--timeout', '30',
                             str(artifact / 'application.hex')], capture_output=True)
    (directory / 'application-upload.log').write_bytes(upload.stdout + upload.stderr)
    if upload.returncode:
        raise base.BenchmarkError('Stock application upload failed; private log retained')
    upload_seconds = time.perf_counter() - start
    device = find_device(usb, backend, 0x0391)
    try:
        adapter = Compact(device, writable=True, flash_wait_ms=args.flash_delay_ms)
        adapter.connect()
        installed = adapter.read(0, 0, 8192)
        verify(installed[0x1b00:], flash[0x1b00:], 'Protected installed loader')
        verify(installed[:2], flash[:2], 'Installed RESET')
        verify(installed[0xfc0:0x1000], b'\xff' * 64, 'Erased trial postscript page')
        for address, value in payload.items():
            if address > 1 and installed[address] != value:
                raise base.BenchmarkError('Uploaded benchmark application does not match the checked HEX')
        current = measure_phase(adapter, directory / 'compact', installed, expected_eeprom)
        verify(adapter.read(0, 0x1b00, 0x500), flash[0x1b00:], 'Final protected loader')
    finally:
        usb.util.dispose_resources(device)
    summary = dict(legacy=summarize(legacy), compact=summarize(current),
                   passed=True, production_bootloader_installed=False,
                   application_upload_seconds=upload_seconds,
                   scope='Host wall-clock throughput includes USB/driver scheduling and completion waits; physical USB bit timing is not measured.',
                   legacy_flash_trials=1, compact_flash_trials=3,
                   legacy_flash_erase='Not benchmarked: scratch initially erased; uploader erases the whole application during transition.',
                   eeprom_restored=True, compact_scratch_erased=True, installed_loader_unchanged=True)
    save_json(directory / 'comparison.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    # Running by path puts hardware/ on sys.path; support the adjacent host modules.
    sys.path.insert(0, str(ROOT))
    main()
