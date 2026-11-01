from pathlib import Path
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits

def data_reply(art,payload=bytes([0x40,3,0x11,0x22,0x80,0,0,0]),pid=0xC3,
               entry=8,rate=1_500_000,token=0x2D,busy=0):
    bind(art);wave=Bits(h.data_packet(payload,pid=pid),rate=rate)
    cpu=h.CPU(art,wave);cpu.t=entry
    cpu.m[0x114]=token;cpu.r[3]=busy;cpu.m[0x10F]=0x5A
    edges=[];capture=None
    for _ in range(20000):
        if cpu.pc==0xFFFE:break
        if cpu.pc==cpu.labels['usb_rx_end_packet']:
            capture=dict(pair=cpu.r[22],even=cpu.r[16])
        ins=cpu.step()
        if ins.op=='out' and ins.operands.startswith('0xb,'):
            edges.append((cpu.t,cpu.io.get(11,0)&6))
    else:raise AssertionError('DATA handler did not return')
    start=next((time for time,value in edges if value==h.K),None)
    j=wave.boundaries[-2]
    return dict(response=None if start is None else start-j,setup_pending=cpu.r[3]==11,tx=cpu.m[0x10f],shadow=cpu.r[12:16]+cpu.r[6:8],current_token=cpu.m[0x114],
                fields=bytes(cpu.m[0x117:0x11F]).hex(),capture=capture,peak=cpu.peak)
