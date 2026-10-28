"""Accepted SETUP owns R3 until dispatch, replacing cached work and replies.

The marker is created by actual paired DATA0/SETUP reception. It cannot be
created by ignored/malformed DATA, a token, an ACK or a custom opcode.
Command execution and temporary-buffer loading remain behind status ACK.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import Bits,bind
from tests35.test_ep0_token_timeout import Joined
from tests35.test_ep0_zero_direction import replace_wire
from tests35.test_sequential_wire import PageCPU
from tests35.test_ep0_token_timeout import wave

SETUP=bytes((0x80,6,0,1,0,0,18,0))
REPLACEMENT=bytes((0,9,1,0,0,0,0,0))
STATES=(0,2,3,4,5,64,11)


def wave_for(payload=SETUP,pid=0xc3,token=0x2d,address=0):
    first=Bits(h.token(token,address=address))
    second=Bits(h.data_packet(payload,pid),start=first.boundaries[-2]+64/3)
    return Joined(first,second)


def receive(cpu,wire):
    cpu.raw_stack.clear();cpu.calls.append(0xfffe)
    cpu.pc=cpu.labels['USB_handler'];cpu.t=8
    replace_wire(cpu,wire);handshakes=[]
    for _ in range(18000):
        if cpu.pc==0xfffe:
            assert cpu.word(28)==cpu.word(30)==0x100
            return handshakes
        if cpu.pc==cpu.labels['usb_tx_acquire_bus']:
            handshakes.append((cpu.r[19],cpu.r[20]))
        cpu.step()
    raise AssertionError('RX did not return')


def seeded(art,state):
    cpu=PageCPU(art)
    cpu.r[3]=state;cpu.r[2]=12
    cpu.r[4:6]=[0x80,0];cpu.r[11]=0xc0
    cpu.r[12:16]=[0xa5,0xb6,0xc7,0xd8];cpu.r[6:8]=[0x91,0xa2]
    cpu.m[0x10f]=12;cpu.m[0x100]=0xff
    cpu.m[0x101:0x10c]=bytes(range(11))
    return cpu


def owned_fields(cpu,payload):
    assert cpu.r[12:16]+cpu.r[6:8]==list(payload[2:8])


def in_response(art,address,length,rate,width,entry):
    incoming=wave(h.token(0x69,address=address),width,rate)
    cpu=seeded(art,11 if length==0x5a else 0)
    cpu.raw_stack.clear();cpu.calls.append(0xfffe)
    cpu.pc=cpu.labels['USB_handler'];cpu.t=entry
    cpu.m[0x10c]=address;cpu.r[8]=h.token(0x69,address=address)[2]
    cpu.m[0x10f]=length
    if length in (4,12):
        packet=h.data_packet(bytes(range(length-4)),0xc3)
        cpu.m[0x101:0x101+len(packet)]=packet
    replace_wire(cpu,incoming);first=None
    for _ in range(18000):
        if cpu.pc==0xfffe:return first-incoming.boundaries[-2]
        ins=cpu.step()
        if first is None and ins.op=='out' and ins.operands.startswith('0xb,') and cpu.io.get(0x0b,0)&6==h.K:
            first=cpu.t
    raise AssertionError('IN response did not return')


def test():
    art=h.build();bind(art);cases=0
    # A quiet cooperative poll must preserve the entire interrupted CRC,
    # cached header, cursor and command state. It shares the validator RET.
    for state in STATES[:-1]:
        cpu=seeded(art,state)
        cpu.r[0]=0x39;cpu.r[24:26]=[0xc2,0xd3]
        before=cpu.r[:],bytes(cpu.m)
        cpu.pc=cpu.labels['usb_service_pending']
        for _ in range(12):
            if cpu.pc==0xfffe:break
            cpu.step()
        assert cpu.pc==0xfffe and (cpu.r[:],bytes(cpu.m))==before
        assert not cpu.nvm
        cases+=1
    for state in STATES:
        cpu=seeded(art,state)
        old_packet=bytes(cpu.m[0x101:0x10c])
        assert receive(cpu,wave_for())==[(2,0xd2)]
        assert cpu.r[3]==11 and cpu.r[2]==0 and cpu.m[0x10f]==0x5a
        owned_fields(cpu,SETUP)
        assert bytes(cpu.m[0x101:0x10c])==old_packet
        assert not cpu.nvm,'Replacement SETUP performed stale Flash work'
        # An IN before dispatch must receive NAK, never old DATA. A stray
        # ACK cannot mistake pending SETUP for WRITE4's distinct bit64.
        assert receive(cpu,Bits(h.token(0x69)))==[(2,0x5a)]
        assert cpu.r[3]==11 and cpu.r[2]==0
        assert receive(cpu,Bits(b'\xd2'))==[]
        assert cpu.r[3]==11 and not cpu.nvm
        assert receive(cpu,wave_for(REPLACEMENT))==[(2,0xd2)]
        owned_fields(cpu,REPLACEMENT)
        assert cpu.r[3]==11 and cpu.m[0x10f]==0x5a
        cases+=1

    invalid=(wave_for(pid=0x4b),wave_for(payload=SETUP[:-1]),
             wave_for(payload=SETUP+b'X'),wave_for(address=1),
             Bits(h.data_packet(SETUP)),Bits(h.token(0x2d)),
             Bits(h.data_packet(SETUP),truncate=8))
    for state in STATES:
        for wire in invalid:
            cpu=seeded(art,state);before=cpu.r[12:16]+cpu.r[6:8]
            assert receive(cpu,wire)==[]
            assert cpu.r[3]==state and cpu.m[0x10f]==12
            assert cpu.r[12:16]+cpu.r[6:8]==before and not cpu.nvm
            cases+=1

    # Neither historical RX field can authorize a request any more. With
    # no pending marker, the ordinary foreground caller returns unchanged.
    for state in STATES[:-1]:
        cpu=seeded(art,state)
        cpu.m[0x112]=11;cpu.m[0x10d]=0x2d
        cpu.pc=cpu.labels['usb_validate_setup']
        for _ in range(12):
            if cpu.pc==0xfffe:break
            cpu.step()
        assert cpu.pc==0xfffe and cpu.r[3]==state and not cpu.nvm
        cases+=1

    # Every cooperative service call must discard its interrupted return
    # frame when real SETUP arrives, then publish only the new status ZLP.
    services=[];receivers=[]
    for pc in range(art['boot'],art['boot']+art['size'],2):
        offset=pc-art['boot'];word=int.from_bytes(art['body'][offset:offset+2],'little')
        if word&0xf000==0xd000:
            relative=word&0xfff
            if relative&0x800:relative-=0x1000
            target=pc+2+2*relative
            if target==cpu.labels['usb_service_pending']:services.append(pc)
            if target==cpu.labels['USB_handler']:receivers.append(pc)
    assert len(services)>=10,services
    assert len(receivers)==2,receivers
    assert {pc+2 for pc in receivers}=={cpu.labels['bootloader_process_pending_command'],cpu.labels['usb_validate_setup']},receivers
    for pc in services:
        cpu=seeded(art,64);cpu.m[0x115]=0
        cpu.pc=pc;cpu.t=8
        replace_wire(cpu,wave_for(REPLACEMENT))
        for _ in range(18000):
            if cpu.pc==cpu.labels['bootloader_check_idle_timeout'] and cpu.m[0x10f]==4:
                assert cpu.r[3]==0 and cpu.m[0x115]==1 and not cpu.nvm
                assert bytes(cpu.m[0x101:0x104])==b'K\0\0'
                assert len(cpu.raw_stack)==2,('Aborted service leaked a return frame',pc,cpu.raw_stack)
                break
            cpu.step()
        else:raise AssertionError(('New SETUP did not replace caller',hex(pc),hex(cpu.pc)))
        cases+=1
    responses=[]
    for address in (0,1,63,127):
        for length in (4,12,0x5a,0x1e):
            for rate in (1499250,1500000,1500750):
                for width in (10.72,64/3,24):
                    for entry in (5,8.25,16.5,24.75,32,38.25):
                        response=in_response(art,address,length,rate,width,entry)
                        period=16000000/rate
                        assert 2*period<=response<=6.5*period,(address,length,rate,width,entry,response)
                        responses.append(response)
    print('PASS pending SETUP marker ownership, busy IN/strayACK, malformed DATA, dead fields and all',len(services),'service callers:',cases,'cases')
    print('PASS shortened IN DATA/NAK/STALL path:',len(responses),'wire responses;',min(responses),'..',max(responses),'cycles')


if __name__=='__main__':test()
