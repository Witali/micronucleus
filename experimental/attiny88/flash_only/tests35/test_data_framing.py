"""USB DATA may end in legal all-one dribble, never arbitrary partial bytes.

USB2.0 bit-stuffing/dribble rules are independent of the project's explicit
received-CRC16 waiver. All base packets have correct CRC16; varying valid
payload words covers every ending class without depending on that waiver.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import Bits,bind
from tests35.phy_model import from_bits,bits_wave


def final_ones(bits):
    count=0
    for bit in reversed(bits):
        if not bit:break
        count+=1
    return count


def ending_packets(setup,length):
    targets={0,0x80,0xc0,0xe0,0xf0,0xf8,0xfc,0xfe}
    found={}
    for word in range(65536):
        payload=bytearray([0x40,3,0,0,0x80,0,0,0] if setup else range(length))
        offset=2 if setup else 0
        payload[offset:offset+2]=word.to_bytes(2,'little')
        packet=h.data_packet(payload,0xc3 if setup else 0x4b)
        if packet[-1] in targets:
            found.setdefault(packet[-1],(packet,bytes(payload)))
        if len(found)==len(targets):return [found[value] for value in sorted(targets)]
    raise AssertionError('CRC ending corpus is incomplete')


def receive(art,packet,tail,setup,raw_bits=None):
    wire=from_bits(Bits(packet).bits+list(tail) if raw_bits is None else raw_bits)
    cpu=h.CPU(art,wire,8)
    cpu.m[0x114]=0x2d if setup else 0xe1
    cpu.m[0x10f]=0x5a if setup else 4
    cpu.r[4:6]=[0x80,0]
    cpu.r[12:16]=[0x11,0x22,0x88,0]
    cpu.r[6:8]=[0x33,0x44]
    cpu.r[11]=0 if setup else 0xc0
    for _ in range(10000):
        if cpu.pc==0xfffe:break
        cpu.step()
    else:raise AssertionError('DATA framing probe did not finish')
    return cpu


def test():
    art=h.build();bind(art);cases=0
    for setup in (True,False):
        for payload_length in ((8,) if setup else (2,8)):
            # FC/FE also cover a mandatory stuffed zero at/near the end.
            for packet,payload in ending_packets(setup,payload_length):
                last_crc=packet[-1]
                run=final_ones(Bits(packet).bits)
                for length in range(8):
                    for pattern in range(1<<length):
                        tail=[(pattern>>bit)&1 for bit in range(length)]
                        legal=pattern==(1<<length)-1 and run+length<=6
                        cpu=receive(art,packet,tail,setup)
                        accepted=cpu.r[3]==11 if setup else cpu.word(4)==0x88
                        context=(setup,len(payload),last_crc,length,pattern,run,accepted)
                        assert accepted==legal,('DATA tail admission',context)
                        assert bool(cpu.bus_events)==legal,('DATA tail bus response',context,cpu.bus_events)
                        if legal and setup:
                            assert cpu.r[12:16]+cpu.r[6:8]==list(payload[2:])
                        if not legal:
                            assert cpu.word(4)==0x80 and cpu.r[3]==0,('invalid DATA changed control state',context)
                            assert cpu.r[12:16]+cpu.r[6:8]==[0x11,0x22,0x88,0,0x33,0x44]
                            assert cpu.m[0x10f]==(0x5a if setup else 4),'invalid DATA retired TX cache'
                        cases+=1
                if setup:
                    encoded,stuff=bits_wave(packet)
                    terminal_stuff=int(bool(stuff) and stuff[-1]==len(encoded.bits)-1)
                    for missing in range(1,8):
                        # Remove actual CRC data bits, not just an optional
                        # terminal stuffed symbol. SETUP still needs 8 bytes.
                        raw=encoded.bits[:-(missing+terminal_stuff)]
                        cpu=receive(art,packet,(),True,raw)
                        assert cpu.r[3]==0 and not cpu.bus_events,('truncated SETUP CRC',last_crc,missing)
                        cases+=1
    empty=h.data_packet(b'',0x4b)
    for missing in range(1,8):
        cpu=receive(art,empty,(),False,Bits(empty).bits[:-missing])
        assert cpu.word(4)==0x80 and not cpu.bus_events,('truncated empty OUT CRC',missing)
        cases+=1
    for size in (1,2):
        cpu=receive(art,empty[:size],(),False)
        assert cpu.word(4)==0x80 and not cpu.bus_events,('OUT lacks two CRC bytes',size)
        cases+=1
    print('PASS DATA full-byte/dribble admission, all partial tails and CRC ending classes:',cases,'wire cases')


if __name__=='__main__':test()
