#!/usr/bin/env python3
"""Compare actual USB waveform timestamps and polling against the deployed body.

This is an instruction-cycle model, not an electrical USB simulator. Symbols
come from each build manifest, avoiding repeated external disassembler calls.
"""
from pathlib import Path
import argparse
import json
import random
import sys

ROOT = Path(__file__).resolve().parent
arguments = sys.argv[1:]  # The historical decoder import resets sys.argv.
sys.path.insert(0,str(ROOT.parent/'tests'))
from source_labels import with_semantic_names
from test_vusb_timing import Timed


def state(build, memory, registers, entry):
    cpu=Timed(build,{'memory':memory,'registers':registers})
    cpu.pc=cpu.labels[entry]
    cpu.io.update({0x09:2,0x0a:0,0x0b:0,0x1b:4})
    return cpu


def reach(cpu, entry, limit=3000):
    for _ in range(limit):
        if cpu.pc==cpu.labels[entry]:return cpu
        cpu.step()
    raise AssertionError(('checkpoint not reached',entry,hex(cpu.pc)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifests',nargs='+',type=Path)
    args=parser.parse_args(arguments)
    for file in args.manifests:
        meta=json.loads(file.read_text())
        old={'name':'deployed','start':0x1ac0,'bin':ROOT.parent/'variants/strict_usb_verified/BOOTLOADER_BODY_1AC0_VERIFIED.bin',
             'o':None,'symbols':with_semantic_names(meta['baseline_symbols']),'step_limit':100000}
        new={'name':'optimized','start':meta['image_address'],'bin':file.parent/meta['body_file'],
             'o':None,'symbols':meta['symbols'],'step_limit':100000}
        rng=random.Random(0x1688)
        for _ in range(600):
            memory=bytearray(rng.getrandbits(8) for _ in range(0x300))
            registers=[rng.getrandbits(8) for _ in range(32)];registers[1]=0
            registers[18]=rng.choice([0,255,0x80,0x7e,0x55,0xc3,rng.getrandbits(8)])
            registers[19]=rng.choice([1,2,3,4,7,12]);registers[20]=rng.choice([0xd2,0x5a])
            y=rng.choice([0x14,0x101,0x110]);registers[28]=y&255;registers[29]=y>>8
            registers[30]=0;registers[31]=1
            a,b=[reach(state(build,memory,registers,'usb_tx_acquire_bus'),'usb_handler_packet_done') for build in (old,new)]
            assert (a.t,a.bus_events,a.m)==(b.t,b.bus_events,b.m),'TX timing or data changed'
        for _ in range(500):
            memory=bytearray(rng.getrandbits(8) for _ in range(0x300))
            registers=[rng.getrandbits(8) for _ in range(32)];registers[1]=0
            a,b=[reach(state(build,memory,registers,'usb_rx_sync_confirmed'),'usb_rx_sample_odd_bit') for build in (old,new)]
            assert (a.t,a.flags,a.r,a.m)==(b.t,b.flags,b.r,b.m),'RX sync timing/context changed'
        for pid in [0xc3,0x4b,0x69,0x2d,0xe1]:
            for mode in [0,1,0x5a]:
                memory=bytearray(0x300);registers=[0]*32
                registers[19]=11;registers[28]=0;registers[29]=1;registers[31]=1
                memory[0x100]=pid;memory[0x112]=1;memory[0x114]=mode;memory[0x10f]=0x5a
                results=[]
                for build in (old,new):
                    cpu=state(build,memory,registers,'usb_rx_end_packet')
                    for _ in range(500):
                        if cpu.pc in [cpu.labels['usb_tx_acquire_bus'],cpu.labels['usb_handler_packet_done']]:break
                        cpu.step()
                    else:raise AssertionError('Handshake checkpoint not reached')
                    results.append((cpu.pc==cpu.labels['usb_tx_acquire_bus'],cpu.t,cpu.m))
                assert results[0]==results[1],'ACK/NAK selection or response latency changed'
        # Check the entire five-millisecond no-traffic interval, including
        # reset detection, and pending-edge latency at every loop phase.
        for level in [0,2]:
            results=[]
            for build in (old,new):
                cpu=state(build,bytearray(0x300),[0]*32,'bootloader_poll_begin')
                cpu.io[0x1b]=0;cpu.io[0x09]=level
                reach(cpu,'bootloader_process_pending_command',100000)
                results.append((cpu.t,cpu.m))
            assert results[0]==results[1],'Poll/reset interval changed'
        for phase in range(15):
            arrivals=[]
            for build in (old,new):
                cpu=state(build,bytearray(0x300),[0]*32,'bootloader_poll_begin');cpu.io[0x1b]=0
                for _ in range(100):
                    if cpu.t>=phase:cpu.io[0x1b]=4
                    if cpu.pc==cpu.labels['USB_handler']:break
                    cpu.step()
                else:raise AssertionError('Pending USB edge was not serviced')
                arrivals.append(cpu.t)
            assert arrivals[0]==arrivals[1],'USB poll-to-handler latency changed'
        print(f'PASS: {file.parent.name}: 600 exact TX traces, 500 RX sync contexts, 15 handshake cases, '
              'idle/reset intervals and all 15 poll arrival phases match the deployed image')


if __name__=='__main__':main()
