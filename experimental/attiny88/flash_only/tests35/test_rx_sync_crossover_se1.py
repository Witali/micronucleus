"""Acquire SYNC despite certified legal transient SE1 observations.

USB 2.0 sections 7.1.2.1 and 7.1.4.1 permit monotonic matched low-speed
edges with 1.3..2.0 V differential crossover and 0.8..2.0 V single-ended
thresholds. The independent witnesses below produce 210 ns both-high
observations without changing the differential crossing or data cells.

This separate gate preserves the existing SE0 SYNC test and its exact
1080 injected + 54 pristine corpus. It calls the original receive oracle;
PID, payload, CRC positions, ownership, pin release and response timing
remain mandatory. Only incoming numeric DATA CRC16 storage is waived.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_legal import receive, RATES, ENTRIES
from tests35.test_rx_crossover_se1 import (
    WIDTH_CLOCKS,
    signal_witnesses as endpoint_signal_witnesses,
    threshold_time,
    voltage,
)
from tests35.test_usb_crossover import single_crossover


def centered_signal_witness():
    """Prove the centered 210 ns placement independently of the decoder.

    At a 1.3 V input threshold both pins are high from -105 to +105 ns.
    Each full-rail edge is strictly monotonic, both 10..90% times are
    300 ns, and the unique differential crossing is 2.0 V at time zero.
    """
    rise = [(-160, 0), (-150, .33), (-105, 1.3),
            (0, 2), (150, 2.97), (160, 3.3)]
    fall = [(-160, 3.3), (-150, 2.97), (0, 2),
            (105, 1.3), (150, .33), (160, 0)]
    assert all(ta < tb and va < vb
               for (ta, va), (tb, vb) in zip(rise, rise[1:]))
    assert all(ta < tb and va > vb
               for (ta, va), (tb, vb) in zip(fall, fall[1:]))
    assert rise[0][1] == fall[-1][1] == 0
    assert rise[-1][1] == fall[0][1] == 3.3
    assert rise[0][0] == fall[0][0] == -160
    assert rise[-1][0] == fall[-1][0] == 160
    up = threshold_time(rise, 2.97) - threshold_time(rise, .33)
    down = threshold_time(fall, .33) - threshold_time(fall, 2.97)
    assert up == down == 300
    assert voltage(rise, 0) == voltage(fall, 0) == 2
    # Strictly increasing minus strictly decreasing has one zero.
    assert voltage(rise, -150) - voltage(fall, -150) == -2.64
    assert voltage(rise, 150) - voltage(fall, 150) == 2.64
    begin = threshold_time(rise, 1.3)
    end = threshold_time(fall, 1.3)
    assert (begin, end) == (-105, 105)
    assert end - begin == 210
    probes = [index / 10 + .001 for index in range(-5000, 5001)]
    probes += [ns + delta for ns in (begin, end)
               for delta in (-1e-6, 1e-6)]
    for ns in probes:
        plus, minus = voltage(rise, ns), voltage(fall, ns)
        assert 0 <= plus <= 3.3 and 0 <= minus <= 3.3
        observed = (h.K if plus > 1.3 else 0) | (h.J if minus > 1.3 else 0)
        expected = h.J if ns < begin else h.J | h.K if ns < end else h.K
        assert observed == expected, (ns, observed, expected)
    return dict(rising_points_ns_v=rise, falling_points_ns_v=fall,
                threshold_v=1.3, crossing_v=2.0,
                high_interval_ns=[begin, end],
                line_10_to_90_ns=[up, down], differential_10_to_90_ns=300,
                full_transition_interval_ns=[-160, 160],
                differential_crossing_ns=0, fraction=.5)


def check(art):
    """Require complete SETUP DATA reception and one timely physical ACK."""
    witnesses = endpoint_signal_witnesses() + [centered_signal_witness()]
    bind(art)
    packet = h.data_packet(bytes([255]) * 8)
    failures = []
    outcomes = []
    responses = []
    certificates = []
    cases = 0
    controls = 0

    def record(wave, entry, **context):
        nonlocal cases, controls
        errors, response = receive(art, packet, wave, entry)
        row = dict(context, entry=entry, errors=errors, response=response)
        outcomes.append(row)
        if errors:
            failures.append(dict(row))
        if response is not None:
            responses.append(response)
        if context['kind'] == 'pristine':
            controls += 1
        else:
            cases += 1

    for rate in RATES:
        for sign in (-1, 0, 1):
            def pristine():
                return h.Wave(packet, rate=rate,
                              jitter=lambda index, line: sign * (.55 if line == h.J else -.55))
            certificates.append(dict(rate=rate, sign=sign,
                                     next_paired_ns=interval_errors(pristine())))
            indexes = [index for index in range(1, 8)
                       if pristine().levels[index] != pristine().levels[index - 1]]
            assert indexes == list(range(1, 7))
            for entry in ENTRIES:
                record(pristine(), entry, kind='pristine', rate=rate, sign=sign)
                for index in indexes:
                    for fraction in (1 / 21, .5, 20 / 21):
                        wave = single_crossover(pristine(), index, width=WIDTH_CLOCKS,
                                                fraction=fraction, observed=h.J | h.K)
                        record(wave, entry, kind='single', rate=rate, sign=sign,
                               index=index, fraction=fraction)
                for fraction in (1 / 21, 20 / 21):
                    wave = pristine()
                    for index in reversed(indexes):
                        single_crossover(wave, index, width=WIDTH_CLOCKS,
                                         fraction=fraction, observed=h.J | h.K)
                    record(wave, entry, kind='all_sync_transitions', rate=rate,
                           sign=sign, fraction=fraction, transitions=len(indexes))
    assert cases == 972 + 108 and controls == 54
    assert len(outcomes) == cases + controls
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                single_cases=972, repeated_cases=108, control_cases=controls,
                total_cases=len(outcomes), crossover_ns=210, observed=h.J | h.K,
                placement_fractions=[1 / 21, .5, 20 / 21],
                signal_witnesses=witnesses, certificates=certificates,
                failures=failures, outcomes=outcomes,
                observation_fields=['errors', 'response'],
                response_range=[min(responses), max(responses)] if responses else None)


def test():
    """Write a separately named report and fail on every mandatory mismatch."""
    import json
    report = check(h.build())
    output = h.ROOT / 'build' / ('sync-se1-crossover-' + report['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('SE1 SYNC 210 ns crossover:', report['cases'], 'injected cases;',
          report['control_cases'], 'controls;', len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
