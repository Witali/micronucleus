"""Vendor field trust must not let OUT release queued write/RUN work."""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_status import out

def test():
    art=h.build();cases=0
    for bm in (0x40,0xc0,0x41,0xc1):
        for command in (2,4,5):
            bind(art);cpu=h.CPU(art,Quiet())
            cpu.pc=cpu.labels['usb_setup_capture_fields']
            cpu.m[0x117:0x11f]=bytes([bm,command,0,0,0x80,0,8,0])
            cpu.r[6:8]=[8,0];cpu.r[12:16]=[0,0,0x80,0]
            cpu.r[11]=0xff;cpu.m[0x10f]=12
            for _ in range(3000):
                if cpu.pc==cpu.labels['usb_rx_release_buffer']:break
                cpu.step()
            else:raise AssertionError('vendor request did not finish')
            assert cpu.r[11]==0,(bm,command,cpu.r[11])
            expected=3 if command==2 else command
            assert cpu.r[3]==expected,(bm,command,cpu.r[3])
            row=out(art,direction=cpu.r[11],command=cpu.r[3],tx=4)
            assert row['command']==0 and row['tx']==0x1e,row
            cases+=1
    print('PASS host-only vendor fields retain write-status ACK gate:',cases,'cases')

if __name__=='__main__':test()
