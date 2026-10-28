"""Qualify observed later handler entries with legal 75/45 ns wire corners.

The fixed39..41-clock regression grid covers the measured40.6773-clock
foreground entry. It is not a USB entry-latency requirement or universal
jitter proof: exact bytes/state and complete response waves remain required.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import eop_wave
from tests35.rx_jitter_patterns import corners,interval_errors
from tests35.test_rx_jitter_spec import corpus
from tests35.test_tx_digital import encoded


def check(art,entries=(39,40,40.75,41)):
    bind(art);cases=0;responses=[];edge_errors={}
    rates=(1499250,1500000,1500750)
    for kind,packet,address,payload in corpus():
        for rate in rates:
            for width in (10.72,2*16000000/rate,24):
                for wire in corners(eop_wave(packet,width,rate)):
                    for distance,extrema in interval_errors(wire).items():
                        saved=edge_errors.setdefault(distance,[1e9,-1e9])
                        saved[0]=min(saved[0],extrema[0]);saved[1]=max(saved[1],extrema[1])
                    for entry in entries:
                        cpu=h.CPU(art,wire,entry)
                        cpu.m[0x10c]=address
                        cpu.r[8]=packet[2] if kind=='IN' else 0x10
                        cpu.m[0x10f]=0x5a if kind!='OUT' else 4
                        cpu.r[4:6]=[0x80,0];cpu.r[14:16]=[0x88,0]
                        cpu.r[11]=0x80 if kind=='OUT' else 0
                        cpu.m[0x114]=0x2d if kind=='SETUP' else (0xe1 if kind=='OUT' else 0)
                        sent=[];outputs=[];accepted=None
                        for _ in range(10000):
                            if cpu.pc==0xfffe:break
                            if cpu.pc==cpu.labels['usb_tx_acquire_bus']:
                                sent.append((cpu.r[19],cpu.r[20]))
                                accepted=cpu.r[23],bytes(cpu.m[0x116:0x116+len(packet)])
                            instruction=cpu.step()
                            if instruction.op=='out' and instruction.operands.startswith('0xb,') and cpu.io.get(10,0)&6==6:
                                outputs.append((cpu.t,cpu.io.get(11,0)&6))
                        else:raise AssertionError('Jittered receiver did not return')
                        context=(kind,address,rate,width,entry,wire.jitter_certificate)
                        assert sent==[(2,0x5a if kind=='IN' else 0xd2)],('valid jittered packet rejected',context,sent)
                        assert accepted==(len(packet),packet),('received bytes/count',context,accepted)
                        levels,_=encoded(bytes([0x80,0x5a if kind=='IN' else 0xd2]))
                        assert [line for _,line in outputs]==levels+[0,h.J],('emitted handshake mismatch',context,outputs)
                        if kind=='SETUP':
                            assert cpu.r[3]==11 and cpu.r[12:16]+cpu.r[6:8]==list(payload[2:]),('SETUP shadow',context)
                        if kind=='OUT':
                            assert cpu.m[0x10f]==0x5a and cpu.m[0x100]&0x80 and cpu.word(4)==0x80,('OUT completion',context)
                        first_k=outputs[0][0]
                        response=first_k-wire.boundaries[-2]
                        # The response here is always an unstuffed handshake.
                        # Use the smaller of the host period and certified
                        # 85/8-clock response cadence as a conservative bound
                        # across reference interpretations of Section 7.1.18.1.
                        response_bit=85/8
                        assert 2*response_bit<=response<=6.5*min(response_bit,wire.period),('jittered response timing',context,response)
                        responses.append(response);cases+=1
    return dict(cases=cases,entries=entries,response_range=[min(responses),max(responses)],differential_edge_error_ns=edge_errors)


def test():
    report=check(h.build())
    print('PASS later-entry exact receive/full response at 75/45 ns corners:',report)
    return report


if __name__=='__main__':test()
