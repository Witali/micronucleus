"""Failed SYNC must cancel ACK eligibility and token authorization."""
from pathlib import Path
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits

HERE=Path(__file__).resolve().parent

class Glitch(h.Wave):
    def __init__(self):
        self.boundaries=[0,4];self.levels=[h.K,h.J];self.labels=['GLITCH','IDLE']
        self.pin_edges=[0,4];self.end=4

def late_ack_after_glitch(art):
    bind(art);c=h.CPU(art,Glitch())
    c.r[2]=12;c.m[0x10f]=12;c.m[0x10c]=6;c.m[0x113]=0x24;c.m[0x114]=0x2d
    for _ in range(3000):
        if c.pc==0xfffe:break
        c.step()
    else:raise AssertionError('failed SYNC did not return')
    marker=c.r[2];token=c.m[0x114]
    wire=Bits(start=c.t+200)
    old=dict(c.io);c.io=h.SynchronizedPinIO(c,wire);c.io.update(old);c.io.cleared_at=c.t-1
    c.calls.append(0xfffe);c.pc=c.labels['USB_handler'];c.t=wire.start+8
    for _ in range(8000):
        if c.pc==0xfffe:break
        c.step()
    else:raise AssertionError('late ACK did not return')
    return dict(marker_after_glitch=marker,token_after_glitch=token,tx=c.m[0x10f],address=c.m[0x10c])

def test():
    art=h.build();row=late_ack_after_glitch(art)
    assert row==dict(marker_after_glitch=0,token_after_glitch=0,tx=12,address=6),row
    print('PASS failed-SYNC cancellation and late-ACK rejection:',row)

if __name__=='__main__':test()
