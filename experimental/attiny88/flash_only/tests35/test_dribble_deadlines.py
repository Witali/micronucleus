"""Token/DATA deadlines at directed final-one dribble extrema.

USB 2.0 sections 7.1.19.1 and 7.1.9.1 require receiving SOP through 16 bit
times, expiring before 18, and accepting a final no-transition run up to six
ones. Check the physical PIN observation and actual received bytes, accepted
SETUP shadow and OUT-status cursor; an entry-time estimate is not an oracle.
The finite cases exercise four ending routes without assuming their encoding.
"""
import math

from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_token_timeout import Joined

SETUPS = (bytes((0x40, 3, 0xff, 0xff, 0x55, 0xaa, 0, 0)),
          bytes((0x80, 6, 0, 1, 0, 0, 18, 0)))

# Historical deadline extrema and the slow-host odd-five route. Each seed is
# (PID, address, appended ones, SE0 clocks, handler entry clocks).
SEEDS = ((0x2d, 0, 0, 24, 5), (0xe1, 63, 1, 10.72, 16.5),
         (0x2d, 0, 3, 24, 5), (0xe1, 63, 2, 10.72, 16.5),
         (0x2d, 0, 5, 24, 5), (0xe1, 63, 4, 10.72, 16.5),
         (0x2d, 0, 6, 24, 5), (0xe1, 1, 3, 10.72, 5),
         (0x2d, 0, 5, 24, 32), (0x2d, 3, 5, 24, 32),
         (0x2d, 7, 5, 24, 32), (0x2d, 55, 5, 24, 32))


def legal_tails(packet):
    run = 0
    for bit in reversed(h.Wave(packet).bits):
        if bit != 1:
            break
        run += 1
    return range(7 - run)


def skew(sign):
    return (lambda index, line: sign * 0.55 * (1 if line == h.K else -1)) if sign else None


def packet_wave(packet, tail, width, rate, jitter=None, start=0):
    """Append raw dribble without inserting a new transmitter-stuffed zero."""
    value = h.Wave(packet, rate=rate)
    value.bits = value.bits + [1] * tail
    value.boundaries, value.levels, value.labels = [], [], []
    line = h.J
    for index, bit in enumerate(value.bits):
        if not bit:
            line = h.K if line == h.J else h.J
        value.boundaries.append(start + index * value.period
                                + (jitter(index, line) if jitter else 0))
        value.levels.append(line)
        value.labels.append(index)
    end = start + len(value.bits) * value.period
    value.boundaries.extend((end, end + width, end + width + value.period))
    value.levels.extend((0, h.J, h.J))
    value.labels.extend(('SE0', 'EOP_J', 'idle'))
    value.start = value.boundaries[0]
    value.end = value.boundaries[-1]
    value.pin_edges = []
    before = h.J
    for time, line in zip(value.boundaries, value.levels):
        if (before ^ line) & 4:
            value.pin_edges.append(time)
        before = line
    return value


def cpu_for(art, wire, pid, address, entry):
    bind(art)
    cpu = h.CPU(art, wire, entry)
    cpu.m[0x10c] = address
    cpu.r[8] = cpu.r[10] = h.token(pid, address=address)[2]
    cpu.m[0x10f], cpu.m[0x100] = 12, 0xff
    cpu.r[11], cpu.r[4:6] = 0xc0, [0x80, 0]
    cpu.r[12:16] = [0xa5, 0xb6, 0x88, 0]
    cpu.r[6:8] = [0xc7, 0xd8]
    return cpu


def expiry(art, pid, address, tail, width, rate, entry, jitter=None):
    wire = packet_wave(h.token(pid, address=address), tail, width, rate, jitter)
    cpu = cpu_for(art, wire, pid, address, entry)
    decision, route = None, None
    for _ in range(14_000):
        if cpu.pc == 0xfffe:
            break
        if cpu.pc == cpu.labels['usb_rx_handle_setup_or_out']:
            route = cpu.r[22]
        final = cpu.pc == cpu.labels['usb_rx_data_timeout_check']
        samples = len(cpu.io.samples)
        cpu.step()
        if final and len(cpu.io.samples) > samples:
            decision = cpu.io.samples[-1][0] - wire.boundaries[-2]
    else:
        raise AssertionError('Quiet token receiver did not return')
    return dict(decision=decision, token=cpu.m[0x114], route=route)


def paired(art, pid, address, tail, width, rate, entry, gap, jitter=None,
           payload=SETUPS[0]):
    token = packet_wave(h.token(pid, address=address), tail, width, rate, jitter)
    packet = h.data_packet(payload, 0xc3) if pid == 0x2d else h.data_packet(b'', 0x4b)
    sop = token.boundaries[-2] + gap * (16_000_000 / rate)
    start = sop - (jitter(0, h.K) if jitter else 0)
    data = packet_wave(packet, 0, width, rate, jitter, start)
    assert abs(data.start - sop) < 1e-8
    cpu = cpu_for(art, Joined(token, data), pid, address, entry)
    old_shadow = (cpu.r[12:16] + cpu.r[6:8])[:]
    rx_entry, handshakes = None, []

    def run():
        nonlocal rx_entry
        for _ in range(18_000):
            if cpu.pc == 0xfffe:
                return
            if (cpu.pc == cpu.labels['usb_rx_wait_for_j'] and cpu.t >= sop
                    and cpu.m[0x114] == pid and rx_entry is None):
                rx_entry = cpu.t - sop - 1
            if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
                handshakes.append((cpu.r[19], cpu.r[20]))
            cpu.step()
        raise AssertionError('Paired token/DATA receiver did not return')

    run()
    if cpu.r[3] != 11 and not (pid == 0xe1 and cpu.m[0x10f] == 0x5a):
        # Reenter from the foreground on the same MCU clock phase after
        # timeout. Advancing time cannot revive the expired token.
        phase = entry % 1
        cpu.t = phase + math.ceil(max(cpu.t, sop + 8) - phase)
        cpu.calls.append(0xfffe)
        cpu.pc = cpu.labels['USB_handler']
        run()
    accepted = cpu.r[3] == 11 if pid == 0x2d else cpu.m[0x10f] == 0x5a
    if accepted:
        assert handshakes == [(2, 0xd2)], ('Not exactly one ACK', handshakes)
        assert cpu.m[0x114] == 0, 'Completed DATA left token authorization'
        if pid == 0x2d:
            expected = list(payload[2:6] + payload[6:8])
            assert cpu.r[12:16] + cpu.r[6:8] == expected, (
                'Corrupt SETUP shadow', expected, cpu.r[12:16] + cpu.r[6:8])
            assert bytes(cpu.m[0x116:0x121]) == packet, (
                'Corrupt received SETUP bytes', bytes(cpu.m[0x116:0x121]).hex(), packet.hex())
            assert cpu.r[3] == 11
        else:
            assert cpu.word(4) == 0x88 and cpu.m[0x100] & 0x80, (
                'OUT status did not commit exact READ8 cursor')
            assert bytes(cpu.m[0x116:0x119]) == packet, 'Corrupt received OUT-status bytes'
    else:
        assert not handshakes and cpu.r[3] != 11, 'Rejected DATA caused an ACK/SETUP side effect'
        assert cpu.r[12:16] + cpu.r[6:8] == old_shadow, (
            'Rejected DATA changed accepted request shadow')
        assert cpu.word(4) == 0x80 and cpu.m[0x10f] == 12, (
            'Rejected DATA retired a pending read')
        assert cpu.m[0x114] == 0, 'Expired DATA retained token authorization'
    return dict(accepted=accepted, entry=rx_entry, token=cpu.m[0x114],
                setup_pending=cpu.r[3] == 11)


def check(art):
    """Run 108 quiet and 540 paired cases against these exact linked bytes."""
    quiet, errors, routes = [], [], {}
    pairs = 0
    for pid, address, tail, width, entry in SEEDS:
        assert tail in legal_tails(h.token(pid, address=address))
        for rate in (1_499_250, 1_500_000, 1_500_750):
            period = 16_000_000 / rate
            for sign in (-1, 0, 1):
                jitter = skew(sign)
                case = pid, address, tail, width, rate, entry, sign
                row = expiry(art, pid, address, tail, width, rate, entry, jitter)
                quiet.append(row['decision'])
                if (row['decision'] is None
                        or not 16 * period <= row['decision'] < 18 * period
                        or row['token']):
                    errors.append(('quiet', case, row))
                route = routes.setdefault(str(row['route']), dict(decisions=[], cases=0))
                route['decisions'].append(row['decision'])
                route['cases'] += 1
                for payload in SETUPS if pid == 0x2d else (SETUPS[0],):
                    for gap in (2, 16, 18):
                        pairs += 1
                        try:
                            result = paired(art, pid, address, tail, width, rate,
                                            entry, gap, jitter, payload)
                        except AssertionError as error:
                            errors.append(('packet/state', case, gap, payload.hex(), str(error)))
                            continue
                        if result['accepted'] != (gap <= 16):
                            errors.append(('admission', case, gap, result))
    for route in routes.values():
        values = [value for value in route.pop('decisions') if value is not None]
        route['decision_range'] = [min(values), max(values)] if values else None
    values = [value for value in quiet if value is not None]
    report = dict(bytes=art['size'], sha256=art['sha256'], quiet=len(quiet), paired=pairs,
                  decision_range=[min(values), max(values)] if values else None,
                  routes=routes, failures=len(errors), errors=errors)
    assert len(quiet) == 108 and pairs == 540, report
    assert not errors, report
    return report


def test():
    report = check(h.build())
    print('PASS directed dribble deadlines:', report['quiet'], 'quiet,',
          report['paired'], 'paired;', report['bytes'], 'bytes;',
          'decision clocks', report['decision_range'])


if __name__ == '__main__':
    test()
