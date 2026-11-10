"""Receive a source-valid EOP whose single-ended PIN interval exceeds1.50us.

USB2.0 sections7.1.2.1,7.1.4 and7.1.13.2.1, Table7-10 and Figure7-50
(CrossoverPointExtended) distinguish source timing at differential Vcross
from receiver input thresholds. No upstream hub-skew budget is used here.
The explicit monotonic300ns curves are a model-input certificate, not board
or complete electrical certification. Firmware, CPU and timing oracles are
unchanged; the approved exception remains numeric incoming DATA CRC16 only.
"""
import json
import math

from tests35 import ep0_model as h
from tests35.address_state import active_crc, seed_active
from tests35.ep0_cases import bind
from tests35.phy_model import complete_frame_entries
from tests35.test_rx_eop_matrix import ENTRIES, tails, wire

CPU_HZ = 16_000_000
CLOCK_NS = 1_000_000_000 / CPU_HZ
RATE = 1_500_000
VCROSS = 1.3
PIN_THRESHOLD = 2.0
SOURCE_WIDTHS = (20.64, 24)
TAIL = 6

# DATA edges cross at1.3V while retaining matched300ns line/differential
# 10..90 timing. Their narrow PIN-low intervals are included even at SOP.
DATA_RISE = ((-160, 0), (-150, .33), (-1, 1.2), (0, 1.3),
             (1, 2.2), (150, 2.97), (160, 3.3))
DATA_FALL = ((-160, 3.3), (-150, 2.97), (-1, 2.2), (0, 1.3),
             (1, 1.2), (150, .33), (160, 0))
EOP_RISE = ((-70, 0), (-60, .33), (0, 1.3), (200, 2),
            (240, 2.97), (250, 3.3))
EOP_FALL = ((-70, 3.3), (-60, 2.97), (-10, 2), (0, 1.3),
            (240, .33), (250, 0))


def crossing(points, value):
    """Interpolate one independent, monotonic voltage crossing."""
    for (ta, va), (tb, vb) in zip(points, points[1:]):
        if min(va, vb) <= value <= max(va, vb):
            return ta + (value - va) * (tb - ta) / (vb - va)
    raise AssertionError(('threshold outside waveform', value))


def voltage(points, when):
    for (ta, va), (tb, vb) in zip(points, points[1:]):
        if ta <= when <= tb:
            return va + (vb - va) * (when - ta) / (tb - ta)
    raise AssertionError(('time outside waveform', when))


def signal_certificate():
    """Check source slew, matching, Vcross and the separate PIN thresholds."""
    durations = {}
    for name, points, ascending in (('data_rise', DATA_RISE, True),
                                    ('data_fall', DATA_FALL, False),
                                    ('eop_rise', EOP_RISE, True),
                                    ('eop_fall', EOP_FALL, False)):
        assert all(tb > ta and ((vb > va) == ascending)
                   for (ta, va), (tb, vb) in zip(points, points[1:]))
        assert min(v for _, v in points) == 0 and max(v for _, v in points) == 3.3
        duration = abs(crossing(points, 2.97) - crossing(points, .33))
        assert 75 <= duration <= 300
        assert crossing(points, VCROSS) == 0
        durations[name] = duration
    assert durations['data_rise'] == durations['data_fall'] == 300
    assert durations['eop_rise'] == durations['eop_fall'] == 300

    knots = sorted({t for t, _ in DATA_RISE} | {t for t, _ in DATA_FALL})
    differential = [(t, voltage(DATA_RISE, t) - voltage(DATA_FALL, t)) for t in knots]
    assert all(a[1] < b[1] for a, b in zip(differential, differential[1:]))
    assert crossing(differential, 0) == 0
    assert voltage(DATA_RISE, 0) == voltage(DATA_FALL, 0) == VCROSS
    differential_duration = crossing(differential, 2.64) - crossing(differential, -2.64)
    assert differential_duration == 300

    low_start = crossing(DATA_FALL, PIN_THRESHOLD)
    low_end = crossing(DATA_RISE, PIN_THRESHOLD)
    assert 0 < low_end - low_start <= 210
    lead = crossing(EOP_FALL, PIN_THRESHOLD)
    trail = crossing(EOP_RISE, PIN_THRESHOLD)
    assert lead == -10 and trail == 200
    return dict(source_vcross_v=VCROSS, pin_threshold_v=PIN_THRESHOLD,
                line_10_to_90_ns=durations, matched_rise_fall_error_percent=0,
                differential_10_to_90_ns=differential_duration,
                data_pin_low_interval_ns=[low_start, low_end],
                eop_pin_lead_trail_ns=[lead, trail],
                pin_width_at_source_1500ns_clocks=24 + (trail - lead) / CLOCK_NS,
                curves=dict(data_rise=DATA_RISE, data_fall=DATA_FALL,
                            eop_rise=EOP_RISE, eop_fall=EOP_FALL),
                reference='USB2.0 7.1.2.1/7.1.4/7.1.13.2.1, Table7-10, Figure7-50')


def threshold_wire(packet, source_width, certificate):
    """Map a differential source waveform into independently derived PIN levels."""
    assert TAIL in tails(packet)
    source = wire(packet, TAIL, RATE, source_width, 0)
    source_eop, source_j = source.boundaries[-3:-1]
    assert 1250 <= source_width * CLOCK_NS <= 1500
    low_start, low_end = certificate['data_pin_low_interval_ns']
    lead, trail = certificate['eop_pin_lead_trail_ns']
    rows = []
    previous = h.J
    for when, level, label in zip(source.boundaries[:-3], source.levels[:-3], source.labels[:-3]):
        if level != previous:
            # Every real transition, including SOP, has its own derived
            # threshold excursion; ideal DATA pins are not assumed.
            rows.extend(((when + low_start / CLOCK_NS, 0, ('crossover', label)),
                         (when + low_end / CLOCK_NS, level, label)))
        else:
            rows.append((when, level, label))
        previous = level
    rows.extend(((source_eop + lead / CLOCK_NS, 0, 'SE0'),
                 (source_j + trail / CLOCK_NS, h.J, 'EOP_J'),
                 (source_j + trail / CLOCK_NS + source.period, h.J, 'idle')))
    source.boundaries = [t for t, _, _ in rows]
    source.levels = [v for _, v, _ in rows]
    source.labels = [label for _, _, label in rows]
    assert all(a < b for a, b in zip(source.boundaries, source.boundaries[1:]))
    source.end = source.boundaries[-1]
    source.pin_edges = []
    previous = h.J
    for when, level in zip(source.boundaries, source.levels):
        if (previous ^ level) & 4:
            source.pin_edges.append(when)
        previous = level
    expected_width = source_width + (trail - lead) / CLOCK_NS
    assert math.isclose(source.boundaries[-2] - source.boundaries[-3], expected_width,
                        rel_tol=0, abs_tol=1e-10)
    return source, dict(differential_se0=[source_eop, source_j],
                        pin_se0=source.boundaries[-3:-1],
                        pin_width=expected_width, source_width=source_width)


def receive(art, packet, incoming, entry, source):
    """Keep existing full-frame, transaction ownership and physical response checks."""
    cpu = h.CPU(art, incoming, entry)
    is_in = packet[0] == 0x69
    cpu.r[0] = 0xa7
    cpu.r[2:4] = [0, 0]
    cpu.r[4:6] = [0x80, 0]
    cpu.r[6:8] = [0x33, 0x44]
    cpu.r[11] = 0xc0
    cpu.r[12:16] = [0x11, 0x22, 0x88, 0]
    cpu.r[24:28] = [0xa5, 0xb6, 0x62, 0x19]
    cpu.m[0x100] = 7
    # Keep a recognizable cached packet. OUT status must retire a real
    # outstanding reply even if its IN ACK was lost; IN here should NAK.
    cpu.m[0x101:0x10c] = bytes([0x4b] + [(i * 37 + 11) & 255 for i in range(10)])
    cpu.m[0x10f] = 0x5a if is_in else 12
    cpu.m[0x114] = 0 if is_in else 0xe1
    seed_active(cpu, 0, h.token(0x69)[2])
    protected = cpu.r[6:16].copy()
    address_crc = active_crc(cpu)
    cached = bytes(cpu.m[0x101:0x10c])
    frames = complete_frame_entries(art)
    decoded = False
    handshakes = []
    first_live = None
    spm = False
    for _ in range(16000):
        if cpu.pc == 0xfffe:
            break
        if cpu.pc in frames:
            meaningful = len(packet) if is_in else len(packet) - 2
            decoded |= (cpu.r[23] == len(packet) and
                        bytes(cpu.m[0x116:0x116 + meaningful]) == packet[:meaningful])
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            handshakes.append((cpu.r[19], cpu.r[20]))
        watch = first_live is None and cpu.pc == cpu.labels.get('usb_rx_wait_eop_j')
        samples = len(cpu.io.samples)
        before = cpu.t
        saved = cpu.r[21] if watch else None
        ins = cpu.step()
        spm |= ins.op == 'spm'
        if watch and len(cpu.io.samples) > samples:
            observation = cpu.io.samples[-1]
            first_live = dict(cpu_time=before, pin_time=observation[0],
                              value=observation[2] & 6, saved_j=saved)
    else:
        raise AssertionError('Threshold-EOP handler did not return')

    first_k = next((t for t, io, value in cpu.bus_events
                    if io == 11 and value & 6 == h.K), None)
    pin_response = None if first_k is None else first_k - incoming.boundaries[-2]
    response = None if first_k is None else first_k - source['differential_se0'][1]
    errors = []
    if not decoded:
        errors.append('complete PID/payload/CRC-position count not received')
    expected_pid = 0x5a if is_in else 0xd2
    if handshakes != [(2, expected_pid)]:
        errors.append(('expected exactly one response', expected_pid, handshakes))
    if response is None or not 2 * (85 / 8) <= response <= 6.5 * min(85 / 8, incoming.period):
        errors.append(('physical response outside differential-recovery-J deadline', response))
    if (cpu.r[0] != 0xa7 or cpu.r[1] or cpu.r[21] != 0xa0
            or cpu.r[24:28] != [0xa5, 0xb6, 0x62, 0x19]
            or cpu.raw_stack or cpu.word(28) != 0x100 or cpu.word(30) != 0x100):
        errors.append('caller/zero register/stack/context restoration')
    if (cpu.r[6:16] != protected or active_crc(cpu) != address_crc or cpu.r[2:4] != [0, 0]
            or bytes(cpu.m[0x101:0x10c]) != cached or cpu.m[0x114] != 0 or spm):
        errors.append('address/shadow/cache/token/NVM ownership')
    # These are the same NAK/read-status lifetime rules checked by
    # test_ep0_status and test_dribble_deadlines, now with thresholded EOP.
    if is_in:
        if cpu.word(4) != 0x80 or cpu.m[0x10f] != 0x5a or cpu.m[0x100] != 7:
            errors.append('NAK advanced or retired the pending control read')
    elif cpu.word(4) != 0x88 or cpu.m[0x10f] != 0x5a or not cpu.m[0x100] & 0x80:
        errors.append('OUT status failed exact READ8 cursor/completion retirement')
    if cpu.io.get(10, 0) & 6:
        errors.append('USB pins not released')
    if any(t < source['differential_se0'][1] and io == 10 and value & 6
           for t, io, value in cpu.bus_events):
        errors.append('USB driven before source recovery J')
    return dict(decoded=decoded, response=response, response_from_pin_j=pin_response,
                first_live=first_live, errors=errors)


def check(art):
    bind(art)
    certificate = signal_certificate()
    rows = []
    failures = []
    responses = []
    for pid in (0x69, 0x4b):
        packet = h.token(pid) if pid == 0x69 else h.data_packet(b'', pid)
        for width in SOURCE_WIDTHS:
            for entry in ENTRIES:
                incoming, source = threshold_wire(packet, width, certificate)
                row = dict(packet=packet.hex(), tail=TAIL, rate=RATE, entry=entry, **source,
                           **receive(art, packet, incoming, entry, source))
                rows.append(row)
                if row['errors']:
                    failures.append(row)
                if row['response'] is not None:
                    responses.append(row['response'])
    assert len(rows) == 24
    return dict(bytes=art['size'], sha256=art['sha256'], cases=len(rows),
                source_widths=list(SOURCE_WIDTHS),
                source_widths_ns=[width * CLOCK_NS for width in SOURCE_WIDTHS],
                pin_widths=[24, 27.36],
                certificate=certificate, failures=failures, rows=rows,
                response_reference='differential CrossoverPointExtended recovery J',
                response_range=[min(responses), max(responses)] if responses else None,
                first_live_se0=sum(bool(row['first_live'] and row['first_live']['value'] == 0)
                                   for row in rows))


def test():
    report = check(h.build())
    output = h.ROOT / 'build' / ('eop-thresholds-' + report['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Threshold-aware EOP:', report['cases'], 'cases;', len(report['failures']),
          'failures;', report['response_range'], flush=True)
    assert not report['failures'], report['failures'][:2]


if __name__ == '__main__':
    test()
