"""Independent emitted-waveform/control-state counterexamples and regressions."""
from pathlib import Path
from bisect import bisect_right
from functools import lru_cache
import json, sys
from tests35 import ep0_model as h

HERE=Path(__file__).resolve().parent
CURRENT=None

class Bits(h.Wave):
    def __init__(self,packet=b'\xd2',extra=(),rate=1_500_000,start=0,truncate=None):
        logical=[(byte>>bit)&1 for byte in b'\x80'+packet for bit in range(8)]
        if truncate is not None:logical=logical[:8+truncate]
        logical+=list(extra)
        bits=[];ones=0
        for bit in logical:
            bits.append(bit);ones=ones+1 if bit else 0
            if ones==6:bits.append(0);ones=0
        self.start=start;self.period=16_000_000/rate;self.packet=bytes(packet)
        self.bits=bits;self.boundaries=[];self.levels=[];self.labels=[];line=h.J
        for index,bit in enumerate(bits):
            if not bit:line=h.K if line==h.J else h.J
            self.boundaries.append(start+index*self.period);self.levels.append(line);self.labels.append(index)
        end=start+len(bits)*self.period
        self.boundaries.extend((end,end+2*self.period,end+3*self.period))
        self.levels.extend((0,h.J,h.J));self.labels.extend(('SE0','EOP_J','idle'))
        self.pin_edges=[];before=h.J
        for time,line in zip(self.boundaries,self.levels):
            if (before^line)&4:self.pin_edges.append(time)
            before=line
        self.end=end+3*self.period


def bind(art):
    global CURRENT
    key=art['boot'],art['sha256']
    if CURRENT!=key:
        h.dec.decode=lru_cache(maxsize=16384)(h.raw_decode);CURRENT=key


def ack(art,extra=(),truncate=None,entry=8,rate=1_500_000,marker=12):
    bind(art)
    wave=Bits(extra=extra,truncate=truncate,rate=rate)
    cpu=h.CPU(art,wave);cpu.t=entry
    cpu.r[2]=marker
    cpu.m[0x10F]=12;cpu.m[0x113]=0x24;cpu.m[0x10C]=6
    before=bytes(cpu.m[0x100:0x116]);at_ack=None;framing=None
    for _ in range(10000):
        if cpu.pc==0xFFFE:break
        if cpu.pc==cpu.labels['usb_rx_end_packet']:
            framing=dict(countdown=cpu.r[23],pair=cpu.r[22],even=cpu.r[16],time=cpu.t)
        if cpu.pc==cpu.labels['usb_rx_accept_ack']:at_ack=cpu.t
        cpu.step()
    else:raise AssertionError('ACK PHY failed to return')
    return dict(accepted=at_ack is not None,tx=cpu.m[0x10F],address=cpu.m[0x10C],
                pending=cpu.m[0x113],marker=cpu.r[2],frame=framing,time=cpu.t,peak=cpu.peak)


class Reset:
    pin_edges=[]
    def level(self,t):return 0
    def cell(self,t):return 'RESET'
    def edge_since(self,start,end):return False


def reset(art,command,rx_length=0):
    bind(art);cpu=h.CPU(art,Reset());cpu.raw_stack.clear()
    cpu.pc=cpu.labels['usb_poll_sample_bus'];cpu.t=0
    cpu.r[2],cpu.r[3],cpu.r[4],cpu.r[5]=12,command,0x80,0
    cpu.r[24],cpu.r[26],cpu.r[27]=100,100,0
    cpu.m[0x100],cpu.m[0x10F],cpu.m[0x10C],cpu.m[0x113]=0xFF,12,6,0x24
    cpu.m[0x114],cpu.m[0x10D],cpu.m[0x112],cpu.m[0x115]=0x2D,0x2D,rx_length,1
    sample=0;reset_state=None
    for _ in range(5000):
        if cpu.pc==cpu.labels['usb_poll_sample_bus']:sample+=1
        if cpu.pc==cpu.labels['bootloader_process_pending_command']:
            reset_state=dict(registers=cpu.r[:],context=bytes(cpu.m[0x100:0x116]).hex(),samples=sample)
        if cpu.pc==cpu.labels['flash_do_spm']:
            return dict(action='SPM',command=cpu.r[3],reset=reset_state)
        if cpu.pc==cpu.labels['bootloader_start_application']:
            return dict(action='RUN',command=cpu.r[3],reset=reset_state)
        if reset_state is not None and cpu.pc==cpu.labels['bootloader_check_idle_timeout']:
            return dict(action='idle',command=cpu.r[3],reset=reset_state)
        cpu.step()
    raise AssertionError('Reset probe did not converge')
