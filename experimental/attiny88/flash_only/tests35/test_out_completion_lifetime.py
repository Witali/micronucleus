"""A negative OUT-completion marker must never become a new DATA reply."""
from tests35 import ep0_model as h
from tests35.ep0_cases import Bits,bind
from tests35.test_ep0_token_timeout import Joined
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_zero_direction import replace_wire
from tests35.test_sequential_wire import PageCPU,write_request,read_request


class Reset:
    pin_edges=[]
    def level(self,time):return 0
    def cell(self,time):return 'RESET'
    def edge_since(self,start,end):return False


def exchange(cpu,incoming):
    cpu.raw_stack.clear();cpu.calls.append(cpu.labels['bootloader_process_pending_command'])
    cpu.pc=cpu.labels['USB_handler'];cpu.t=incoming.boundaries[0]+8
    replace_wire(cpu,incoming);packets=[]
    for _ in range(18000):
        if cpu.pc==cpu.labels['usb_tx_acquire_bus']:
            packets.append((cpu.r[19],cpu.r[20]))
        pc=cpu.pc;ins=cpu.step()
        if ins.op=='out' and pc==cpu.labels['usb_tx_eop_delay']+4:replace_wire(cpu,Quiet())
        if cpu.pc==cpu.labels['bootloader_poll_begin']:return packets
    raise AssertionError('Post-completion packet did not finish')


def test():
    art=h.build();bind(art);cpu=PageCPU(art)
    # The private completion contract is the sign bit, including ACK D2,
    # OUT E1 and the normal exhausted subtraction values F8..FF.
    for marker in range(0x80,0x100):
        probe=PageCPU(art);probe.m[0x100]=marker;probe.m[0x10f]=0x5a
        probe.r[4:6]=[0x80,0];probe.r[14:16]=[0x88,0]
        probe.pc=probe.labels['usb_tx_prepare_pending_reply']
        for _ in range(100):
            assert probe.pc!=probe.labels['usb_tx_publish_packet_length']
            if probe.pc==probe.labels['bootloader_poll_begin']:break
            probe.step()
        else:raise AssertionError('Negative marker did not stay complete')
        assert probe.m[0x100]==marker and probe.m[0x10f]==0x5a
        assert probe.word(4)==0x80 and probe.word(14)==0x88 and not probe.nvm
    cpu.flash.memory[0x80:0xa0]=bytes(range(32))
    write_request(cpu,1,index=0x80)
    data,_=read_request(cpu,8,retry=True)
    assert data==bytes(range(8)) and cpu.word(4)==0x88
    assert cpu.m[0x100]&0x80 and cpu.m[0x10f]==0x5a
    nvm=len(cpu.nvm)
    # Delay the foreground, then repeatedly take the legitimate builder
    # path. Signed completion must bypass CRC construction/publication.
    cpu.t+=1_000_000;replace_wire(cpu,Quiet())
    for _ in range(100):
        cpu.pc=cpu.labels['usb_tx_prepare_pending_reply']
        for _ in range(100):
            assert cpu.pc!=cpu.labels['usb_tx_publish_packet_length']
            assert cpu.pc!=cpu.labels['bootloader_start_application']
            if cpu.pc==cpu.labels['bootloader_poll_begin']:break
            cpu.step()
        else:raise AssertionError('Completed reply did not remain idle')
        assert cpu.m[0x100]&0x80 and cpu.m[0x10f]==0x5a
        assert cpu.word(4)==cpu.word(14)==0x88 and len(cpu.nvm)==nvm
    for _ in range(3):
        assert exchange(cpu,Bits(h.token(0x69),start=cpu.t+16))==[(2,0x5a)]
        assert cpu.word(4)==0x88 and cpu.m[0x100]&0x80
    # Repeating the final OUT status must confirm the same consumed pointer,
    # never advance it again or resurrect the previous IN payload.
    token=Bits(h.token(0xe1),start=cpu.t+16)
    status=Bits(h.data_packet(b'',0x4b),start=token.boundaries[-2]+64/3)
    assert exchange(cpu,Joined(token,status))==[(2,0xd2)]
    assert cpu.word(4)==0x88 and cpu.m[0x100]&0x80
    data,_=read_request(cpu,2)
    assert data==bytes((8,9)) and cpu.word(4)==0x8a
    assert cpu.m[0x100]&0x80 and len(cpu.nvm)==nvm
    cpu.raw_stack.clear();cpu.pc=cpu.labels['usb_poll_sample_bus']
    cpu.r[24]=100;cpu.r[26:28]=[100,0]
    replace_wire(cpu,Reset())
    for _ in range(2000):
        if cpu.pc==cpu.labels['usb_poll_check_packet_pending'] and cpu.r[5]==0xff:break
        cpu.step()
    else:raise AssertionError('Bus reset did not retire completed control state')
    assert cpu.m[0x100]==0xff and cpu.m[0x10f]==0x5a and cpu.r[2:4]==[0,0]
    assert cpu.r[11]==0 and cpu.r[8]==0x10 and len(cpu.nvm)==nvm
    print('PASS: 128 negative markers, 100 delayed builder passes, IN retries, duplicate status, new SETUP and bus reset')


if __name__=='__main__':test()
