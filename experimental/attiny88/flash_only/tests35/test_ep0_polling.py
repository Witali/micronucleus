"""Inject legal IN tokens after a SETUP ACK through actual foreground paths."""
from pathlib import Path
import json,shutil
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits
CPU=h.CPU

HERE=Path(__file__).resolve().parent

def incoming(art,setup,delay,rate=1_500_000,config=1):
    bind(art);c=CPU(art,Bits(h.data_packet(setup),rate=rate))
    c.calls.pop();c.calls.append(c.labels['bootloader_process_pending_command'])
    c.m[0x114]=0x2d;c.m[0x10f]=0x5a;c.m[0x115]=config;c.r[4:6]=[0x80,0]
    j=None;entry=None
    for _ in range(18000):
        if c.pc==c.labels['USB_handler'] and j is not None:entry=c.t-j-delay
        if c.pc==c.labels['usb_rx_handle_in'] and j is not None:return True,entry
        pc=c.pc;ins=c.step()
        if j is None and ins.op=='out' and ins.operands.startswith('0xb,') and c.io.get(11,0)&6==h.J and pc==c.labels['usb_tx_eop_delay']+4:
            j=c.t
            wire=Bits(h.token(0x69),start=j+delay,rate=rate)
            old=dict(c.io);cleared=c.io.cleared_at
            c.io=h.SynchronizedPinIO(c,wire);c.io.update(old);c.io.cleared_at=cleared
        if j is not None and c.t>j+delay+800:return False,entry
    raise AssertionError('foreground injection did not finish')

def test():
    art=h.build();entries=[];cases=0
    requests=[(0x80,6,0x100,0,18,1),(0x80,6,0x200,0,18,1),
              (0x81,10,0,0,1,1),(0x81,10,0,0,1,0),
              (0x81,0,0,0,2,1),(0x81,0,0,0,2,0),(0x82,0,0,0x80,2,1),
              (0,5,37,0,0,1),(0,9,1,0,0,1),(0,9,0,0,0,1),
              (0xc0,0xb0,0,0x80,8,1),(0x20,2,0,0x80,0,1)]
    for bm,req,value,index,length,config in requests:
        setup=bytes([bm,req,value&255,value>>8,index&255,index>>8,length&255,length>>8])
        for rate in (1_499_250,1_500_000,1_500_750):
            delays=[2*(16_000_000/rate)+offset for offset in range(81)]
            delays.extend(range(104,225,4))
            for delay in delays:
                ok,entry=incoming(art,setup,delay,rate,config)
                assert ok and 5<=entry<=39,(setup.hex(),config,rate,delay,entry)
                entries.append(entry);cases+=1
    print('PASS foreground real-IN packet reception:',cases,'cases; PHY entry',min(entries),'..',max(entries),'cycles')

if __name__=='__main__':test()
