"""Physical token-tail oracle independent of a decoder's phase encoding.

Generate the complete stuffed wire, append every raw 0..7-bit tail, execute to
handler return, and check CRC5/endpoint/address authorization and exact bytes.
The incoming DATA CRC16 waiver is irrelevant to these token CRC5 checks.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import from_bits


def crc5(field):
    state=31
    for _ in range(11):
        feedback=(state^field)&1;state>>=1
        if feedback:state^=20
        field>>=1
    return state^31


def packet(pid,address,endpoint=0,flip=0):
    field=address|(endpoint<<7)
    return bytes([pid])+((field|((crc5(field)^flip)<<11))).to_bytes(2,'little')


def final_ones(bits):
    n=0
    for bit in reversed(bits):
        if not bit:break
        n+=1
    return n


def representatives():
    # Endpoint0 CRC bytes have three low zero endpoint bits. These endings
    # span every possible final one-run classes 0..5, including the maximal run.
    targets={0x00,0x80,0xc0,0xe0,0xf0,0xf8}
    found={}
    for address in range(128):
        high=packet(0x69,address)[2]
        if high in targets:found.setdefault(high,address)
    assert set(found)==targets
    # Also cover address/PID stuffing at the long address-bit runs.
    return sorted(set(found.values())|{0,1,63,126,127})


def receive(art,raw,active,entry=8):
    wave=from_bits(raw,rate=1500000,width=64/3)
    cpu=h.CPU(art,wave,entry)
    cpu.m[0x10c]=active;cpu.r[8]=crc5(active)<<3
    cpu.m[0x10f]=0x5a;cpu.r[24:26]=[0xa5,0xb6]
    admitted=[];last_eof=None;tx=[]
    labels={art['symbols'][name]:name for name in
            ('usb_rx_handle_in','usb_rx_handle_setup_or_out')}
    for _ in range(16000):
        if cpu.pc==0xfffe:break
        if cpu.pc==art['symbols']['usb_rx_end_packet']:
            last_eof=dict(time=cpu.t,count=cpu.word(28)-0x116)
        if cpu.pc in labels:
            admitted.append(dict(kind=labels[cpu.pc],time=cpu.t,count=cpu.r[23],
                                 rx=bytes(cpu.m[0x116:0x119]),eof=last_eof))
        if cpu.pc==art['symbols']['usb_tx_acquire_bus']:
            tx.append((cpu.r[19],cpu.r[20]))
        cpu.step()
    else:raise AssertionError('Token-tail handler did not return')
    assert cpu.r[24:26]==[0xa5,0xb6] and not cpu.raw_stack,'Token-tail ABI/stack'
    return wave,cpu,admitted,tx


def check(art):
    bind(art);cases=0
    vectors=[]
    for address in representatives():
        for pid in (0x69,0x2d,0xe1):
            vectors.append((packet(pid,address),address,True))
    # Keep authorization independent of framing: each negative uses a correctly
    # stuffed full wire and the same complete tail enumeration.
    for pid in (0x69,0x2d,0xe1):
        vectors.extend(((packet(pid,0,flip=1),0,False),
                        (packet(pid,0,endpoint=1),0,False),
                        (packet(pid,0,endpoint=2),0,False),
                        (packet(pid,0),1,False)))
    for data,active,authorized in vectors:
        bits=h.Wave(data).bits;run=final_ones(bits)
        for length in range(8):
            for pattern in range(1<<length):
                tail=[(pattern>>bit)&1 for bit in range(length)]
                framing=pattern==(1<<length)-1 and run+length<=6
                expected=authorized and framing
                wave,cpu,admitted,tx=receive(art,bits+tail,active)
                key=(data.hex(),active,length,pattern,run,authorized)
                assert bool(admitted)==expected,('Token-tail admission',key,admitted,tx)
                if expected:
                    assert len(admitted)==1,('Multiple token admissions',key,admitted)
                    frame=admitted[0]
                    assert frame['rx']==data and frame['count']==3,('Token bytes/count',key,frame)
                    assert frame['eof'] and frame['eof']['count']==3,('Uncommitted token bytes',key,frame)
                    assert frame['time']>=wave.boundaries[-3],('Premature token admission',key,frame)
                    if data[0]==0x69:
                        assert tx==[(2,0x5a)],('Token did not send exactly one NAK',key,tx)
                        first=next((t for t,io,value in cpu.bus_events if io==11 and value&6==4),None)
                        gap=None if first is None else first-wave.boundaries[-2]
                        assert gap is not None and 2*wave.period<=gap<=6.5*wave.period,('Token GPIO response timing',key,gap)
                    else:assert not tx and not cpu.bus_events,('OUT/SETUP token drove bus',key,tx)
                else:
                    assert not tx and not cpu.bus_events,('Invalid token drove bus',key,tx,cpu.bus_events[:3])
                assert cpu.m[0x10f]==0x5a and cpu.r[3]==0,('Token changed pending transfer',key)
                cases+=1
    print('PASS physical token CRC/stuffing-ending classes, all 0..7-bit tails and authorization:',cases,'wire cases',flush=True)
    return cases


def test():check(h.build())
if __name__=='__main__':test()
