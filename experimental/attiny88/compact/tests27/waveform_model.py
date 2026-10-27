"""Independent digital USB encoder and ATtiny88 GPIO/PCINT model.

The MCU interpreter executes emitted AVR opcodes. This model excludes analog
thresholds, metastability and oscillator drift; it is not USB certification.
"""
from bisect import bisect_left, bisect_right
from pathlib import Path
import math
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'tests'))
from test_vusb_timing import Timed
from emulator_diff_test import dec

F_CPU=16_000_000
J,K,SE0=2,4,0

def crc16(data):
    crc=0xffff
    for byte in data:
        crc^=byte
        for _ in range(8):crc=(crc>>1)^(0xa001 if crc&1 else 0)
    return (crc^0xffff).to_bytes(2,'little')

def crc5(value):
    crc=0x1f
    for _ in range(11):
        bit=(crc^value)&1
        crc>>=1
        if bit:crc^=0x14
        value>>=1
    return crc^0x1f

def token(pid,address=0,endpoint=0):
    word=address|(endpoint<<7)
    return bytes([pid])+((word|(crc5(word)<<11))).to_bytes(2,'little')

def data_packet(payload,pid=0xc3):return bytes([pid])+bytes(payload)+crc16(payload)

class Wave:
    def __init__(self,packet,rate=1_500_000,start=0.0,jitter=None):
        self.packet=bytes(packet);self.period=F_CPU/rate;self.start=start
        logical=[(byte>>bit)&1 for byte in bytes([0x80])+self.packet for bit in range(8)]
        bits=[];ones=0
        for bit in logical:
            bits.append(bit)
            ones=ones+1 if bit else 0
            if ones==6:bits.append(0);ones=0
        self.bits=bits
        self.boundaries=[];self.levels=[];self.labels=[];self.pin_edges=[]
        level=J
        for index,bit in enumerate(bits):
            if bit==0:level=K if level==J else J
            t=start+index*self.period
            if jitter:t+=jitter(index,level)
            self.boundaries.append(t);self.levels.append(level);self.labels.append(index)
        end=start+len(bits)*self.period
        self.boundaries.extend([end,end+2*self.period,end+3*self.period])
        self.levels.extend([SE0,J,J]);self.labels.extend(['SE0','EOP_J','idle'])
        previous=J
        for t,level in zip(self.boundaries,self.levels):
            if (previous^level)&4:self.pin_edges.append(t)
            previous=level
        self.end=end+3*self.period

    def level(self,t):
        index=bisect_right(self.boundaries,t)-1
        return self.levels[index] if index>=0 else J

    def cell(self,t):
        index=bisect_right(self.boundaries,t)-1
        return self.labels[index] if index>=0 else 'pre'

    def edge_since(self,start,end):
        return bisect_right(self.pin_edges,end)>bisect_right(self.pin_edges,start)

class PinIO(dict):
    def __init__(self,cpu,wave,sample_offset=0.0):
        super().__init__({0x09:J,0x0a:0,0x0b:0,0x1b:0})
        self.cpu=cpu;self.wave=wave;self.sample_offset=sample_offset
        self.cleared_at=-1e30;self.samples=[]
    def get(self,addr,default=0):
        when=self.cpu.t+self.sample_offset
        if addr==0x09:
            level=self.wave.level(when)
            self.samples.append((when,getattr(self.cpu,'executing_pc',self.cpu.pc),level,self.wave.cell(when)))
            return level
        if addr==0x1b:return 4 if self.wave.edge_since(self.cleared_at,when) else 0
        return super().get(addr,default)
    def __setitem__(self,addr,value):
        if addr==0x1b and value&4:
            # SBI clears PCIF2 at its final write cycle. Only digital flag
            # behavior is represented; no input synchronizer is added.
            self.cleared_at=self.cpu.t+2
        else:super().__setitem__(addr,value)

class FlashView:
    """Avoid allocating the same flash tail at every decoder invocation."""
    def __init__(self,memory,base):self.memory=memory;self.base=base;self.body=bytes(memory[base:])
    def __getitem__(self,key):
        if isinstance(key,slice) and key.start==self.base and key.stop is None:return self.body
        return self.memory[key]
    def __len__(self):return len(self.memory)

APERTURE = float(os.environ.get('USB_PIN_APERTURE', '-1e-7'))
CLEAR_SET_WINS = os.environ.get('USB_PCIF_SET_WINS', '0') == '1'


class SynchronizedPinIO(PinIO):
    """Read clocked PIN; retain all PCIF pipeline events across W1C.

    At rising edge n, PIN loads the input latched at n - 0.5. The IN in
    Figure 10-4 begins at n and reads that updated PIN value. PCINT instead
    compares direct input with the *previous* pin_sync at n; pcint_syn,
    pcint_setflag and PCIF then form three clocked stages. One physical
    edge in the low half-cycle can produce two adjacent set events.
    """
    def __init__(self, cpu, wave, sample_offset=0.0):
        super().__init__(cpu, wave, sample_offset)
        self.phase = cpu.t - math.floor(cpu.t)
        edges = wave.pin_edges
        clocks = set()
        for edge in edges:
            first = math.floor(edge - self.phase) - 1
            clocks.update(range(first, first + 6))
        events = []
        for index in sorted(clocks):
            n = self.phase + index
            direct = wave.level(n + APERTURE)
            old_sync = wave.level(n - 1.5 + APERTURE)
            if (direct ^ old_sync) & 4:
                events.append(n + 2)
        self.flag_events = events

    def get(self, addr, default=0):
        if addr == 0x09:
            when = self.cpu.t - 0.5 + APERTURE
            level = self.wave.level(when)
            self.samples.append((when, getattr(self.cpu, 'executing_pc', self.cpu.pc), level, self.wave.cell(when)))
            return level
        if addr == 0x1b:
            left = (bisect_left if CLEAR_SET_WINS else bisect_right)(self.flag_events, self.cleared_at)
            return 4 if bisect_right(self.flag_events, self.cpu.t) > left else 0
        return dict.get(self, addr, default)
