"""Independent endpoint-zero token oracle over the linked AVR dispatch path.

Raw-wave tests separately verify that the decoder's count/phase observations
really correspond to complete bytes. This suite does not assume that proof.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_nvm_state import initialized


def crc5(value):
    remainder=31
    for _ in range(11):
        remainder=(remainder>>1)^(20 if (remainder^value)&1 else 0)
        value>>=1
    return remainder^31


class Quiet:
    pin_edges=[]
    def level(self,time):return h.J
    def cell(self,time):return 'IDLE'
    def edge_since(self,start,end):return False


def reset(cpu,artifact,address=0):
    cpu.r[:]=[0]*32
    cpu.r[28:32]=[0x19,1,0,1]
    cpu.r[21]=0xA0
    cpu.r[8]=crc5(address)<<3
    cpu.r[10]=0xA5
    cpu.m[0x100:0x12C]=bytes(44)
    cpu.m[0x10C],cpu.m[0x10F]=address,0x5A
    cpu.io={0x1B:0,9:h.J,10:0,11:h.J}
    cpu.raw_stack[:]=[0xFF,0x7F]
    cpu.pc=artifact['symbols']['usb_rx_end_packet']
    cpu.t=0
    cpu.flags=0xA5
    cpu.steps=0
    cpu.bus_events=[]
    cpu.visited.clear()


def dispatch(cpu,artifact,pid,word,address=0,length=3,pair=None,last_odd=h.J):
    reset(cpu,artifact,address)
    # A complete packet of any length has its own pair phase. Changing length
    # alone must exercise token length admission, not fail the earlier gate.
    cpu.r[16],cpu.r[17]=0,last_odd
    cpu.r[22]=(0x55-length)&255 if pair is None else pair
    cpu.r[23]=(11-length)&255
    cpu.m[0x116:0x119]=bytes((pid,word&255,word>>8))
    ends={artifact['symbols'][name]:name for name in
          ('usb_rx_handle_in','usb_rx_handle_setup_or_out','usb_rx_ignore_packet')}
    for _ in range(120):
        if cpu.pc in ends:return ends[cpu.pc]!='usb_rx_ignore_packet'
        cpu.step()
    raise AssertionError('Token dispatch failed to return')


def test():
    artifact=h.build()
    bind(artifact)
    # Execute the real cold-start call with a poisoned cache. The shared
    # initializer's location and instruction spelling are not the contract.
    cpu=initialized(artifact,0xa5)
    assert cpu.r[8]==0x10
    cpu.pc=artifact['symbols']['usb_poll_check_reset_duration']
    cpu.r[24:26]=[1,0]
    cpu.r[8]=0xA5
    for _ in range(80):
        if cpu.pc==artifact['symbols']['usb_poll_check_packet_pending']:break
        cpu.step()
    else:raise AssertionError('Bus reset did not reach the polling boundary')
    assert cpu.m[0x10C]==0 and cpu.r[8]==0x10
    cases=0
    for active in range(128):
        for endpoint in range(16):
            field=active|(endpoint<<7)
            for check in range(32):
                expected=endpoint==0 and check==crc5(field)
                for pid in (0x69,0x2D,0xE1):
                    assert dispatch(cpu,artifact,pid,field|(check<<11),address=active)==expected
                    cases+=1
        for received in range(128):
            assert dispatch(cpu,artifact,0x69,received|(crc5(received)<<11),address=active)==(active==received)
            cases+=1
    for length in range(256):
        assert dispatch(cpu,artifact,0x69,crc5(0)<<11,length=length)==(length==3)
        cases+=1
    for pair in range(256):
        for last_odd in (0,2,4,6):
            assert dispatch(cpu,artifact,0x69,crc5(0)<<11,pair=pair,last_odd=last_odd)==(pair==0x52 and last_odd!=0)
            cases+=1
    # USB9.4.6 leaves values above127 undefined; only valid addresses have
    # a required endpoint-zero CRC/cache outcome.
    for address in range(128):
        reset(cpu,artifact,42)
        canonical=address&127
        before=cpu.r[8]
        cpu.r[12],cpu.r[24],cpu.r[25]=address,0,5
        cpu.r[28:30]=[0,1]
        cpu.pc=artifact['symbols']['usb_standard_dispatch']
        for _ in range(1500):
            if cpu.pc==artifact['symbols']['usb_reply_empty']:break
            cpu.step()
        else:raise AssertionError('Pending SET_ADDRESS did not complete')
        assert cpu.r[8]==before and cpu.m[0x10C]==42
        assert cpu.r[10]==(crc5(canonical)<<3)
        assert cpu.m[0x113]==canonical
        cpu.r[2],cpu.r[23]=12,1
        cpu.pc=artifact['symbols']['usb_rx_check_ack']
        for _ in range(120):
            if cpu.pc==artifact['symbols']['usb_handler_packet_done']:break
            cpu.step()
        else:raise AssertionError('Eligible ACK did not complete')
        assert cpu.m[0x10C]==canonical and cpu.r[8]==cpu.r[10]
    print('PASS',cases,'token address/endpoint/CRC5/count/phase cases and128 valid atomic address-cache commits')


if __name__=='__main__':test()
