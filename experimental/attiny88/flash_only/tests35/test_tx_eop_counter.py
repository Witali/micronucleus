"""Measure transmitted EOP on emitted AVR GPIO events, including bit stuffing.

USB2 Table 7-10 permits source SE0 of 1.25..1.50us:20..24 clocks at 16 MHz.
This model excludes analog voltage thresholds and actual oscillator drift.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_reply_fragments import crc16


def measure(art,pid,payload=None,prior_ddr=0):
    bind(art);cpu=h.CPU(art,Quiet());cpu.t=0
    cpu.r[2]=0  # Transmitter-only proof; no host ACK is scheduled.
    cpu.io.update({10:prior_ddr&~6,11:0xa9&~6})
    if payload is None:
        cpu.r[20]=pid
        cpu.pc=cpu.labels['usb_tx_prepare_handshake']
    else:
        packet=bytes([pid])+payload+crc16(payload)
        cpu.m[0x101:0x101+len(packet)]=packet
        cpu.r[28:30]=[1,1];cpu.r[19]=len(payload)+4
        cpu.pc=cpu.labels['usb_tx_acquire_bus']
    saw_counter=False
    for _ in range(20000):
        if cpu.pc==0xfffe:break
        if cpu.pc==cpu.labels['usb_tx_finish_eop']:
            # R21 is still the USB line mask; data/unstuff paths did not
            # modify it. It can also supply the six-count EOP delay.
            assert cpu.r[21]==6,(pid,payload,prior_ddr,cpu.r[21])
            saw_counter=True
        cpu.step()
    else:raise AssertionError('TX did not return')
    assert saw_counter and cpu.r[21]==0xa0
    driving=False;se0=None;j=None;released=None
    for when,register,value in cpu.bus_events:
        if register==10:
            was_driving=driving;driving=(value&6)==6
            if was_driving and not driving:
                released=when
                assert value==prior_ddr&~6
        elif register==11 and driving:
            if value&6==0 and se0 is None:se0=when
            elif se0 is not None and value&6==2 and j is None:j=when
    assert None not in (se0,j,released),(pid,payload,cpu.bus_events)
    return j-se0,released-j


def check(art,expected_clocks):
    packets={(pid,bytes([value])*length)
             for pid in (0xc3,0x4b) for length in range(9)
             for value in (0,255,0x55,0xaa)}
    packets.update((0x4b,bytes((seed+37*i)&255 for i in range(8)))
                   for seed in range(256))
    cases=0
    for ddr in (0,0x19,0xf9):
        for pid,payload in sorted(packets):
            width,drive_j=measure(art,pid,payload,ddr)
            assert 20<=width<=24 and width==expected_clocks,(pid,payload,width)
            assert drive_j==11,drive_j
            cases+=1
        for pid in (0xd2,0x5a,0x1e):
            width,drive_j=measure(art,pid,None,ddr)
            assert width==expected_clocks and drive_j==11,(pid,width,drive_j)
            cases+=1
    return cases


def test():
    cases=check(h.build(),21)
    print('PASS transmitted EOP:',cases,'DATA/handshake/DDR cases; SE0=21clocks, J=11clocks')


if __name__=='__main__':test()
