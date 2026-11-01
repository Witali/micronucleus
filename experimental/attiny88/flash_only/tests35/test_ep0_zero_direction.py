"""USB9.3.1: wLength0 ignores D7 and always has an IN status stage."""
from tests35 import ep0_model as h
from tests35.ep0_cases import Bits,bind

def replace_wire(cpu,wire):
    old=dict(cpu.io);cleared=cpu.io.cleared_at
    cpu.io=h.SynchronizedPinIO(cpu,wire);cpu.io.update(old);cpu.io.cleared_at=cleared

def exchange(art,bm,req,value=0,index=0,retry=False):
    setup=bytes([bm,req,value&255,value>>8,index&255,index>>8,0,0])
    bind(art);cpu=h.CPU(art,Bits(h.data_packet(setup)))
    cpu.calls.pop();cpu.calls.append(cpu.labels['bootloader_process_pending_command'])
    cpu.m[0x114]=0x2d;cpu.m[0x10f]=12;cpu.r[3]=5;cpu.r[11]=0xff
    phase='setup';packet=None;statuses=[];acked=False;wire=None;before_ack=[]
    for _ in range(120000):
        assert cpu.pc!=cpu.labels['flash_do_spm'],'stale command survived SETUP'
        if cpu.pc==cpu.labels['usb_tx_acquire_bus']:
            packet=('handshake',cpu.r[20],0) if cpu.r[19]==2 else ('data',cpu.m[0x101],cpu.r[19]-4)
            if packet[0]=='data':
                statuses.append(packet);before_ack.append(cpu.m[0x10c])
                assert packet==('data',0x4b,0),packet
        if cpu.pc==cpu.labels['usb_rx_accept_ack'] and phase=='status':acked=True
        pc=cpu.pc;ins=cpu.step()
        if ins.op=='out' and ins.operands.startswith('0xb,') and pc==cpu.labels['usb_tx_eop_delay']+4:
            if packet==('handshake',0xd2,0) and phase=='setup':
                phase='status';wire=Bits(h.token(0x69),start=cpu.t+64/3);replace_wire(cpu,wire)
            elif packet==('handshake',0x5a,0):
                wire=Bits(h.token(0x69),start=cpu.t+500);replace_wire(cpu,wire)
            elif packet[0]=='data':
                if retry and len(statuses)==1:
                    # No ACK was received; the same DATA1 ZLP must repeat.
                    wire=Bits(h.token(0x69),start=cpu.t+500)
                else:wire=Bits(b'\xd2',start=cpu.t+64/3)
                replace_wire(cpu,wire)
            else:raise AssertionError(('unexpected reply',bm,req,packet))
        if acked and cpu.pc==cpu.labels['bootloader_poll_begin']:
            assert cpu.m[0x10f]==0x5a and cpu.m[0x100]&0x80
            assert before_ack==[0]*len(before_ack)
            assert len(statuses)==(2 if retry else 1)
            if req==5:assert cpu.m[0x10c]==value
            if req==9:assert cpu.m[0x115]==(value&255)
            return
    raise AssertionError(('zero-length status did not finish',bm,req,phase,statuses,hex(cpu.pc)))

def test():
    art=h.build();cases=0
    for retry in (False,True):
        for bm in (0,0x80):
            for req,value in ((5,37),(9,1),(6,0x100)):
                exchange(art,bm,req,value,retry=retry);cases+=1
        for bm in (0x40,0xc0):
            exchange(art,bm,0xb0,index=0x80,retry=retry);cases+=1
    print('PASS wLength0 ignoresD7, INstatus and immutable retry:',cases,'real wire sequences')

if __name__=='__main__':test()
