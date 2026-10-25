#!/usr/bin/env python3
"""Read a twice-verified local backup through the application-only rehearsal.

Requires PyUSB and the existing libusb0 driver. This client issues only vendor
IN requests 0x00 (info), 0xB0 (Flash read), and 0xA0 (EEPROM read).
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dll', required=True)
    parser.add_argument('--python-libs')
    parser.add_argument('--backup', required=True)
    args = parser.parse_args()
    if args.python_libs:
        sys.path.insert(0,args.python_libs)
    import usb.core
    import usb.backend.libusb0
    backend = usb.backend.libusb0.get_backend(find_library=lambda _:args.dll)
    if backend is None:
        raise RuntimeError('libusb0 backend could not load')
    deadline = time.monotonic() + 30
    device = None
    while time.monotonic() < deadline:
        try:
            candidate = usb.core.find(idVendor=0x16d0,idProduct=0x0753,backend=backend)
            info = bytes(candidate.ctrl_transfer(0xc0,0,0,0,8,timeout=1000)) if candidate else b''
            if len(info)==8 and info[:2]==b'\x0f\xfc' and info[4:6]==b'\x93\x11':
                device=candidate
                break
        except usb.core.USBError:
            pass
        time.sleep(0.2)
    if device is None:
        raise RuntimeError('Application rehearsal with capacity 4092 was not detected')
    def read(op,address,length):
        value=bytes(device.ctrl_transfer(0xc0,op,address,0,length,timeout=3000))
        if len(value)!=length:
            raise RuntimeError(f'Short reply at {address:#x}: {len(value)} != {length}')
        return value
    def flash():
        return b''.join(read(0xb0,a,8) for a in range(0,8192,8))
    def eeprom():
        return b''.join(read(0xa0,a,1) for a in range(64))
    first,ee = flash(),eeprom()
    assert first==flash(),'Flash reads differ'
    assert ee==eeprom(),'EEPROM reads differ'
    # The original 2.2 bootloader stays intact at the 0x1A00 page boundary.
    reset=int.from_bytes(first[:2],'little')
    assert reset==0xccff, f'Unexpected old RESET: {reset:#x}'
    backup=Path(args.backup)
    backup.mkdir(parents=True,exist_ok=False)
    (backup/'flash.bin').write_bytes(first)
    (backup/'eeprom.bin').write_bytes(ee)
    def record(address,data,kind=0):
        r=bytes([len(data),address>>8,address&255,kind])+data
        return ':'+(r+bytes([-sum(r)&255])).hex().upper()
    lines=[record(0,first[:2])]
    lines += [record(a,first[a:a+16]) for a in range(0x1a00,8192,16)]
    lines.append(record(0,b'',1))
    (backup/'stock-2.2-isp-recovery.hex').write_text('\n'.join(lines)+'\n')
    metadata={'bootloader_before':'2.2','old_boot_address':0x1a00,
              'diagnostic_usb_version':hex(device.bcdDevice),
              'flash_sha256':hashlib.sha256(first).hexdigest(),
              'eeprom_sha256':hashlib.sha256(ee).hexdigest(),
              'stock_boot_sha256':hashlib.sha256(first[0x1a00:]).hexdigest(),
              'two_reads_identical':True}
    (backup/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('PASS: rehearsal USB protocol; twice-verified 8192-byte Flash and 64-byte EEPROM reads')
    print('Local backup:',backup)
    print('Stock bootloader SHA-256:',metadata['stock_boot_sha256'])


if __name__=='__main__':
    main()
