"""Read-only real-board checks of the application-only protocol3.0 trial."""
from pathlib import Path
import hashlib
import json
import sys
import time

import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--private-dir',type=Path,required=True)
parser.add_argument('--python-libs',required=True)
parser.add_argument('--dll',required=True)
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
OUT=args.private_dir
sys.path[:0]=[args.python_libs,str(ROOT)]
import usb.core
import usb.util
import usb.backend.libusb0
from host.compact_programmer import parse_intel_hex

backend = usb.backend.libusb0.get_backend(find_library=lambda _: args.dll)
device = None
until = time.monotonic() + 30
while time.monotonic() < until:
    candidate = usb.core.find(idVendor=0x16D0, idProduct=0x0753, backend=backend)
    if candidate and candidate.bcdDevice == 0x0390:
        device = candidate
        break
    time.sleep(.15)
if device is None:
    raise SystemExit('Application trial 0x0390 not detected; installed loader was not replaced.')
print('Found live application-only protocol3.0 trial 0x0390', flush=True)

def control(kind, request, value=0, index=0, length=0):
    return bytes(device.ctrl_transfer(kind, request, value, index,
                                     length if kind & 0x80 else [], timeout=1500))

def read_memory(address, count, *, eeprom=False):
    assert address % 4 == 0 and count % 8 == 0
    control(0x40, 1, index=address | (0x8000 if eeprom else 0))
    chunks = []
    for _ in range(count // 8):
        value = control(0xC0, 0xB0, length=8)
        assert len(value) == 8
        chunks.append(value)
    return b''.join(chunks)

descriptor = control(0x80, 6, value=0x100, length=18)
assert len(descriptor) == 18 and descriptor[12:14] == b'\x90\x03'
assert control(0x80, 0, length=2) == b'\0\0'
assert control(0x80, 8, length=1) in (b'\0', b'\1')
configuration = control(0x80, 6, value=0x200, length=18)
assert len(configuration) == 18 and configuration[:2] == b'\x09\x02'
for _ in range(30):
    assert control(0x80, 6, value=0x100, length=18) == descriptor
    assert control(0x80, 6, value=0x200, length=18) == configuration
print('PASS repeated descriptors, GET_STATUS and GET_CONFIGURATION', flush=True)
started = time.monotonic()
first = read_memory(0, 8192)
second = read_memory(0, 8192)
assert first == second
ee = read_memory(0, 64, eeprom=True)
assert ee == read_memory(0, 64, eeprom=True)
assert ee == (OUT / 'before/eeprom.bin').read_bytes()
expected = parse_intel_hex((ROOT / 'build/rehearsal30/rehearsal.hex').read_text())
for address, value in expected.items():
    if address > 1:
        assert first[address] == value, ('uploaded application differs', address)
assert first[:2] == (0xC000 | (((json.loads((OUT/'before/manifest.json').read_text())['boot_at']//2)-1)&0xFFF)).to_bytes(2, 'little'), 'Installed bootloader RESET must remain'
assert first[0xFFC:0x1000] == b'\xff' * 4, 'Trial must keep waiting rather than jump to an application'
body = (ROOT / 'build/rehearsal30/body.bin').read_bytes()
assert first[0x1000:0x1000 + len(body)] == body
for address in (0, 0x80, 0x200, 0x1000, 0x1AF8, 0x1B00, 0x1FF8):
    assert read_memory(address, 8) == first[address:address + 8]
(OUT / 'after-flash.bin').write_bytes(first)
(OUT / 'after-eeprom.bin').write_bytes(ee)
report = dict(passed=True, installed_in_application=True, protocol='3.0',
              bcdDevice='0x0390', installed_loader='2.8 at 0x1B00',
              repeated_descriptors=60, full_flash_reads=2, eeprom_reads=2,
              eeprom_unchanged=True, application_body_matches=True,
              flash_sha256=hashlib.sha256(first).hexdigest(),
              installed_boot_sha256=hashlib.sha256(first[0x1B00:]).hexdigest(),
              elapsed_read_seconds=time.monotonic() - started,
              scope='Read-only trial; no Flash/EEPROM write commands or physical bit-timing measurement')
(OUT / 'hardware-report.json').write_text(json.dumps(report, indent=2))
usb.util.dispose_resources(device)
print('PASS two identical full Flash/EEPROM reads, exact trial body, unchanged EEPROM and boot RESET', flush=True)
print('Hardware report saved locally; no device-memory bytes printed.', flush=True)
