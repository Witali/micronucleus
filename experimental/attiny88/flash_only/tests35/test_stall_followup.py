"""Minimum-gap traffic must observe completed protocol-STALL retirement.

Exercise real linked instructions through cooperative foreground service. An IN
must retain STALL instead of old DATA, and a replacement SETUP must be received
intact. Neither path may release the canceled Flash/RUN command or move its cursor.
"""
from itertools import product

from tests35 import ep0_model as h
from tests35.ep0_cases import Bits, bind
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_token_timeout import Joined
from tests35.test_ep0_zero_direction import replace_wire
from tests35.test_sequential_wire import PageCPU


SET_CONFIGURATION = bytes((0, 9, 1, 0, 0, 0, 0, 0))


def exchange(art, next_packet, command, direction, pid, rate, entry):
    """Send an OUT error, followed by IN or SETUP at the two-bit gap."""
    cpu = PageCPU(art)
    cpu.raw_stack.clear()
    cpu.calls.append(cpu.labels['bootloader_process_pending_command'])
    cpu.pc = cpu.labels['USB_handler']
    cpu.t = entry
    cpu.r[3] = command
    cpu.r[11] = direction
    cpu.r[4:6] = [0x80, 0]
    cpu.r[24:26] = [0xa5, 0xb6]
    cpu.m[0x100] = 7
    cpu.m[0x10f] = 12
    cpu.m[0x114] = 0xe1
    cpu.m[0x101:0x10c] = h.data_packet(bytes(range(8)), 0x4b)
    replace_wire(cpu, Bits(h.data_packet(b'', pid), rate=rate))
    handshakes = []
    eops = 0
    receiver_entries = 0
    first_retired = False
    returning_context = False
    saved_caller = None
    for _ in range(30_000):
        if cpu.pc == cpu.labels['USB_handler']:
            receiver_entries += 1
            if receiver_entries > 1:
                assert first_retired, 'Next receiver overtook error retirement'
            saved_caller = cpu.r[24:26]
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            handshakes.append((cpu.r[19], cpu.r[20]))
        if cpu.pc == cpu.labels['usb_return_context']:
            returning_context = True
            if eops == 1:
                assert cpu.r[3] == 0 and cpu.m[0x100] == 0xe1
                assert cpu.m[0x10f] == 0x1e and cpu.m[0x114] == 0
                assert cpu.r[4:6] == [0x80, 0] and not cpu.nvm
                first_retired = True
            elif next_packet == 'SETUP' and eops == 2:
                assert cpu.r[3] == 11
                assert cpu.r[12:16] + cpu.r[6:8] == list(SET_CONFIGURATION[2:])
        pc = cpu.pc
        instruction = cpu.step()
        if (returning_context and pc == cpu.labels['usb_handler_return']
                and instruction.op == 'ret'):
            assert cpu.r[24:26] == saved_caller, 'Caller registers not restored'
            assert cpu.word(28) == cpu.word(30) == 0x100
            assert cpu.r[1] == 0 and cpu.r[21] == 0xa0
            returning_context = False
        if instruction.op == 'out' and pc == cpu.labels['usb_tx_eop_delay'] + 4:
            eops += 1
            incoming = Quiet()
            if eops == 1:
                start = cpu.t + 2 * 16_000_000 / rate
                token = Bits(h.token(0x69 if next_packet == 'IN' else 0x2d),
                             start=start, rate=rate)
                incoming = token
                if next_packet == 'SETUP':
                    data = Bits(h.data_packet(SET_CONFIGURATION, 0xc3), rate=rate,
                                start=token.boundaries[-2] + 2 * 16_000_000 / rate)
                    incoming = Joined(token, data)
            replace_wire(cpu, incoming)
        if eops == 2:
            if next_packet == 'IN' and cpu.pc == cpu.labels['bootloader_poll_begin']:
                break
            if (next_packet == 'SETUP'
                    and cpu.pc == cpu.labels['bootloader_check_idle_timeout']
                    and cpu.m[0x10f] == 4):
                break
    else:
        raise AssertionError(('Minimum-gap followup did not finish', hex(cpu.pc),
                              handshakes))
    expected = [(2, 0x1e), (2, 0x1e if next_packet == 'IN' else 0xd2)]
    assert handshakes == expected, ('Old DATA or incorrect handshake', handshakes)
    assert first_retired and cpu.r[3] == 0 and cpu.m[0x114] == 0
    assert cpu.r[4:6] == [0x80, 0] and not cpu.nvm
    assert not cpu.raw_stack, 'Followup leaked a return frame'
    if next_packet == 'IN':
        assert cpu.m[0x100] == 0xe1 and cpu.m[0x10f] == 0x1e
    else:
        assert cpu.m[0x115] == 1, 'Replacement SET_CONFIGURATION was not accepted'


def check(art):
    bind(art)
    groups = {'IN': 0, 'SETUP': 0}
    for values in product(('IN', 'SETUP'), (3, 4, 5, 64), (0, 0x40),
                          (0xc3, 0x4b), (1_499_250, 1_500_000, 1_500_750),
                          (5, 8.25, 16.5, 24.75, 32, 38.25)):
        try:
            exchange(art, *values)
        except AssertionError as error:
            raise AssertionError(('STALL-to-followup', values, str(error))) from error
        groups[values[0]] += 1
    assert groups == {'IN': 288, 'SETUP': 288}
    return dict(bytes=art['size'], sha256=art['sha256'], cases=sum(groups.values()),
                groups=groups)


def test():
    report = check(h.build())
    print('PASS minimum-gap error STALL retirement:', report, flush=True)


if __name__ == '__main__':
    test()
