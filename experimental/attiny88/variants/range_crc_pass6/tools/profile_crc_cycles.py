#!/usr/bin/env python3
"""Instruction-cycle model of CPU time spent in CRC USB control handlers.

This does not model packet scheduling, host delays, VBUS transients or analog USB.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_crc_range import CRCDevice
from test_vusb_timing import Timed

class CycleDevice(CRCDevice,Timed):
    pass

def main():
    obj=CycleDevice(rom=bytes(i&255 for i in range(8192)))
    t=obj.t;obj.request(0xD0,0,512);print('CRC START cycles:',obj.t-t)
    for chunk in (1,2,4,8,16):
        t=obj.t
        ret=obj.request(0xD2,start=chunk,length=3)
        used=obj.t-t
        print(f'CRC STEP {chunk:2} bytes: {used:4} AVR cycles, {used/16:.2f} us at 16 MHz, response={ret.hex()}')
    print('NOTE: This is extra control-handler time, NOT a proof of USB timing compliance.')

if __name__=='__main__':main()
