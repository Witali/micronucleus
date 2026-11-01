"""Overlong DATA cannot consume an earlier IN packet's ACK ownership.

Exercise the emitted overflow path with a pending address and deferred marker.
Reusing a nearby reject tail must not fall into recovery-J ACK acceptance.
The incoming numeric DATA CRC16 waiver does not allow an oversized packet.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
import re


def deferred_commands():
    """Use named current markers, retaining the frozen pre-SWAP encoding."""
    header = (h.ROOT / 'source/compact_protocol.inc').read_text()
    values = []
    for name, previous in (('CMD_PENDING_WRITE4', 0x40), ('CMD_PENDING_RUN', 4)):
        found = re.search(r'^#define ' + name + r'\s+(0x[0-9a-fA-F]+|[0-9]+)\s*$',
                          header, re.MULTILINE)
        values.append(int(found.group(1), 0) if found else previous)
    return (0, *values)


def check(artifact):
    bind(artifact)
    cases = 0
    for payload in (0x00, 0xff, 0x55, 0xaa, 0x15):
        for length in (9, 16):
            packet = h.data_packet(bytes([payload]) * length)
            for rate in (1_499_250, 1_500_000, 1_500_750):
                for entry in (5, 8.25, 16.5, 24.75, 32, 38.25):
                    for pending in deferred_commands():
                        cpu = h.CPU(artifact, h.Wave(packet, rate=rate), entry)
                        cpu.r[2] = 12
                        cpu.r[3] = pending
                        cpu.r[4:6] = [0x80, 0]
                        cpu.r[24] = 0xa5
                        cpu.m[0x10f] = 12
                        cpu.m[0x113] = 0x24
                        overflows = []
                        key = payload, length, rate, entry, pending
                        for _ in range(20_000):
                            if cpu.pc == 0xfffe:
                                break
                            if cpu.pc == cpu.labels['usb_rx_overflow']:
                                overflows.append(cpu.word(28) - 0x116)
                            assert cpu.pc != cpu.labels['flash_buffer_ack_write4'], key
                            cpu.step()
                        else:
                            raise AssertionError(('Overlong DATA did not return', key))
                        assert 11 in overflows, ('RX buffer limit not exercised', key, overflows)
                        assert cpu.r[2] == 0 and cpu.m[0x114] == 0, ('Authorization survived', key)
                        assert cpu.m[0x10c] == 0 and cpu.m[0x10f] == 12, ('False ACK committed state', key)
                        assert cpu.r[3] == pending and cpu.word(4) == 0x80, ('Pending command changed', key)
                        assert cpu.r[24] == 0xa5 and not cpu.raw_stack, ('Caller ABI', key)
                        assert not cpu.bus_events, ('Overlong DATA drove USB', key)
                        cases += 1
    print('PASS overlong DATA overflow, deferred command and ACK ownership:', cases)
    return cases


def test():
    return check(h.build())


if __name__ == '__main__':
    test()
