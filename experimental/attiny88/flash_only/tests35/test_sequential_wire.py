"""Actual emitted USB exchange plus ATtiny88 once-per-slot buffer semantics."""
from tests35 import ep0_model as h
from tests35.ep0_cases import Bits,bind
from tests35.test_ep0_zero_direction import replace_wire
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_token_timeout import Joined

class PageCPU(h.CPU):
    def __init__(self,art):
        super().__init__(art,Quiet())
        self.buffer={};self.nvm=[];self.status_acked=False
    def step(self):
        pc=self.pc
        word=self.flash[pc]|self.flash[pc+1]<<8
        if word==0x95e8:
            command=self.io.get(0x37,0)
            address=self.r[30]|self.r[31]<<8
            data=self.r[0]|self.r[1]<<8
            self.nvm.append((command,address,data,self.status_acked))
            if command==17:self.buffer.clear()
            elif command==1:
                assert self.status_acked,'buffer load occurred before status ACK'
                slot=address&63
                assert slot not in self.buffer,('SPM slot loaded twice',slot,self.nvm)
                self.buffer[slot]=data
            elif command==3:
                assert self.status_acked,'erase occurred before status ACK'
                page=address&~63
                self.flash.memory[page:page+64]=bytes([255])*64
                self.t+=72000
            elif command==5:
                assert self.status_acked,'page write occurred before status ACK'
                assert address%64==0
                assert len(self.buffer)==32,('incomplete auto page write',len(self.buffer))
                for offset,data in self.buffer.items():
                    old=int.from_bytes(self.flash.memory[address+offset:address+offset+2],'little')
                    assert old&data==data,'page was not erased before programming'
                    self.flash.memory[address+offset:address+offset+2]=data.to_bytes(2,'little')
                self.buffer.clear();self.t+=72000
            else:raise AssertionError(('unexpected SPM operation',command))
        return super().step()

def write_request(cpu,opcode,value=0,index=0,retry=False,followup=False,rate=1500000,ack_phase=0,
                  ack_extra_ones=0,ack_eop_cycles=None):
    period=16000000/rate
    assert 0<=ack_extra_ones<=4
    def bits(packet,**kwargs):
        if packet==b'\xd2':
            kwargs['start']=kwargs.get('start',0)+ack_phase
            if ack_extra_ones or ack_eop_cycles is not None:
                from tests35.phy_model import from_bits
                # Append raw final ones after encoding. A hub may extend the
                # final run to six; it does not add another stuffed symbol.
                raw=Bits(packet,rate=rate).bits+[1]*ack_extra_ones
                wave=from_bits(raw,rate,2*period if ack_eop_cycles is None else ack_eop_cycles)
                start=kwargs['start']
                wave.start=start;wave.end+=start
                wave.boundaries=[t+start for t in wave.boundaries]
                wave.pin_edges=[t+start for t in wave.pin_edges]
                return wave
        return Bits(packet,rate=rate,**kwargs)
    before=len(cpu.nvm);cursor=cpu.r[4]|cpu.r[5]<<8
    setup=bytes([0x40,opcode,value&255,value>>8,index&255,index>>8,0,0])
    cpu.status_acked=False
    cpu.raw_stack.clear();cpu.calls.append(cpu.labels['bootloader_process_pending_command'])
    cpu.pc=cpu.labels['USB_handler'];cpu.m[0x114]=0x2d
    wire=bits(h.data_packet(setup),start=cpu.t+16)
    cpu.t=wire.start+8;replace_wire(cpu,wire)
    tx=None;phase='setup';statuses=0;acks=0;accepted_followup=False;followup_end=None
    followup_ack=False;followup_eop=False
    following=bytes([0x40,3,0x55,0x66,0x77,0x88,0,0])
    for _ in range(150000):
        if followup_ack:
            # The public boundary is before any later RX or foreground
            # dispatch. A SETUP may be shadowed during ACK completion,
            # provided no subsequent token can overwrite its raw header.
            assert cpu.pc not in (cpu.labels['USB_handler'],cpu.labels['usb_rx_wait_for_j']), 'RX overtook accepted SETUP'
            if cpu.pc in (cpu.labels['usb_validate_setup'],cpu.labels['bootloader_process_pending_command']):
                assert followup_eop and cpu.io.get(0x0a,0)&6==0,'SETUP returned before ACK release'
                assert cpu.r[12:16]+cpu.r[6:8]==list(following[2:]),'next SETUP shadow corrupted'
                assert cpu.r[1]==0 and acks==1 and statuses==(2 if retry else 1)
                return
        if followup and cpu.status_acked and cpu.pc==cpu.labels['usb_rx_setup_data']:
            # A new minimum-gap SETUP may arrive immediately after the ACK.
            # It must not cancel a successfully completed previous WRITE4.
            assert len([row for row in cpu.nvm[before:] if row[0]==1])==2,('new SETUP overtook WRITE4',cpu.nvm[before:])
            assert cpu.r[4]|cpu.r[5]<<8==cursor+4
            assert bytes(cpu.m[0x116:0x121])==h.data_packet(following),'next SETUP bytes corrupted'
            accepted_followup=True
        if cpu.pc==cpu.labels['usb_tx_acquire_bus']:
            tx=('handshake',cpu.r[20]) if cpu.r[19]==2 else ('data',cpu.m[0x101])
            if followup and cpu.status_acked and cpu.r[3]==11 and tx==('handshake',0xd2):
                assert accepted_followup,'next SETUP ACK without its DATA'
                followup_ack=True
            if tx[0]=='data':
                statuses+=1
                assert cpu.r[19]==4 and tx[1]==0x4b
                if opcode==3:
                    assert len(cpu.nvm)==before and cpu.r[4]|cpu.r[5]<<8==cursor
        if cpu.pc==cpu.labels['usb_rx_accept_ack']:
            assert phase=='status';cpu.status_acked=True;acks+=1
            assert acks==1,'old status ACK accepted more than once'
        pc=cpu.pc;ins=cpu.step()
        if ins.op=='out' and pc==cpu.labels['usb_tx_eop_delay']+4:
            if followup_ack:
                followup_eop=True;replace_wire(cpu,Quiet())
            elif tx==('handshake',0xd2) and phase=='setup':
                phase='status';replace_wire(cpu,bits(h.token(0x69),start=cpu.t+2*period))
            elif tx==('handshake',0x5a):
                replace_wire(cpu,bits(h.token(0x69),start=cpu.t+500))
            elif tx[0]=='data':
                wire=bits(h.token(0x69) if retry and statuses==1 else b'\xd2',
                          start=cpu.t+(500 if retry and statuses==1 else 2*period))
                if followup and not (retry and statuses==1):
                    token=bits(h.token(0x2d),start=wire.boundaries[-2]+2*period)
                    data=bits(h.data_packet(following),start=token.boundaries[-2]+2*period)
                    followup_end=data.end
                    wire=Joined(Joined(wire,token),data)
                replace_wire(cpu,wire)
            else:raise AssertionError(('unexpected reply',tx,phase))
        if not followup and cpu.status_acked and cpu.pc==cpu.labels['bootloader_poll_begin']:
            assert statuses==(2 if retry else 1)
            assert cpu.r[3]==0
            return
        if followup_end is not None and cpu.t>followup_end+1000:
            raise AssertionError(('next SETUP not accepted',hex(cpu.pc),cpu.t,cpu.r[3],cpu.r[4]|cpu.r[5]<<8,cpu.nvm[before:]))
    raise AssertionError(('request did not finish',opcode,phase,hex(cpu.pc),cpu.t))

def read_request(cpu,length=8,retry=False,standard=False):
    cursor=cpu.r[4]|cpu.r[5]<<8
    setup=bytes([0x80 if standard else 0xc0,6 if standard else 0xb0,
                 0,1 if standard else 0,0,0,length,0])
    cpu.raw_stack.clear();cpu.calls.append(cpu.labels['bootloader_process_pending_command'])
    cpu.pc=cpu.labels['USB_handler'];cpu.m[0x114]=0x2d
    wire=Bits(h.data_packet(setup),start=cpu.t+16)
    cpu.t=wire.start+8;replace_wire(cpu,wire)
    tx=None;phase='setup';packets=[];done=False;ack_response=None;status_j=None;first_k=None
    for _ in range(150000):
        if cpu.pc==cpu.labels['usb_tx_acquire_bus']:
            tx=('handshake',cpu.r[20]) if cpu.r[19]==2 else ('data',cpu.m[0x101])
            first_k=None
            if tx[0]=='data':
                n=cpu.r[19]-4
                packets.append((cpu.m[0x101],bytes(cpu.m[0x102:0x102+n])))
                assert cpu.r[4]|cpu.r[5]<<8==cursor,'IN preparation/retry moved cursor'
        pc=cpu.pc;ins=cpu.step()
        if ins.op=='out' and ins.operands.startswith('0xb,') and cpu.io.get(11,0)&6==h.K and first_k is None:
            first_k=cpu.t
        if ins.op=='out' and pc==cpu.labels['usb_tx_eop_delay']+4:
            if tx==('handshake',0xd2) and phase=='setup':
                phase='read';replace_wire(cpu,Bits(h.token(0x69),start=cpu.t+64/3))
            elif tx==('handshake',0x5a):
                replace_wire(cpu,Bits(h.token(0x69),start=cpu.t+500))
            elif tx[0]=='data':
                if retry and len(packets)==1:
                    replace_wire(cpu,Bits(h.token(0x69),start=cpu.t+500))
                else:
                    ack=Bits(b'\xd2',start=cpu.t+64/3)
                    token=Bits(h.token(0xe1),start=ack.boundaries[-2]+64)
                    status=Bits(h.data_packet(b'',0x4b),start=token.boundaries[-2]+64/3)
                    status_j=status.boundaries[-2]
                    replace_wire(cpu,Joined(Joined(ack,token),status));phase='status'
            elif tx==('handshake',0xd2) and phase=='status':
                ack_response=first_k-status_j
                replace_wire(cpu,Quiet());done=True
            else:raise AssertionError(('unexpected read reply',tx,phase))
        if done and cpu.pc==cpu.labels['bootloader_poll_begin']:
            assert packets[0][0]==0x4b and len(packets[0][1])==length
            assert len(packets)==(2 if retry else 1)
            assert all(row==packets[0] for row in packets),'IN retry changed data or PID'
            assert cpu.r[4]|cpu.r[5]<<8==(cursor if standard else cursor+length)
            assert 2*(32/3)<=ack_response<=6.5*(32/3),ack_response
            return packets[0][1],ack_response
    raise AssertionError(('read did not finish',phase,hex(cpu.pc),cpu.t))

def check():
    art=h.build();bind(art)
    cases=0
    for page in (0,0x80,art['boot']-64):
        for retry in (False,True):
            cpu=PageCPU(art)
            write_request(cpu,2,index=page,retry=retry)
            assert cpu.r[4]|cpu.r[5]<<8==page
            expected=bytes((page+i*37)&255 for i in range(64))
            for offset in range(0,64,4):
                a=int.from_bytes(expected[offset:offset+2],'little')
                b=int.from_bytes(expected[offset+2:offset+4],'little')
                write_request(cpu,3,a,b,retry=retry)
                assert cpu.r[4]|cpu.r[5]<<8==page+offset+4
                assert len([row for row in cpu.nvm if row[0]==5])==(offset==60)
                cases+=1
            assert bytes(cpu.flash.memory[page:page+64])==expected
            assert not cpu.buffer
            assert len([row for row in cpu.nvm if row[0]==1])==32
    print('PASS sequential WRITE4, immutable status retry, one load per word and auto page write:',cases,'wire sequences')
    reads=0;responses=[]
    for start in (0x80,0xf8,art['boot']-8,8184):
        for retry in (False,True):
            for length in (2,4,8):
                cpu=PageCPU(art)
                expected=bytes((start+i*13)&255 for i in range(length))
                cpu.flash.memory[start:start+length]=expected
                write_request(cpu,1,index=start)
                value,response=read_request(cpu,length,retry=retry)
                assert value==expected,(start,length,value.hex(),expected.hex())
                responses.append(response);reads+=1
    for retry in (False,True):
        cpu=PageCPU(art);write_request(cpu,1,index=0x80)
        value,response=read_request(cpu,8,retry=retry,standard=True)
        assert value==art['body'][20:28]
        responses.append(response);reads+=1
    print('PASS sequential READ cursor, actual-length advance, immutable IN retry and standard-read isolation:',reads,
          'wire sequences; OUT-status ACK cycles',min(responses),max(responses))
    cpu=PageCPU(art);write_request(cpu,1,index=0x80)
    write_request(cpu,3,0x1122,0x3344,followup=True)
    print('PASS minimum2bit next SETUP cannot overtake an acknowledged WRITE4')
    spacing=0
    for rate in (1499250,1500000,1500750):
        for quarter in range(33):
            cpu=PageCPU(art);write_request(cpu,1,index=0x80,rate=rate,ack_phase=quarter/4)
            write_request(cpu,3,0x1122,0x3344,followup=True,rate=rate,ack_phase=quarter/4)
            spacing+=1
    print('PASS minimum-gap ACK-to-SETUP:',spacing,'host-rate/ACK-phase cases')

if __name__=='__main__':check()
