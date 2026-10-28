"""USB2 7.1.19.1: require ACK SOP timeout after16..18 LS bit times."""
from pathlib import Path
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits
from tests35.test_ep0_standard import Quiet

HERE=Path(__file__).resolve().parent

def transmitter(art,wire):
    bind(art);c=h.CPU(art,wire);c.t=0
    c.pc=c.labels['usb_tx_acquire_bus'];c.r[28:32]=[1,1,0,1]
    c.r[2]=12;c.r[3]=5;c.r[19]=12
    c.m[0x101:0x10c]=h.data_packet(bytes(range(8)))
    c.m[0x100]=0xff;c.m[0x10f]=12;c.m[0x10c]=6;c.m[0x113]=0x24
    return c

def transmit(art,delay=None,rate=1_500_000):
    c=transmitter(art,Quiet());j=None;cleared=None;accepted=False
    for _ in range(15000):
        if c.pc==0xfffe:break
        if c.pc==c.labels['usb_rx_accept_ack']:accepted=True
        before=c.r[2];ins=c.step()
        if before and c.r[2]==0:cleared=c.t
        if ins.op=='out' and ins.operands.startswith('0xb,') and c.io.get(11,0)&6==h.J and c.executing_pc==c.labels['usb_tx_eop_delay']+4:
            j=c.t
            if delay is not None:
                wave=Bits(start=j+delay,rate=rate)
                old=dict(c.io);c.io=h.SynchronizedPinIO(c,wave);c.io.update(old);c.io.cleared_at=c.t-1
    else:raise AssertionError('TX did not return')
    assert j is not None
    return dict(j=j,expiry=None if cleared is None else cleared-j,accepted=accepted,tx=c.m[0x10f],address=c.m[0x10c],marker=c.r[2],command=c.r[3],end=c.t),c

def test():
    art=h.build()
    quiet,_=transmit(art)
    assert quiet['marker']==0 and quiet['tx']==12 and quiet['address']==6,quiet
    assert 16*(16_000_000/1_499_250)<=quiet['expiry']<18*(16_000_000/1_500_750),quiet
    cases=0
    for rate in (1_499_250,1_500_000,1_500_750):
        period=16_000_000/rate
        for bits in (2,4,7.5,15.5,16):
            row,_=transmit(art,delay=bits*period,rate=rate)
            assert row['accepted'] and row['tx']==0x5a and row['address']==0x24 and row['command']==5,(bits,rate,row)
            cases+=1
        for bits in (18,24,100):
            row,c=transmit(art,delay=bits*period,rate=rate)
            assert not row['accepted'] and row['tx']==12 and row['address']==6 and row['marker']==0,(bits,rate,row)
            # Receiving the late ACK in the foreground cannot revive eligibility.
            c.calls.append(0xfffe);c.pc=c.labels['USB_handler'];c.t=row['j']+bits*period+8
            for _ in range(8000):
                if c.pc==0xfffe:break
                assert c.pc!=c.labels['usb_rx_accept_ack']
                c.step()
            else:raise AssertionError('late ACK did not return')
            assert c.m[0x10f]==12 and c.m[0x10c]==6
            cases+=1
    report=dict(bytes=art['size'],sha256=art['sha256'],fixed_quiet=quiet,cases=cases)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':test()
