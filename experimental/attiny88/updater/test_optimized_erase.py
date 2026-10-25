#!/usr/bin/env python3
"""Run the actual optimized erase loop with an independent simavr CPU/SPM."""
from pathlib import Path
import argparse
import json
import subprocess

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simavr_source',type=Path)
    parser.add_argument('manifests',nargs='+',type=Path)
    args=parser.parse_args()
    sim=args.simavr_source.resolve()/'simavr'
    library=next(sim.glob('obj-*/libsimavr.so')).parent
    executable=ROOT/'build/test_optimized_erase'
    subprocess.run(['gcc','-Wall','-Wextra','-Werror','-I'+str(sim/'sim'),
                    str(ROOT/'test_optimized_erase.c'),'-L'+str(library),'-Wl,-rpath,'+str(library),
                    '-lsimavr','-lelf','-o',str(executable)],check=True)
    for file in args.manifests:
        file=file.resolve();meta=json.loads(file.read_text());symbols=meta['symbols']
        subprocess.run([str(executable),str(file.parent/meta['body_file']),str(meta['image_address']),
                        str(symbols['bootloader_process_pending_command']),
                        str(symbols['usb_control_process_received_packet'])],check=True)


if __name__=='__main__':main()
