"""SET_ADDRESS changes the live address/cache only after its real status ACK.

Exercise paired SETUP/DATA0, actual foreground CRC/status construction, IN,
lost/duplicate ACK, replacement SETUP, wrong-direction status and bus reset.
The oracle observes the active address and independent CRC5, not its storage.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import Bits, bind, Reset
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_zero_direction import replace_wire
from tests35.test_ep0_token_timeout import Joined
from tests35.test_setup_pending_marker import receive, wave_for
from tests35.test_sequential_wire import PageCPU
from tests35.test_token_crc5 import crc5


def setup(cpu, address, bm=0, request=5):
    old = cpu.m[0x10c]
    payload = bytes((bm, request, address, 0, 0, 0, 0, 0))
    assert receive(cpu, wave_for(payload, address=old)) == [(2, 0xd2)]
    assert cpu.r[3] == 11 and cpu.m[0x10f] == 0x5a
    assert cpu.m[0x10c] == old and cpu.r[8] == crc5(old) << 3
    cpu.pc = cpu.labels['bootloader_process_pending_command']
    cpu.raw_stack.clear()
    replace_wire(cpu, Quiet())
    for _ in range(4000):
        assert not cpu.nvm
        if cpu.m[0x10f] == 4 and cpu.pc == cpu.labels['bootloader_check_idle_timeout']:
            assert bytes(cpu.m[0x101:0x104]) == b'K\0\0'
            assert cpu.m[0x10c] == old and cpu.r[8] == crc5(old) << 3
            return
        cpu.step()
    raise AssertionError('SETUP did not publish DATA1 status')


def status(cpu, expected, retry=False):
    old = cpu.m[0x10c]
    cursor = cpu.word(4)
    cpu.pc = cpu.labels['bootloader_poll_begin']
    replace_wire(cpu, Bits(h.token(0x69, address=old), start=cpu.t+64))
    packet = None
    packets = []
    accepted = False
    for _ in range(60000):
        assert not cpu.nvm and cpu.word(4) == cursor
        if not accepted:
            assert cpu.m[0x10c] == old and cpu.r[8] == crc5(old) << 3
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            packet = ('handshake', cpu.r[20]) if cpu.r[19] == 2 else ('data', bytes(cpu.m[0x101:0x104]))
            if packet[0] == 'data':
                assert cpu.r[19] == 4 and packet[1] == b'K\0\0'
                packets.append(packet)
        if cpu.pc == cpu.labels['usb_rx_accept_ack']:
            assert not accepted
            accepted = True
        pc = cpu.pc
        ins = cpu.step()
        if ins.op in ('out','sbi','cbi') and pc == cpu.labels['usb_tx_eop_delay']+4:
            if packet == ('handshake', 0x5a):
                wire = Bits(h.token(0x69,address=old),start=cpu.t+500)
            elif packet and packet[0] == 'data':
                wire = Bits(h.token(0x69,address=old) if retry and len(packets)==1 else b'\xd2',
                            start=cpu.t+(500 if retry and len(packets)==1 else 64/3))
            else:
                raise AssertionError(('unexpected status response',packet))
            replace_wire(cpu,wire)
        if accepted and cpu.pc == cpu.labels['bootloader_poll_begin']:
            assert cpu.m[0x10c] == expected and cpu.r[8] == crc5(expected) << 3
            assert cpu.m[0x10f] == 0x5a and cpu.r[2:4] == [0,0]
            assert len(packets) == (2 if retry else 1)
            # No new IN was transmitted: this ACK cannot own another update.
            assert receive(cpu,Bits(b'\xd2')) == []
            assert cpu.m[0x10c] == expected and cpu.r[8] == crc5(expected) << 3
            assert not cpu.nvm and cpu.word(4) == cursor
            return
    raise AssertionError('Status ACK did not finish')


def fresh(art):
    cpu = PageCPU(art)
    cpu.m[0x10c] = 6
    cpu.r[8] = crc5(6) << 3
    cpu.r[4:6] = [0x80,0]
    return cpu


def test():
    art = h.build()
    bind(art)
    cases = 0
    for address in range(128):
        cpu = fresh(art)
        setup(cpu,address)
        status(cpu,address)
        cases += 1
    for bm in (0,0x80):
        for address in (0,1,37,127):
            cpu = fresh(art)
            setup(cpu,address,bm)
            status(cpu,address,retry=True)
            cases += 1
    for replacement in (5,9):
        cpu = fresh(art)
        setup(cpu,37)
        setup(cpu,1,request=replacement)
        status(cpu,1 if replacement==5 else 6,retry=True)
        assert cpu.m[0x115] == (1 if replacement==9 else 0)
        cases += 1
    cpu = fresh(art)
    setup(cpu,37)
    # R11's private bit6 cannot turn an OUT into SET_ADDRESS's IN status.
    out = Bits(h.token(0xe1,address=6))
    data = Bits(h.data_packet(b'',0x4b),start=out.boundaries[-2]+64/3)
    assert receive(cpu,Joined(out,data)) == [(2,0x1e)]
    assert cpu.m[0x10c] == 6 and cpu.r[8] == crc5(6) << 3
    assert not cpu.nvm and cpu.word(4) == 0x80
    setup(cpu,37)
    cpu.pc = cpu.labels['usb_poll_sample_bus']
    cpu.r[24],cpu.r[26],cpu.r[27] = 100,100,0
    replace_wire(cpu,Reset())
    for _ in range(5000):
        if cpu.pc == cpu.labels['bootloader_process_pending_command']:
            break
        cpu.step()
    else:
        raise AssertionError('Reset did not finish')
    assert cpu.r[2:4] == [0,0] and cpu.r[11] == 0
    assert cpu.m[0x10c] == 0 and cpu.r[8] == crc5(0) << 3
    assert cpu.m[0x10f] == 0x5a and not cpu.nvm
    assert receive(cpu,Bits(b'\xd2')) == []
    assert cpu.m[0x10c] == 0 and cpu.r[8] == crc5(0) << 3
    # A later ordinary status must not revive the old CRC/address either.
    setup(cpu,1,request=9)
    status(cpu,0)
    assert cpu.m[0x115] == 1
    cases += 2
    print('PASS SET_ADDRESS external address/cache ownership:',cases,
          'wire scenarios, including retry/duplicate/replacement/OUT/reset')


if __name__ == '__main__':
    test()
