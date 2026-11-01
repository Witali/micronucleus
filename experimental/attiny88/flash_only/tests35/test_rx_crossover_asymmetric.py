"""Receive legal asymmetric 210 ns single-ended crossover observations.

USB2 7.1.2.1 permits monotonic, 75..300 ns, +/-20% matched LS edges and
Vcross=1.3..2.0 V. Equal instantaneous slew and constant common-mode voltage
are preferred, not required. At common 2 V pin thresholds this witness gives
SE0 from -10 to +200 ns about the unchanged differential crossing:

  rising: (-60 ns,.33 V), (0,1.3), (200,2.0), (240,2.97)
  falling: (-60 ns,2.97 V), (-10,2.0), (0,1.3), (240,.33)

Interpolate monotonically, adding 0/3.3 V rail endpoints at -70/+250 ns.
Both line 10..90 times are 300 ns, exactly matched; differential 10..90 also
takes 300 ns. The unique differential crossing remains t=0 at 1.3 V.
Reverse time and swap rising/falling roles for SE0 from -200 to +10 ns.
This preserves the differential-edge jitter certificate: 7.1.13.1.1 measures
jitter at the data-line crossover, not at either single-ended threshold.
7.1.4.1 requires the receiver to tolerate this <=210 ns observation.

This is a legal signal witness and emitted-instruction regression. It does
not certify an actual driver across all loads, an AVR threshold or a board.
Only numeric incoming DATA CRC16 values/storage remain waived.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_legal import receive, RATES, ENTRIES
from tests35.test_usb_crossover import single_crossover


FRACTIONS = (1/21, 20/21)


def threshold_time(points, threshold):
    """Solve a single monotonic voltage segment at the chosen threshold."""
    for (ta, va), (tb, vb) in zip(points, points[1:]):
        if min(va, vb) <= threshold <= max(va, vb):
            return ta + (threshold-va)*(tb-ta)/(vb-va)
    raise AssertionError(('threshold outside witness', threshold))


def signal_witnesses():
    """Certify both asymmetric placements independently of the GPIO decoder."""
    rise = [(-70, 0), (-60, .33), (0, 1.3), (200, 2), (240, 2.97), (250, 3.3)]
    fall = [(-70, 3.3), (-60, 2.97), (-10, 2), (0, 1.3), (240, .33), (250, 0)]
    mirrored_rise = [(-time, voltage) for time, voltage in reversed(fall)]
    mirrored_fall = [(-time, voltage) for time, voltage in reversed(rise)]
    certificates = []
    for rising, falling, fraction in ((rise, fall, FRACTIONS[0]),
                                     (mirrored_rise, mirrored_fall, FRACTIONS[1])):
        assert all(a[0] < b[0] and a[1] < b[1]
                   for a, b in zip(rising, rising[1:]))
        assert all(a[0] < b[0] and a[1] > b[1]
                   for a, b in zip(falling, falling[1:]))
        up = threshold_time(rising, 2.97)-threshold_time(rising, .33)
        down = threshold_time(falling, .33)-threshold_time(falling, 2.97)
        assert up == down == 300 and 75 <= up <= 300
        # Strictly rising minus strictly falling has one differential zero.
        assert (0, 1.3) in rising and (0, 1.3) in falling
        start = threshold_time(rising, .33)
        end = threshold_time(rising, 2.97)
        assert start == threshold_time(falling, 2.97)
        assert end == threshold_time(falling, .33)
        assert (start, .33) in rising and (start, 2.97) in falling
        assert (end, 2.97) in rising and (end, .33) in falling
        assert end-start == 300
        assert rising[0][0] == falling[0][0]
        assert rising[-1][0] == falling[-1][0]
        low_start = threshold_time(falling, 2)
        low_end = threshold_time(rising, 2)
        assert low_end-low_start == 210
        assert abs(-low_start/210-fraction) < 1e-12
        certificates.append(dict(rising_points_ns_v=rising, falling_points_ns_v=falling,
                                 threshold_v=2, low_interval_ns=[low_start, low_end],
                                 line_10_to_90_ns=[up, down], differential_10_to_90_ns=300,
                                 full_transition_interval_ns=[rising[0][0], rising[-1][0]],
                                 differential_crossing_ns=0, crossing_v=1.3))
    return certificates


def check(art):
    witnesses = signal_witnesses()
    bind(art)
    packet = h.data_packet(bytes([255])*8)
    failures = []
    responses = []
    certificates = []
    cases = 0

    def record(incoming, entry, **context):
        nonlocal cases
        errors, response = receive(art, packet, incoming, entry)
        if errors:
            failures.append(dict(context, entry=entry, errors=errors))
        if response is not None:
            responses.append(response)
        cases += 1

    for rate in RATES:
        for sign in (-1, 0, 1):
            def pristine():
                return h.Wave(packet, rate=rate,
                              jitter=lambda index, line: sign*(.55 if line == h.J else -.55))
            certificates.append(dict(rate=rate, sign=sign,
                                     next_paired_ns=interval_errors(pristine())))
            wave = pristine()
            indexes = [i for i in range(8, len(wave.bits))
                       if wave.levels[i] != wave.levels[i-1]]
            assert len(indexes) == 22
            for index in indexes:
                for fraction in FRACTIONS:
                    for entry in ENTRIES:
                        incoming = single_crossover(pristine(), index, width=3.36, fraction=fraction)
                        record(incoming, entry, kind='single', rate=rate, sign=sign,
                               index=index, fraction=fraction)
            # Repeated crossings are individually legal and do not overlap.
            # They expose recovery that accumulates a small phase error.
            for fraction in FRACTIONS:
                for entry in ENTRIES:
                    incoming = pristine()
                    for index in reversed(indexes):
                        single_crossover(incoming, index, width=3.36, fraction=fraction)
                    record(incoming, entry, kind='all_transitions', rate=rate,
                           sign=sign, fraction=fraction, transitions=len(indexes))
    assert cases == 2376 + 108
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                single_cases=2376, repeated_cases=108,
                crossover_ns=210, placement_fractions=list(FRACTIONS),
                line_rise_fall_ns=300, differential_crossover_v=1.3,
                signal_witnesses=witnesses,
                certificates=certificates, failures=failures,
                response_range=[min(responses), max(responses)] if responses else None)


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('asymmetric-crossover-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Asymmetric 210 ns crossover:', report['cases'], 'cases;',
          len(report['failures']), 'failures;', report['response_range'], flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
