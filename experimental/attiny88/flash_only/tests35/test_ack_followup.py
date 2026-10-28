"""Legal ACK tails must leave time for the next minimum-gap WRITE4 SETUP.

Exercise linked AVR instructions and actual hardware-buffer staging, with
independent NRZI waveforms. A completed old write alone is insufficient: the
next SETUP must also be received intact and acknowledged.
"""
import os
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_sequential_wire import PageCPU,write_request


def test():
    art=h.build();bind(art);cases=0
    phases=[quarter/4 for quarter in range(33)] if os.environ.get('USB_PHY_EXHAUSTIVE')=='1' else (0,0.25,1,2,8)
    for rate in (1499250,1500000,1500750):
        period=16000000/rate
        for width in (10.72,2*period,24):
            for tail in range(5):
                for phase in phases:
                    cpu=PageCPU(art)
                    write_request(cpu,1,index=0x80,rate=rate,ack_phase=phase)
                    try:
                        write_request(cpu,3,0x1122,0x3344,followup=True,rate=rate,ack_phase=phase,
                                      ack_extra_ones=tail,ack_eop_cycles=width)
                    except AssertionError as error:
                        raise AssertionError(('ACK-to-SETUP',rate,width,tail,phase,str(error))) from error
                    assert cpu.buffer=={0:0x1122,2:0x3344},'old words/data/order changed'
                    assert cpu.r[4]|cpu.r[5]<<8==0x84
                    cases+=1
    print('PASS physical2bit ACK-to-next-SETUP, legal dribble, EOP widths, rates and phases:',cases,'wire exchanges')


if __name__=='__main__':test()
