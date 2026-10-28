"""Exercise Table 7-10 receiver interval corners using legal NRZI waves.

Each generated wave proves its next/paired interval errors remain within
75/45 ns. Actual receive effects and response timing are checked separately;
fixture legality alone never proves that the AVR received it correctly.
"""
import os
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import eop_wave
from tests35.rx_jitter_patterns import corners,interval_errors
from tests35.test_data_framing import ending_packets


def corpus():
    for address in (0,31,63,127):
        yield 'IN',h.token(0x69,address=address),address,None
    for packet,payload in (ending_packets(True,8)[0],ending_packets(True,8)[5]):
        yield 'SETUP',packet,0,payload
    for payload in (b'',bytes([255])*8):
        yield 'OUT',h.data_packet(payload,0x4b),0,payload


def test():
    art=h.build();bind(art);cases=0;responses=[]
    exhaustive=os.environ.get('USB_PHY_EXHAUSTIVE')=='1'
    rates=(1499250,1500000,1500750) if exhaustive else (1500000,)
    entries=(5,8,16.5,24,32,38) if exhaustive else (5,16.5,38)
    for kind,packet,address,payload in corpus():
        for rate in rates:
            for width in (10.72,2*16000000/rate,24):
                for wire in corners(eop_wave(packet,width,rate)):
                    interval_errors(wire)
                    for entry in entries:
                        cpu=h.CPU(art,wire,entry)
                        cpu.m[0x10c]=address
                        cpu.r[8]=packet[2] if kind=='IN' else 0x10
                        cpu.m[0x10f]=0x5a if kind!='OUT' else 4
                        cpu.r[4:6]=[0x80,0];cpu.r[14:16]=[0x88,0]
                        cpu.r[11]=0x80 if kind=='OUT' else 0
                        cpu.m[0x114]=0x2d if kind=='SETUP' else (0xe1 if kind=='OUT' else 0)
                        sent=[]
                        for _ in range(10000):
                            if cpu.pc==0xfffe:break
                            if cpu.pc==cpu.labels['usb_tx_acquire_bus']:sent.append((cpu.r[19],cpu.r[20]))
                            cpu.step()
                        else:raise AssertionError('Jittered receiver did not return')
                        context=(kind,address,rate,width,entry,wire.jitter_certificate)
                        assert sent==[(2,0x5a if kind=='IN' else 0xd2)],('valid jittered packet rejected',context,sent)
                        if kind=='SETUP':
                            assert cpu.r[3]==11 and cpu.r[12:16]+cpu.r[6:8]==list(payload[2:]),('SETUP shadow',context)
                        if kind=='OUT':
                            assert cpu.m[0x10f]==0x5a and cpu.m[0x100]&0x80 and cpu.word(4)==0x80,('OUT completion',context)
                        first_k=next(t for t,io,value in cpu.bus_events if io==11 and value&6==h.K)
                        response=first_k-wire.boundaries[-2]
                        # The response here is always an unstuffed handshake.
                        # Use the smaller of the host period and certified
                        # 85/8-clock response cadence as a conservative bound
                        # across reference interpretations of Section 7.1.18.1.
                        response_bit=85/8
                        assert 2*response_bit<=response<=6.5*min(response_bit,wire.period),('jittered response timing',context,response)
                        responses.append(response);cases+=1
    print('PASS receiver 75/45 ns next/paired corners:',cases,'wire cases; response clocks',min(responses),max(responses))


if __name__=='__main__':test()
