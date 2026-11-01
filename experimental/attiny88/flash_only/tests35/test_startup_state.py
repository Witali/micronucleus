"""Cold startup and first USB exchanges must not depend on old SRAM contents.

Execute the linked reset path. Only repeated disconnect-delay iterations are
fast-forwarded; their counter, clocks and final SBIW/BRNE still execute exactly.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind, Bits
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_zero_direction import replace_wire
from tests35.test_setup_pending_marker import wave_for, SETUP


def cold(art, seed):
    bind(art)
    cpu = h.CPU(art, Quiet())
    cpu.raw_stack.clear()
    cpu.r[:] = [(seed + index * 37) & 255 for index in range(32)]
    cpu.m[0x100:0x12c] = bytes((seed + index * 53) & 255 for index in range(44))
    cpu.pc = cpu.labels['bootloader_start']
    cpu.t = 0
    cpu.step_limit = 3000000
    slices = 0
    for _ in range(1000):
        if cpu.pc == cpu.labels['usb_disconnect_delay_inner']:
            count = cpu.word(24)
            assert count > 0
            # Each skipped SBIW/taken-BRNE pair takes four clocks. The last
            # pair remains real, preserving SREG and the not-taken branch.
            cpu.t += 4 * (count - 1)
            cpu.steps += 2 * (count - 1)
            cpu.r[24:26] = [1, 0]
            slices += 1
        if cpu.pc == cpu.labels['bootloader_poll_begin']:
            break
        cpu.step()
    else:
        raise AssertionError('cold startup did not reach USB polling')
    assert slices == 44 and 0.29 * 16000000 < cpu.t < 0.31 * 16000000
    assert not cpu.raw_stack and cpu.r[1:4] == [0, 0, 0]
    assert cpu.r[5] == 255 and cpu.r[6:9] == [0, 0, 0x10] and cpu.r[11] == 0
    assert cpu.word(28) == 0x100
    assert [cpu.m[0x100 + n] for n in (0, 12, 15, 19, 20, 21)] == [255, 0, 0x5a, 0, 0, 0]
    assert cpu.io.get(0x0a, 0) & 6 == 0, 'USB pins not released after disconnect'
    return cpu


def exchange(cpu, wire):
    # Start a separate packet relative to its own waveform. No state from
    # the completed startup is seeded or cleared by this test adapter.
    cpu.pc = cpu.labels['USB_handler']
    cpu.calls.append(0xfffe)
    cpu.t = 8
    replace_wire(cpu, wire)
    before = len(cpu.bus_events)
    replies = []
    for _ in range(16000):
        if cpu.pc == 0xfffe:
            assert not cpu.raw_stack and cpu.word(28) == cpu.word(30) == 0x100
            return replies, cpu.bus_events[before:]
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            replies.append((cpu.r[19], cpu.r[20]))
        cpu.step()
    raise AssertionError('first USB exchange did not finish')


def test():
    art = h.build()
    cases = 0
    for seed in range(256):
        for packet in (h.token(0x69), b'\xd2', h.data_packet(bytes(8)),
                       h.token(0x69, address=1), h.token(0x69, endpoint=1)):
            cpu = cold(art, seed)
            replies, events = exchange(cpu, Bits(packet))
            assert replies == ([(2, 0x5a)] if packet == h.token(0x69) else []), (seed, packet.hex(), replies)
            assert bool(events) == (packet == h.token(0x69))
            assert cpu.r[2:4] == [0, 0] and cpu.r[5] == 255
            assert cpu.m[0x10c] == cpu.m[0x114] == 0
            cases += 1
        cpu = cold(art, seed)
        replies, _ = exchange(cpu, wave_for())
        assert replies == [(2, 0xd2)] and cpu.r[3] == 11
        assert cpu.r[12:16] + cpu.r[6:8] == list(SETUP[2:])
        assert cpu.m[0x10f] == 0x5a and cpu.m[0x10c] == 0
        cpu.pc = cpu.labels['bootloader_process_pending_command']
        replace_wire(cpu, Quiet())
        for _ in range(3000):
            if cpu.pc == cpu.labels['bootloader_poll_begin']:
                break
            cpu.step()
        else:
            raise AssertionError('first descriptor reply did not become ready')
        expected = h.data_packet(art['body'][20:28], 0x4b)
        assert cpu.m[0x10f] == 12
        assert bytes(cpu.m[0x101:0x10c]) == expected, 'cold-start descriptor or CRC depends on old SRAM'
        cases += 1
    print('PASS cold startup and first USB packets from poisoned SRAM:', cases, 'cases')


if __name__ == '__main__':
    test()
