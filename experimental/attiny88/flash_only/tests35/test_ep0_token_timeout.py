"""Token authorization expires on silence; DATA after expiry is unpaired."""
from pathlib import Path
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits
def wave(packet,width,rate):
    value=Bits(packet,rate=rate)
    end=value.boundaries[-3]
    value.boundaries[-2:]=[end+width,end+width+value.period]
    value.end=value.boundaries[-1];value.pin_edges=[];before=h.J
    for time,line in zip(value.boundaries,value.levels):
        if (before^line)&4:value.pin_edges.append(time)
        before=line
    return value

HERE=Path(__file__).resolve().parent

class Joined(h.Wave):
    def __init__(self,a,b):
        self.boundaries=a.boundaries+b.boundaries
        self.levels=a.levels+b.levels;self.labels=a.labels+b.labels
        self.pin_edges=[];before=h.J
        for t,v in zip(self.boundaries,self.levels):
            if (before^v)&4:self.pin_edges.append(t)
            before=v
        self.end=b.end

def transaction(art,delay=None,rate=1_500_000,width=64/3,entry=8):
    token=wave(h.token(0x2d),width,rate);wire=token
    if delay is not None:
        data=Bits(h.data_packet(bytes([0x40,3,0x11,0x22,0x80,0,0,0])),start=token.boundaries[-2]+delay,rate=rate)
        wire=Joined(token,data)
    bind(art);c=h.CPU(art,wire);c.t=entry;c.m[0x10f]=0x5a
    expiry=None;decision=None
    for _ in range(10000):
        if c.pc==0xfffe:break
        if c.pc==c.labels['usb_rx_data_timeout_check']:decision=c.t-token.boundaries[-2]
        pc=c.pc;ins=c.step()
        if ins.op=='std' and ins.operands=='Z+20, r1' and c.executing_pc<c.labels['usb_rx_store_token']:
            expiry=c.t-token.boundaries[-2]
    else:raise AssertionError('token/DATA did not terminate')
    if delay is not None and c.t<data.start:
        # The next foreground packet decode cannot reuse the expired token.
        c.calls.append(0xfffe);c.pc=c.labels['USB_handler'];c.t=data.start+8
        for _ in range(10000):
            if c.pc==0xfffe:break
            c.step()
        else:raise AssertionError('late DATA did not terminate')
    return dict(expiry=expiry,decision=decision,token=c.m[0x114],setup_pending=c.r[3]==11,shadow=c.r[12:16]+c.r[6:8])

def test():
    art=h.build();rows=[];cases=0
    for rate in (1_499_250,1_500_000,1_500_750):
        period=16_000_000/rate
        for width in (10.72,64/3,24):
            for entry in (5,8,16,24,32,38):
                row=transaction(art,rate=rate,width=width,entry=entry)
                assert row['token']==0 and 16*period<=row['decision']<18*period,(rate,width,entry,row)
                rows.append(row['expiry'])
                for bits in (2,7.5,15.5,16,18,24):
                    row=transaction(art,delay=bits*period,rate=rate,width=width,entry=entry)
                    assert row['setup_pending']==(bits<=16),(bits,rate,width,entry,row)
                    if bits<=16:assert row['shadow']==[0x11,0x22,0x80,0,0,0],row
                    cases+=1
    report=dict(bytes=art['size'],sha256=art['sha256'],cases=cases,flag_store_range=[min(rows),max(rows)])
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':test()
