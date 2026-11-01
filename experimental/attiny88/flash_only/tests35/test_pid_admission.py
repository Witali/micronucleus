"""Qualify every PID by completed USB/control effects, not dispatch visits.

The receiver may speculatively dispatch a PID before its exact validation.
Only an emitted response, committed control state or executed token-to-DATA
wait counts here. The incoming DATA CRC16 value waiver does not waive PID
validation, token CRC5, framing, register preservation or a balanced stack.
"""
import json

from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_rx_eop_matrix import wire


SHAPES = ('ack', 'token', 'setup', 'out')
FOCUSED_PIDS = (0x1f, 0x3f, 0x5f, 0x7f, 0x9f, 0xbf, 0xdf, 0xff,
                0x69, 0x2d, 0xe1, 0xd2, 0xc3, 0x4b)


def probe(art, pid, shape, rate=1_500_000, width=64/3, entry=8):
    if shape == 'ack':
        packet = bytes((pid,))
    elif shape == 'token':
        packet = bytes((pid, 0, 0x10))
    else:
        payload = bytes((0x40, 3, 0x11, 0x22, 0x80, 0, 0, 0)) if shape == 'setup' else b''
        base = h.data_packet(payload, 0xc3 if shape == 'setup' else 0x4b)
        packet = bytes((pid,)) + base[1:]

    cpu = h.CPU(art, wire(packet, 0, rate, width), entry)
    cpu.r[0] = 0xa5
    cpu.r[4:6] = [0x80, 0]
    cpu.r[12:16] = [0x11, 0x22, 0x88, 0]
    cpu.r[6:8] = [0x33, 0x44]
    cpu.r[11] = 0xc0
    cpu.m[0x100] = 0xff
    cpu.m[0x10f] = 4 if shape in ('ack', 'out') else 0x5a
    cpu.m[0x113] = 0x24
    cpu.m[0x114] = 0x2d if shape == 'setup' else 0xe1 if shape == 'out' else 0
    cpu.r[2] = 4 if shape == 'ack' else 0

    waited_tokens = []
    wait_pc = art['symbols']['usb_rx_wait_for_data']
    read_io = cpu.io.get

    def observe_io(address, default=0):
        value = read_io(address, default)
        # Observe the actual PCIF2 read in the token-to-DATA wait. A visit
        # to an earlier generic PID/DATA dispatcher proves no acceptance.
        if address == 0x1b and cpu.executing_pc == wait_pc and not waited_tokens:
            waited_tokens.append(cpu.r[16])
        return value

    cpu.io.get = observe_io
    for _ in range(16_000):
        if cpu.pc == 0xfffe:
            break
        cpu.step()
    else:
        raise AssertionError(('PID probe failed to return', pid, shape, rate, width, entry))

    responding = any(io == 11 and value & 6 == h.K for _, io, value in cpu.bus_events)
    expected_response = (pid == 0x69 if shape == 'token' else
                         pid == 0xc3 if shape == 'setup' else
                         pid in (0xc3, 0x4b) if shape == 'out' else False)
    expected_setup = shape == 'setup' and pid == 0xc3
    expected_cursor = 0x88 if shape == 'out' and pid == 0x4b else 0x80
    expected_ack = shape == 'ack' and pid == 0xd2
    expected_tokens = [pid] if shape == 'token' and pid in (0x2d, 0xe1) else []
    actual = (responding, cpu.r[3] == 11, cpu.word(4), cpu.m[0x10c] == 0x24,
              waited_tokens, cpu.r[0], len(cpu.raw_stack))
    expected = (expected_response, expected_setup, expected_cursor, expected_ack,
                expected_tokens, 0xa5, 0)
    return actual, expected


def check(art):
    bind(art)
    cases = 0
    errors = []

    def observe(pid, shape, rate=1_500_000, width=64/3, entry=8):
        nonlocal cases
        actual, expected = probe(art, pid, shape, rate, width, entry)
        if actual != expected:
            errors.append((pid, shape, rate, width, entry, actual, expected))
        cases += 1

    for pid in range(256):
        for shape in SHAPES:
            observe(pid, shape)
    for pid in FOCUSED_PIDS:
        for shape in SHAPES:
            for rate in (1_499_250, 1_500_000, 1_500_750):
                for width in (10.72, 24):
                    for entry in (5, 8.25, 16.5, 24.75, 32, 38.25):
                        observe(pid, shape, rate, width, entry)
    assert cases == 3_040
    report = dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                  errors=len(errors), first_errors=errors[:4])
    print('USB PID admission effects:', json.dumps(report), flush=True)
    assert not errors, ('PID admission effects', errors[:4])
    return report


def test():
    return check(h.build())


if __name__ == '__main__':
    test()
