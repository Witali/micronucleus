#!/usr/bin/env python3
"""Opt-in physical Flash/EEPROM write/read/erase test with restoration.

Not part of unittest discovery. Requires an explicitly selected real board,
the saved EEPROM backup, and a verified application image to restore.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from firmware_layout import firmware_layout

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--exercise-hardware',action='store_true',required=True)
    for name in ['dll','python-libs','micronucleus','backup','report']:
        p.add_argument('--'+name,required=True)
    p.add_argument('--restore-hex','--led-hex',dest='restore_hex',required=True,help='Original application to restore after testing')
    p.add_argument('--firmware-manifest',type=Path,help='Expected layout; default is the deployed 6844-byte capacity')
    args=p.parse_args();sys.path.insert(0,args.python_libs)
    boot,app_bytes,reset=firmware_layout(args.firmware_manifest)
    import usb.core
    import usb.util
    import usb.backend.libusb0
    spec=importlib.util.spec_from_file_location('memory_host',ROOT.parent/'host/micronucleus_plus.py')
    host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
    backend=usb.backend.libusb0.get_backend(find_library=lambda _:args.dll)
    report={'boot_address':boot,'flash_bytes':app_bytes,'eeprom_bytes':64,'checks':{},'passed':False}
    destination=Path(args.report);destination.parent.mkdir(parents=True,exist_ok=True)
    print('Waiting for Micronucleus+ 2.8; press RESET once, keeping USB power connected.',flush=True)

    def connect(timeout=120):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            try:
                dev=usb.core.find(idVendor=0x16d0,idProduct=0x0753,backend=backend)
                if dev and dev.bcdDevice==0x0208:
                    tool=host.EEPROMTool(dev);tool.check_device()
                    if tool.flash_size==app_bytes:return tool
            except (usb.core.USBError,host.EEPROMError):pass
            time.sleep(0.1)
        raise RuntimeError('Expected new loader was not observed')

    def cli(tool,stage,image=None,erase=False):
        usb.util.dispose_resources(tool.dev)
        command=[args.micronucleus,'--timeout','5']
        command+=['--erase-only'] if erase else [str(image)]
        result=subprocess.run(command,capture_output=True,text=True)
        destination.with_name(destination.stem+'-'+stage+'.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode:raise RuntimeError(f'Micronucleus {stage} failed: {result.returncode}')
        return connect(5)

    def passed(name):
        report['checks'][name]=True;print('PASS:',name,flush=True)

    tool=connect()
    original=tool.read()
    assert original==(Path(args.backup)/'eeprom.bin').read_bytes(),'EEPROM differs from the pre-update backup'
    destination.with_suffix('.eeprom-backup.bin').write_bytes(original)
    try:
        try:
            pattern=bytes((i*73+0x35)&255 for i in range(64))
            tool.program(dict(enumerate(pattern)),skip_unchanged=False,verify=True)
            assert tool.read()==pattern
            passed('EEPROM: write/read all 64 bytes')
            tool.program(dict(enumerate(b'\xff'*64)),verify=True)
            assert tool.read()==b'\xff'*64
            passed('EEPROM: erase to 0xFF and read all 64 bytes')
        finally:
            tool.wait_ready()
            tool.program(dict(enumerate(original)),verify=True)
            assert tool.read()==original
            passed('EEPROM: original contents restored exactly')

        with tempfile.TemporaryDirectory(prefix='tiny88-memory-') as temporary:
            # Safe fallback entry: RESET -> 0x0080 -> an infinite RJMP loop.
            # Arbitrary test data is never executable even if the loader times out.
            pattern=bytearray((i*109+0x27)&255 for i in range(app_bytes))
            pattern[:2]=(0xc03f).to_bytes(2,'little')
            pattern[0x80:0x82]=(0xcfff).to_bytes(2,'little')
            image=Path(temporary)/'pattern.hex'
            image.write_text(host.write_hex_bytes(bytes(pattern)),encoding='ascii')
            try:
                tool=cli(tool,'flash-pattern',image=image)
                actual=tool.read_flash()
                assert actual[:2]==reset.to_bytes(2,'little')
                assert actual[2:]==pattern[2:]
                passed(f'Flash: write/read all {app_bytes} application bytes, accounting for patched RESET')
                tool=cli(tool,'flash-erase',erase=True)
                assert tool.read_flash()==b'\xff'*app_bytes
                passed(f'Flash: erase/read all {app_bytes} application bytes')
            finally:
                tool=cli(tool,'restore-app',image=Path(args.restore_hex))
                cells=host.load_image(Path(args.restore_hex),max_size=app_bytes)
                tool.verify_flash(cells,skip_reset_vector=True)
                assert tool.read_flash_block(0,2)==reset.to_bytes(2,'little')
                passed('Flash: original application restored and readback verified')
        assert tool.read()==original
        passed('EEPROM: still unchanged after Flash write/erase/restore')
        tool.dev.ctrl_transfer(0x40,4,0,0,b'',timeout=3000)
        passed('Original application start command accepted')
        report['passed']=True
    except Exception as exc:
        report['error']=str(exc)
        raise
    finally:
        destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PASS: hardware memory cycle complete; original EEPROM and application restored.',flush=True)


if __name__=='__main__':main()
