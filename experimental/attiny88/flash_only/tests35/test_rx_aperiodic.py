"""Finite ordinary DATA packets with independently certified edge jitter.

The rounded SYNC/data correlations retain both a rejected optimization's
regressions and inherited receiver weaknesses. They are valid packets which
must decode and receive ACK; an existing failure never changes that oracle.
USB 2.0 Table 7-10 limits next/paired transition errors to 75/45 ns. Frequency
error consumes this same budget. These digital cases are not full USB proof.
"""
from copy import copy
import json

from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import complete_frame_entries, eop_wave
from tests35.rx_jitter_patterns import differential_edges, interval_errors

# These are phase offsets in AVR clocks at actual differential transitions,
# rather than extra bits or a change to packet contents. Continue the first
# two prefixes by alternating +/-0.6 clock, subject to the interval budget.
SEARCH_PREFIX = (0, .6, .6, .6, .13, .07, -.6, .578)
EOP_PREFIX = (0, .6, .475, .6, -.255, .6, -.6, .578)
FRAMING_OFFSETS = EOP_PREFIX + (
    -.123, -.141, -.167, -.335, .061, -.029, .027, .334, .094, .364,
    .470, .105, -.148, -.120, .411, .313, -.332, -.358, -.406, -.467, -.065)

# Names describe the observed failure during discovery, not an expected result.
# Both search families passed the previous receiver and exposed its proposed
# SYNC change. The other families exposed inherited EOP/framing failures.
FAMILIES = (
    ('search_36', 0x9f, SEARCH_PREFIX, 36),
    ('search_38', 0x9f, SEARCH_PREFIX, 38),
    ('eop_35', 0x9f, EOP_PREFIX, 35),
    ('eop_37', 0x9f, EOP_PREFIX, 37),
    ('framing_35', 0xff, FRAMING_OFFSETS, 35),
    ('framing_37', 0xff, FRAMING_OFFSETS, 37),
)


def edge_wave(packet, targets, rate, width):
    """Build a fixed aperiodic pattern and prove its whole-wave legality.

    Clip each target against both previous actual transitions. This adapts
    the same rounded pattern to the host-rate extrema without stacking full
    jitter on top of frequency error. The independent interval oracle below
    recomputes legality from the final physical transition times.
    """
    base = eop_wave(packet, width, rate)
    edges = differential_edges(base)
    assert [index for index, _ in edges[:8]] == [0, 1, 2, 3, 4, 5, 6, 10]
    offsets = []
    for i, (bit, _) in enumerate(edges):
        lower, upper = -.6, .6
        for distance, limit in ((1, 1.2), (2, .72)):
            if i >= distance:
                frequency = (bit - edges[i-distance][0]) * (base.period - 32/3)
                lower = max(lower, offsets[i-distance] - limit - frequency)
                upper = min(upper, offsets[i-distance] + limit - frequency)
        assert lower <= upper + 1e-8, ('no legal jitter target', i, lower, upper)
        target = targets[i] if i < len(targets) else (-.6 if i % 2 else .6)
        offsets.append(min(upper, max(lower, target)))
    assert offsets[0] == 0
    phase_at = {edge[0]: delta for edge, delta in zip(edges, offsets)}
    wave = copy(base)
    wave.boundaries = []
    current = 0
    for i, when in enumerate(base.boundaries):
        if i in phase_at:
            current = phase_at[i]
        wave.boundaries.append(when + current)
    wave.start, wave.end = wave.boundaries[0], wave.boundaries[-1]
    wave.pin_edges = []
    previous = h.J
    for when, level in zip(wave.boundaries, wave.levels):
        if (previous ^ level) & 4:
            wave.pin_edges.append(when)
        previous = level
    assert all(a < b for a, b in zip(wave.boundaries, wave.boundaries[1:]))
    certificate = interval_errors(wave)
    return wave, certificate


def receive(art, packet, payload, incoming, entry):
    cpu = h.CPU(art, incoming, entry)
    cpu.r[24:26] = [0xa5, 0xb6]
    cpu.m[0x10f] = 0x5a
    cpu.m[0x114] = 0x2d  # A valid SETUP token already authorizes this DATA0.
    targets = complete_frame_entries(art)
    frames, handshakes, eof = [], [], []
    returned = False
    for _ in range(16_000):
        if cpu.pc == 0xfffe:
            returned = True
            break
        if cpu.pc in targets:
            frames.append(dict(time=cpu.t, count=cpu.r[23],
                               rx=bytes(cpu.m[0x116:0x116+len(packet)]).hex()))
        if cpu.pc == cpu.labels['usb_rx_end_packet']:
            eof.append(dict(time=cpu.t, raw_count=cpu.word(28)-0x116,
                            count=cpu.r[23]))
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            handshakes.append((cpu.r[19], cpu.r[20]))
        cpu.step()
    meaningful = packet[:-2]
    # Only numeric DATA CRC16 validation/storage is waived. Require PID,
    # every payload byte and the count including both CRC-byte positions.
    decoded = any(row['count'] == len(packet)
                  and bytes.fromhex(row['rx'])[:-2] == meaningful for row in frames)
    first_k = next((when for when, io, value in cpu.bus_events
                    if io == 11 and value & 6 == h.K), None)
    response = None if first_k is None else first_k - incoming.boundaries[-2]
    first_se0 = next((sample for sample in cpu.io.samples if sample[2] == 0), None)
    problems = []
    if not returned:
        problems.append('handler did not return')
    if not decoded:
        problems.append('PID/payload/count not framed')
    if handshakes != [(2, 0xd2)]:
        problems.append('expected exactly one ACK')
    if (cpu.r[3] != 11 or cpu.r[12:16] + cpu.r[6:8] != list(payload[2:])
            or cpu.m[0x10f] != 0x5a or cpu.m[0x114] != 0 or cpu.r[2] != 0):
        problems.append('accepted SETUP state/shadow mismatch')
    if (response is None
            or not 2*(85/8) <= response <= 6.5*min(85/8, incoming.period)):
        problems.append('response outside recovery-J deadline')
    if cpu.r[24:26] != [0xa5, 0xb6] or cpu.raw_stack:
        problems.append('caller registers/stack not restored')
    if cpu.io.get(10, 0) & 6:
        problems.append('USB pins still driven after return')
    return dict(problems=problems, decoded=decoded, frames=frames, eof=eof,
                handshakes=handshakes, response=response, first_response_k=first_k,
                physical_se0=incoming.boundaries[-3], recovery_j=incoming.boundaries[-2],
                first_se0_pin=first_se0, final_rx=bytes(cpu.m[0x116:0x121]).hex(),
                command=cpu.r[3], shadow=cpu.r[12:16]+cpu.r[6:8],
                tx_length=cpu.m[0x10f], token=cpu.m[0x114], returned=returned)


def check(art):
    bind(art)
    rows, errors = [], []
    groups = {name: dict(cases=0, failures=0) for name, *_ in FAMILIES}
    for name, value, targets, integer_entry in FAMILIES:
        payload = bytes([value]) * 8
        packet = h.data_packet(payload, 0xc3)
        for rate in (1_499_250, 1_500_000, 1_500_750):
            for width in (10.72, 24):
                incoming, certificate = edge_wave(packet, targets, rate, width)
                for fraction in (.94, .95, .96, .97, .98):
                    entry = integer_entry + fraction
                    result = receive(art, packet, payload, incoming, entry)
                    row = dict(family=name, packet=packet.hex(), rate=rate,
                               eop_width=width, entry=entry, certificate=certificate,
                               **result)
                    rows.append(row)
                    groups[name]['cases'] += 1
                    if result['problems']:
                        groups[name]['failures'] += 1
                        errors.append(dict(family=name, rate=rate, eop_width=width,
                                           entry=entry, problems=result['problems'],
                                           response=result['response'],
                                           final_rx=result['final_rx']))
    assert len(rows) == 180
    return dict(bytes=art['size'], sha256=art['sha256'], cases=len(rows),
                groups=groups, errors=errors, rows=rows)


def test():
    report = check(h.build())
    destination = h.ROOT / 'build' / ('aperiodic-rx-' + report['sha256'][:16] + '.json')
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print('Aperiodic receiver:', report['cases'], 'certified cases;',
          len(report['errors']), 'failures;', report['bytes'], 'bytes')
    assert not report['errors'], ('aperiodic RX failures', len(report['errors']),
                                  report['errors'][:4])


if __name__ == '__main__':
    test()
