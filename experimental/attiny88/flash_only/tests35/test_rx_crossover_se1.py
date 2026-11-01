"""Receive legal transient SE1 at asymmetric low-speed crossovers.

USB2 sections 7.1.2.1 and 7.1.4.1 allow monotonic matched low-speed edges,
a differential crossover of 1.3..2.0 V, and single-ended thresholds of
0.8..2.0 V. Complementing the established 2 V / Vcross 1.3 V SE0 witness
about 3.3 V and exchanging pin roles gives a 1.3 V / Vcross 2.0 V witness:

  rising: (-70 ns,0 V), (-60,.33), (-10,1.3), (0,2), (240,2.97), (250,3.3)
  falling: (-70 ns,3.3 V), (-60,2.97), (0,2), (200,1.3), (240,.33), (250,0)

Both full-rail transitions are monotonic, with exactly matched 300 ns
10..90% times. The differential 10..90% time is also 300 ns. Both digital
pins are high from -10 to +200 ns at the permitted 1.3 V threshold, while
the differential crossing stays at t=0. Time reversal plus exchanging pin
roles gives the second placement, from -200 to +10 ns.

This is a derived legal electrical witness, not permission for sustained
SE1. Existing malformed-packet and sustained-SE1 rejection tests remain
unchanged. Only numeric incoming DATA CRC16 values/storage are waived;
PID, payload, both CRC positions, framing, ownership and timing are strict.
"""
from bisect import bisect_right

from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_legal import receive, RATES, ENTRIES
from tests35.test_usb_crossover import single_crossover


FRACTIONS = (1 / 21, 20 / 21)
THRESHOLD_V = 1.3
CROSSOVER_V = 2.0
WIDTH_NS = 210
WIDTH_CLOCKS = WIDTH_NS * 16_000_000 / 1_000_000_000


def threshold_time(points, threshold):
    """Solve a threshold crossing on one strictly monotonic full-rail edge."""
    for (ta, va), (tb, vb) in zip(points, points[1:]):
        if min(va, vb) <= threshold <= max(va, vb):
            return ta + (threshold - va) * (tb - ta) / (vb - va)
    raise AssertionError(('threshold outside witness', threshold))


def voltage(points, ns):
    """Interpolate the certified segments and hold the two supply rails."""
    if ns <= points[0][0]:
        return points[0][1]
    if ns >= points[-1][0]:
        return points[-1][1]
    index = bisect_right([point[0] for point in points], ns) - 1
    (ta, va), (tb, vb) = points[index:index + 2]
    return va + (vb - va) * (ns - ta) / (tb - ta)


def signal_witnesses():
    """Numerically certify both placements independently of the decoder."""
    low_rise = [(-70, 0), (-60, .33), (0, 1.3), (200, 2),
                (240, 2.97), (250, 3.3)]
    low_fall = [(-70, 3.3), (-60, 2.97), (-10, 2), (0, 1.3),
                (240, .33), (250, 0)]
    rise = [(time, round(3.3 - value, 12)) for time, value in low_fall]
    fall = [(time, round(3.3 - value, 12)) for time, value in low_rise]
    mirrored_rise = [(-time, value) for time, value in reversed(fall)]
    mirrored_fall = [(-time, value) for time, value in reversed(rise)]
    certificates = []
    for rising, falling, fraction in ((rise, fall, FRACTIONS[0]),
                                     (mirrored_rise, mirrored_fall, FRACTIONS[1])):
        assert all(ta < tb and va < vb
                   for (ta, va), (tb, vb) in zip(rising, rising[1:]))
        assert all(ta < tb and va > vb
                   for (ta, va), (tb, vb) in zip(falling, falling[1:]))
        assert rising[0][1] == falling[-1][1] == 0
        assert rising[-1][1] == falling[0][1] == 3.3
        assert rising[0][0] == falling[0][0]
        assert rising[-1][0] == falling[-1][0]
        up = threshold_time(rising, 2.97) - threshold_time(rising, .33)
        down = threshold_time(falling, .33) - threshold_time(falling, 2.97)
        assert up == down == 300 and 75 <= up <= 300
        # Strictly increasing minus strictly decreasing has one zero.
        assert (0, CROSSOVER_V) in rising and (0, CROSSOVER_V) in falling
        begin = threshold_time(rising, .33)
        end = threshold_time(rising, 2.97)
        assert begin == threshold_time(falling, 2.97)
        assert end == threshold_time(falling, .33)
        assert abs(voltage(rising, begin) - voltage(falling, begin) + 2.64) < 1e-12
        assert abs(voltage(rising, end) - voltage(falling, end) - 2.64) < 1e-12
        assert end - begin == 300
        high_begin = threshold_time(rising, THRESHOLD_V)
        high_end = threshold_time(falling, THRESHOLD_V)
        assert high_end - high_begin == WIDTH_NS
        assert abs(-high_begin / WIDTH_NS - fraction) < 1e-12
        # The offset avoids equality at either switching threshold. Include
        # the full transition, both settled rails and both pulse boundaries.
        probes = [index / 10 + .001 for index in range(-5000, 5001)]
        probes += [time + delta for time in (high_begin, high_end)
                   for delta in (-1e-6, 1e-6)]
        for ns in probes:
            plus = voltage(rising, ns)
            minus = voltage(falling, ns)
            assert 0 <= plus <= 3.3 and 0 <= minus <= 3.3
            observed = (h.K if plus > THRESHOLD_V else 0) | (h.J if minus > THRESHOLD_V else 0)
            expected = h.J if ns < high_begin else (h.J | h.K) if ns < high_end else h.K
            assert observed == expected, (ns, observed, expected)
        certificates.append(dict(rising_points_ns_v=rising,
                                 falling_points_ns_v=falling,
                                 threshold_v=THRESHOLD_V,
                                 high_interval_ns=[high_begin, high_end],
                                 line_10_to_90_ns=[up, down],
                                 differential_10_to_90_ns=300,
                                 full_transition_interval_ns=[rising[0][0], rising[-1][0]],
                                 differential_crossing_ns=0,
                                 crossing_v=CROSSOVER_V))
    return certificates


def check(art):
    witnesses = signal_witnesses()
    bind(art)
    packet = h.data_packet(bytes([255]) * 8)
    failures = []
    responses = []
    jitter_certificates = []
    counts = dict(single=0, all_transitions=0, directed=0, pristine=0)

    def record(data, incoming, entry, **context):
        errors, response = receive(art, data, incoming, entry)
        if errors:
            failures.append(dict(context, packet=data.hex(), entry=entry,
                                 errors=errors))
        if response is not None:
            responses.append(response)
        counts[context['kind']] += 1

    for rate in RATES:
        for sign in (-1, 0, 1):
            def pristine():
                return h.Wave(packet, rate=rate,
                              jitter=lambda index, line: sign * (.55 if line == h.J else -.55))
            jitter_certificates.append(dict(rate=rate, sign=sign,
                                            next_paired_ns=interval_errors(pristine())))
            wave = pristine()
            indexes = [index for index in range(8, len(wave.bits))
                       if wave.levels[index] != wave.levels[index - 1]]
            assert len(indexes) == 22
            for index in indexes:
                for fraction in FRACTIONS:
                    for entry in ENTRIES:
                        incoming = single_crossover(pristine(), index,
                                                    width=WIDTH_CLOCKS,
                                                    fraction=fraction, observed=h.J | h.K)
                        record(packet, incoming, entry, kind='single',
                               rate=rate, sign=sign, index=index, fraction=fraction)
            for fraction in FRACTIONS:
                for entry in ENTRIES:
                    incoming = pristine()
                    for index in reversed(indexes):
                        single_crossover(incoming, index, width=WIDTH_CLOCKS,
                                         fraction=fraction, observed=h.J | h.K)
                    record(packet, incoming, entry, kind='all_transitions',
                           rate=rate, sign=sign, fraction=fraction,
                           transitions=len(indexes))

    # This payload case exposes corruption outside numeric CRC storage:
    # the OR-only prototype changed a payload byte from 0x15 to 0x11.
    directed = h.data_packet(bytes([0x15]) * 8)
    assert directed.hex() == 'c31515151515151515ef97'
    control = h.Wave(directed, rate=1_499_250)
    assert control.levels[57] != control.levels[56]
    record(directed, control, 8, kind='pristine', rate=1_499_250, sign=0)
    incoming = single_crossover(h.Wave(directed, rate=1_499_250), 57,
                                width=WIDTH_CLOCKS, fraction=FRACTIONS[0],
                                observed=h.J | h.K)
    record(directed, incoming, 8, kind='directed', rate=1_499_250, sign=0,
           index=57, fraction=FRACTIONS[0])
    assert counts == dict(single=2376, all_transitions=108,
                          directed=1, pristine=1), counts
    failure_counts = {kind: sum(row['kind'] == kind for row in failures)
                      for kind in counts}
    return dict(bytes=art['size'], sha256=art['sha256'], cases=sum(counts.values()),
                counts=counts, failure_counts=failure_counts,
                crossover_ns=WIDTH_NS, observed=h.J | h.K,
                placement_fractions=list(FRACTIONS), threshold_v=THRESHOLD_V,
                differential_crossover_v=CROSSOVER_V,
                signal_witnesses=witnesses, certificates=jitter_certificates,
                failures=failures,
                response_range=[min(responses), max(responses)] if responses else None)


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('se1-crossover-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Legal transient SE1 crossover:', report['cases'], 'cases;',
          len(report['failures']), 'failures;', report['response_range'], flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
