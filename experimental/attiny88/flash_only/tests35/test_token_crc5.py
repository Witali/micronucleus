"""Independent endpoint-zero token oracle over the linked AVR dispatch path.

Raw-wave tests separately verify that the decoder's count/phase observations
really correspond to complete bytes. This suite does not assume that proof.
"""
from tests35 import ep0_model as h
from tests35.address_state import active as active_address,active_crc,seed_active,pending_crc,paired
from tests35.address_state import pending
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
    cpu.m[0x100:0x12C]=bytes(44)
    seed_active(cpu,address,crc5(address)<<3)
    cpu.r[13 if paired(cpu) else 10]=0xA5  # retain the unrelated pending-cache poison
    cpu.m[0x10F]=0x5A
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
    # A real decoder also advances its committed-byte pointer. Keep both
    # observations consistent: the composed receiver derives count from Y,
    # avoiding the countdown's phantom byte on interrupted bit6/7 paths.
    cpu.r[28]=(0x16+length)&255
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
    assert active_crc(cpu)==0x10
    cpu.pc=artifact['symbols']['usb_poll_check_reset_duration']
    cpu.r[24:26]=[1,0]
    seed_active(cpu,active_address(cpu),0xA5)
    for _ in range(80):
        if cpu.pc==artifact['symbols']['usb_poll_check_packet_pending']:break
        cpu.step()
    else:raise AssertionError('Bus reset did not reach the polling boundary')
    assert active_address(cpu)==0 and active_crc(cpu)==0x10
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
    # Internal phase tags differ between complete-byte and qualified-dribble
    # receivers. Their producer invariants cannot be tested by injecting every
    # arbitrary register value. test_token_framing_wire instead enumerates the
    # actual physical tails and requires exact bytes/count and authorization.
    # USB9.4.6 leaves values above127 undefined; only valid addresses have
    # a required endpoint-zero CRC/cache outcome.
    for address in range(128):
        reset(cpu,artifact,42)
        canonical=address&127
        before=active_crc(cpu)
        cpu.r[12],cpu.r[24],cpu.r[25]=address,0,5
        cpu.r[28:30]=[0,1]
        cpu.pc=artifact['symbols']['usb_standard_dispatch']
        for _ in range(1500):
            if cpu.pc==artifact['symbols']['usb_reply_empty']:break
            cpu.step()
        else:raise AssertionError('Pending SET_ADDRESS did not complete')
        assert active_crc(cpu)==before and active_address(cpu)==42
        assert pending_crc(cpu)==(crc5(canonical)<<3)
        assert pending(cpu)==canonical
        cpu.r[2],cpu.r[23]=12,1
        cpu.pc=artifact['symbols']['usb_rx_check_ack']
        for _ in range(120):
            if cpu.pc==artifact['symbols']['usb_handler_packet_done']:break
            cpu.step()
        else:raise AssertionError('Eligible ACK did not complete')
        assert active_address(cpu)==canonical and active_crc(cpu)==pending_crc(cpu)
    print('PASS',cases,'token address/endpoint/CRC5/count cases and128 valid atomic address-cache commits')


if __name__=='__main__':test()
