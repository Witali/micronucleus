"""Control-read wire completion: exact wLength, short replies and required ZLP.

USB2 5.5.3 advances to Status at wLength bytes or a short packet. 8.5.3.3
requires a correctly paired OUT/DATA1 status to retire the final IN even if
its ACK was lost. Starting from the validated length limiter, this test runs
all emitted packet construction, IN/ACK and OUT/DATA1 reception instructions.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_token_timeout import Joined
CPU=h.CPU

def incoming_wire(cpu,wire):
    old=dict(cpu.io);cleared=cpu.io.cleared_at
    cpu.io=h.SynchronizedPinIO(cpu,wire);cpu.io.update(old);cpu.io.cleared_at=cleared

def control_read(art,requested=8,available=18,status_gap=64,kind='descriptor'):
    bind(art);c=CPU(art,Quiet());c.t=0;c.pc=c.labels['usb_reply_limit_length']
    c.r[6:8]=[requested&255,requested>>8];c.r[24]=available
    c.r[9]=0xc3;c.r[11]=0x80 if kind=='descriptor' else 0xc0
    pointer=art['boot']+20 if kind=='descriptor' else 0x80
    c.r[14:16]=[pointer&255,pointer>>8]
    c.m[0x100]=0xff;c.m[0x10f]=0x5a
    period=32/3;wire=None;data=[];tx_kind=None;status_pending=False;status_j=None
    first_sent=False;status_response=None;status_data_j=None;first_k=None
    for _ in range(150000):
        if not first_sent and c.m[0x10f]!=0x5a:
            wire=Bits(h.token(0x69),start=c.t+64);incoming_wire(c,wire);first_sent=True
        if c.pc==c.labels['usb_tx_acquire_bus']:
            if c.r[19]==2:
                tx_kind=('handshake',c.r[20],0)
            else:
                n=c.r[19]-4
                tx_kind=('data',c.m[0x101],n)
                data.append((c.m[0x101],bytes(c.m[0x102:0x102+n]).hex()))
            first_k=None
        pc=c.pc;ins=c.step()
        if ins.op=='out' and ins.operands.startswith('0xb,') and c.io.get(11,0)&6==h.K and first_k is None:
            first_k=c.t
        if ins.op=='out' and ins.operands.startswith('0xb,') and pc==c.labels['usb_tx_eop_delay']+4:
            assert tx_kind is not None
            if tx_kind[0]=='data':
                ack=Bits(b'\xd2',start=c.t+2*period)
                amount=sum(len(bytes.fromhex(row[1])) for row in data)
                if tx_kind[2]<8 or amount>=requested:
                    assert amount<=requested
                    token=Bits(h.token(0xe1),start=ack.boundaries[-2]+status_gap)
                    zlp=Bits(h.data_packet(b'',0x4b),start=token.boundaries[-2]+2*period)
                    status_data_j=zlp.boundaries[-2]
                    wire=Joined(Joined(ack,token),zlp);status_pending=True
                else:wire=Joined(ack,Bits(h.token(0x69),start=ack.boundaries[-2]+500))
                incoming_wire(c,wire)
            elif tx_kind[1]==0x5a:
                wire=Bits(h.token(0x69),start=c.t+500);incoming_wire(c,wire)
            elif tx_kind[1]==0xd2 and status_pending:
                status_j=c.t;status_response=first_k-status_data_j
                incoming_wire(c,Quiet())
            else:raise AssertionError(('unexpected handshake',tx_kind,c.t))
        if status_j is not None and c.pc==c.labels['bootloader_poll_begin']:
            return dict(data=data,tx=c.m[0x10f],message=c.m[0x100],direction=c.r[11],
                        status_response=status_response,peak=c.peak,status_gap=status_gap)
    raise AssertionError(('control read did not finish',requested,available,status_gap,hex(c.pc),c.t,data))

def test():
    art=h.build();rows=[]
    for gap in range(22,121,2):
        row=control_read(art,status_gap=gap)
        assert row['tx']==0x5a and row['message']==0xff,(gap,row)
        assert [len(bytes.fromhex(p[1])) for p in row['data']]==[8],row
        assert row['data'][0][1]==art['body'][20:28].hex(),row
        rows.append(row)
    for requested,available,kind,lengths in [(16,18,'descriptor',[8,8]),(18,18,'descriptor',[8,8,2]),
            (64,18,'descriptor',[8,8,2]),(64,8,'read8',[8,0]),(8,8,'read8',[8]),
            (7,18,'descriptor',[7]),(9,18,'descriptor',[8,1])]:
        row=control_read(art,requested,available,64,kind)
        assert [len(bytes.fromhex(p[1])) for p in row['data']]==lengths,row
        assert row['tx']==0x5a and row['message']==0xff,row
        assert [p[0] for p in row['data']]==[0x4b if i%2==0 else 0xc3 for i in range(len(lengths))],row
        rows.append(row)
    responses=[row['status_response'] for row in rows]
    assert 2*(32/3)<=min(responses) and max(responses)<=6.5*(32/3),responses
    print('PASS control-read exact/short/required-ZLP completion:',len(rows),
          'wire sequences; OUT-status ACK',min(responses),'..',max(responses),'cycles')

if __name__=='__main__':test()
