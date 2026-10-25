#!/usr/bin/env python3
"""Check the installed loader, unchanged EEPROM, and optional application readback."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from firmware_layout import firmware_layout


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dll',required=True)
    p.add_argument('--python-libs',required=True)
    p.add_argument('--backup',required=True)
    p.add_argument('--app')
    p.add_argument('--start',action='store_true')
    p.add_argument('--check-configuration',action='store_true')
    p.add_argument('--firmware-manifest',type=Path,help='Expected layout; default is the deployed 6844-byte capacity')
    p.add_argument('--benchmark-reads',type=int,default=0,metavar='COUNT',help='Time repeated application Flash reads without writing memory')
    p.add_argument('--readback-dir',type=Path,help='Save verified repeated Flash reads and EEPROM in a new local directory')
    p.add_argument('--timeout',type=float,default=30,help='Seconds to wait for the selected loader')
    args=p.parse_args();sys.path.insert(0,args.python_libs)
    if args.benchmark_reads<0:p.error('--benchmark-reads must be nonnegative')
    if args.timeout<=0:p.error('--timeout must be positive')
    if args.readback_dir and args.benchmark_reads<2:p.error('--readback-dir requires at least two benchmark reads')
    if args.readback_dir and args.readback_dir.exists():p.error('--readback-dir must name a new directory')
    boot,app_bytes,reset=firmware_layout(args.firmware_manifest)
    import usb.core
    import usb.backend.libusb0
    backend=usb.backend.libusb0.get_backend(find_library=lambda _:args.dll)
    print(f'Waiting up to {args.timeout:g} seconds for capacity {app_bytes}; press RESET and keep USB power connected.',flush=True)
    until=time.monotonic()+args.timeout;device=None
    while time.monotonic()<until:
        try:
            d=usb.core.find(idVendor=0x16d0,idProduct=0x0753,backend=backend)
            info=bytes(d.ctrl_transfer(0xc0,0,0,0,8,timeout=1000)) if d else b''
            if len(info)==8 and int.from_bytes(info[:2],'big')==app_bytes and info[2]==64 and info[4:6]==b'\x93\x11' and info[6]==0xe0 and d.bcdDevice==0x0208:
                device=d;break
        except usb.core.USBError:pass
        time.sleep(0.1)
    if device is None:raise RuntimeError(f'New 2.8 loader with capacity {app_bytes} was not detected')
    def read(request,address,length):
        result=bytes(device.ctrl_transfer(0xc0,request,address,0,length,timeout=3000))
        assert len(result)==length,(hex(request),address,len(result),length)
        return result
    eeprom=b''.join(read(0xa0,a,1) for a in range(64))
    assert eeprom==(Path(args.backup)/'eeprom.bin').read_bytes(),'EEPROM changed during update'
    assert bytes(device.ctrl_transfer(0xc0,0xb0,app_bytes,0,1,timeout=3000))==b'','Protected Flash range was exposed'
    print(f'PASS: installed Micronucleus+ 2.8, ATtiny88, 64-byte pages, {app_bytes} application bytes, boot {boot:#06x}')
    print('PASS: all 64 EEPROM bytes unchanged; Flash boundary protected')
    previous=None;samples=[]
    for run in range(args.benchmark_reads):
        started=time.perf_counter()
        image=b''.join(read(0xb0,address,min(8,app_bytes-address)) for address in range(0,app_bytes,8))
        elapsed=time.perf_counter()-started
        samples.append(elapsed)
        if previous is not None:assert image==previous,'Repeated Flash reads differ'
        previous=image
        print(f'READ BENCHMARK {run+1}: {app_bytes} bytes, {(app_bytes+7)//8} requests, '
              f'{elapsed:.6f} seconds, {app_bytes/elapsed:.1f} bytes/second',flush=True)
    if args.readback_dir:
        args.readback_dir.mkdir(parents=True)
        (args.readback_dir/'flash-app.bin').write_bytes(previous)
        (args.readback_dir/'eeprom.bin').write_bytes(eeprom)
        record={'boot_address':boot,'application_bytes':app_bytes,'usb_bcd_device':device.bcdDevice,
                'flash_sha256':hashlib.sha256(previous).hexdigest(),
                'eeprom_sha256':hashlib.sha256(eeprom).hexdigest(),'read_seconds':samples,
                'repeated_reads_identical':True}
        (args.readback_dir/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
        print('PASS: repeated Flash readback and EEPROM saved locally to',args.readback_dir,flush=True)
    if args.check_configuration:
        configuration=bytes(device.ctrl_transfer(0x80,8,0,0,1,timeout=3000))
        assert configuration==b'\x01',('GET_CONFIGURATION',configuration)
        print('PASS: standard GET_CONFIGURATION returns configuration 1 from SRAM')
    if args.app:
        cells={}
        for line in Path(args.app).read_text().splitlines():
            r=bytes.fromhex(line[1:]);assert sum(r)%256==0
            if r[3]==0:
                address=int.from_bytes(r[1:3],'big')
                cells.update({address+i:b for i,b in enumerate(r[4:-1])})
            else:assert r[3] in (1,3,5)
        end=max(cells)+1
        actual=b''.join(read(0xb0,a,min(8,end-a)) for a in range(0,end,8))
        assert actual[:2]==reset.to_bytes(2,'little'),'RESET does not retain the new bootloader'
        for address,value in cells.items():
            if address>=2:assert actual[address]==value,('Application mismatch',address)
        print('PASS: application Flash readback matches Intel HEX (excluding patched RESET),',len(cells),'bytes')
        if args.start:
            device.ctrl_transfer(0x40,4,0,0,b'',timeout=3000)
            print('Application start command sent')
    elif args.start:raise RuntimeError('--start requires verified --app')


if __name__=='__main__':main()
