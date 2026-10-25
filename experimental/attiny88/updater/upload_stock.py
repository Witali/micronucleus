#!/usr/bin/env python3
"""Wait for the original 2.2 loader before sending an application image.

This avoids accidentally invoking Flash writes through a running diagnostic
loader whose protected boundary is intentionally different.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dll',required=True)
    p.add_argument('--python-libs',required=True)
    p.add_argument('--micronucleus',required=True)
    p.add_argument('--hex',required=True)
    p.add_argument('--log',required=True)
    args=p.parse_args()
    sys.path.insert(0,args.python_libs)
    import usb.core
    import usb.util
    import usb.backend.libusb0
    backend=usb.backend.libusb0.get_backend(find_library=lambda _:args.dll)
    if backend is None:raise RuntimeError('Cannot load libusb0')
    print('Waiting up to 90 seconds for stock Micronucleus 2.2, capacity 6650; reconnect USB now.',flush=True)
    until=time.monotonic()+90
    while time.monotonic()<until:
        device=None
        try:
            device=usb.core.find(idVendor=0x16d0,idProduct=0x0753,backend=backend)
            if device:
                info=bytes(device.ctrl_transfer(0xc0,0,0,0,8,timeout=800))
                if len(info)>=6 and info[:2]==bytes([0x19,0xfa]) and info[4:6]==bytes([0x93,0x11]) and device.bcdDevice==0x0202:
                    usb.util.dispose_resources(device)
                    result=subprocess.run([args.micronucleus,'--run','--timeout','5',args.hex],capture_output=True,text=True)
                    Path(args.log).write_text(result.stdout+result.stderr+f'\nExit code: {result.returncode}\n',encoding='utf-8')
                    print(result.stdout,flush=True)
                    if result.stderr:print(result.stderr,file=sys.stderr)
                    if result.returncode:raise RuntimeError('Stock application upload failed')
                    return
        except usb.core.USBError:
            pass
        finally:
            if device:usb.util.dispose_resources(device)
        time.sleep(0.1)
    raise RuntimeError('Stock loader was not observed; nothing was written')


if __name__=='__main__':main()
