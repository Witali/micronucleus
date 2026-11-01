"""Reject extra ACK tail zeros even when legal crossovers hide their edges.

A one- or two-zero tail after D2 is not legal all-one dribble and does not
terminate the one-byte handshake correctly. Reuse the existing partial-frame
rejection oracle unchanged, including its historical generic error text.

The source differential edges retain the certified rate/jitter limits.
Each inserted 210 ns single-ended observation has a monotonic full-rail,
matched 300 ns electrical witness at Vcross 1.3 V / threshold 2 V for SE0,
or its complemented counterpart at Vcross 2 V / threshold 1.3 V for SE1.
A transient SE1 here is not a sustained invalid bus-state waiver.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import from_bits
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_legal import RATES, ENTRIES
from tests35.test_rx_crossover_se1 import threshold_time, voltage
from tests35.test_rx_legal_dribble import receive
from tests35.test_usb_crossover import single_crossover


PLACEMENTS = (1e-6, 1 / 21, .25, .5, .75, 20 / 21, 1 - 1e-6)
CRITICAL_PAIRS = ((1e-6, .75), (1e-6, 20 / 21), (1 / 42, 20 / 21))
# Same-placement and mirrored-placement pairs cover all seven values on
# each edge without a quadratic product. Retain the measured aliases too.
PAIR_PLACEMENTS = tuple(sorted(set([(value, value) for value in PLACEMENTS] +
                                   list(zip(PLACEMENTS, reversed(PLACEMENTS))) +
                                   list(CRITICAL_PAIRS))))
assert len(PAIR_PLACEMENTS) == 16
WIDTH_CLOCKS = 3.36
EOP_CLOCKS = 10.72


def placement_witness(fraction, observed):
    """Certify one placement, including the near-endpoint stress samples."""
    assert 0 < fraction < 1 and observed in (0, 6)
    begin = -210 * fraction
    end = 210 * (1 - fraction)
    low90 = -60 - 210 * fraction
    high90 = low90 + 300
    rise = [(low90 - 10, 0), (low90, .33), (0, 1.3),
            (end, 2), (high90, 2.97), (high90 + 10, 3.3)]
    fall = [(low90 - 10, 3.3), (low90, 2.97), (begin, 2),
            (0, 1.3), (high90, .33), (high90 + 10, 0)]
    threshold, crossing = 2.0, 1.3
    if observed == 6:
        rise, fall = ([(time, round(3.3 - value, 12)) for time, value in fall],
                      [(time, round(3.3 - value, 12)) for time, value in rise])
        threshold, crossing = 1.3, 2.0
    assert all(ta < tb and va < vb
               for (ta, va), (tb, vb) in zip(rise, rise[1:]))
    assert all(ta < tb and va > vb
               for (ta, va), (tb, vb) in zip(fall, fall[1:]))
    assert rise[0][1] == fall[-1][1] == 0
    assert rise[-1][1] == fall[0][1] == 3.3
    up = threshold_time(rise, 2.97) - threshold_time(rise, .33)
    down = threshold_time(fall, .33) - threshold_time(fall, 2.97)
    assert abs(up - 300) < 1e-9 and abs(down - 300) < 1e-9
    assert (0, crossing) in rise and (0, crossing) in fall
    actual_begin = threshold_time(fall if observed == 0 else rise, threshold)
    actual_end = threshold_time(rise if observed == 0 else fall, threshold)
    assert abs(actual_begin - begin) < 1e-9
    assert abs(actual_end - end) < 1e-9
    assert abs(actual_end - actual_begin - 210) < 1e-9
    probes = [step / 4 + .001 for step in range(-1600, 1601)]
    probes += [time + delta for time in (begin, end)
               for delta in (-1e-6, 1e-6)]
    for ns in probes:
        plus, minus = voltage(rise, ns), voltage(fall, ns)
        assert 0 <= plus <= 3.3 and 0 <= minus <= 3.3
        sample = (h.K if plus > threshold else 0) | (h.J if minus > threshold else 0)
        expected = h.J if ns < begin else observed if ns < end else h.K
        assert sample == expected, (fraction, observed, ns, sample, expected)
    return dict(fraction=fraction, observed=observed,
                rising_points_ns_v=rise, falling_points_ns_v=fall,
                threshold_v=threshold, differential_crossover_v=crossing,
                single_ended_interval_ns=[begin, end],
                matched_line_10_to_90_ns=[up, down],
                full_transition_interval_ns=[rise[0][0], rise[-1][0]])


def wire(zeros, rate, sign):
    """Append actual zero data symbols and certify their differential edges."""
    bits = h.Wave(b'\xd2').bits + [0] * zeros
    assert len(bits) == 16 + zeros
    wave = from_bits(bits, rate, width=EOP_CLOCKS)
    for index, line in enumerate(wave.levels[:-3]):
        wave.boundaries[index] += sign * (.55 if line == h.J else -.55)
    wave.pin_edges = []
    before = h.J
    for time, line in zip(wave.boundaries, wave.levels):
        if (before ^ line) & 4:
            wave.pin_edges.append(time)
        before = line
    return wave


def check(art):
    fractions = sorted(set(PLACEMENTS) | {value for pair in CRITICAL_PAIRS for value in pair})
    witnesses = [placement_witness(fraction, observed)
                 for observed in (0, 6) for fraction in fractions]
    bind(art)
    counts = dict(pristine=0, single=0, pair=0)
    failures = []
    certificates = []

    def record(incoming, entry, **context):
        # Keep this oracle's historical error wording unchanged: the same
        # malformed partial-packet rejection covers zeros and seven ones.
        errors = receive(art, 'ACK', b'\xd2', incoming, entry, False)
        if errors:
            failures.append(dict(context, entry=entry, errors=errors))
        counts[context['kind']] += 1

    for zeros in (1, 2):
        indexes = tuple(range(16, 16 + zeros))
        for rate in RATES:
            for sign in (-1, 0, 1):
                certificate = interval_errors(wire(zeros, rate, sign))
                certificates.append(dict(zeros=zeros, rate=rate, sign=sign,
                                         intervals=certificate))
                for entry in ENTRIES:
                    common = dict(zeros=zeros, rate=rate, sign=sign)
                    record(wire(zeros, rate, sign), entry,
                           kind='pristine', **common)
                    for observed in (0, 6):
                        for index in indexes:
                            for fraction in PLACEMENTS:
                                incoming = single_crossover(wire(zeros, rate, sign), index,
                                                            width=WIDTH_CLOCKS,
                                                            fraction=fraction, observed=observed)
                                record(incoming, entry, kind='single', observed=observed,
                                       index=index, fraction=fraction, **common)
                        if zeros == 2:
                            for first, second in PAIR_PLACEMENTS:
                                incoming = wire(zeros, rate, sign)
                                single_crossover(incoming, 17, width=WIDTH_CLOCKS,
                                                 fraction=second, observed=observed)
                                single_crossover(incoming, 16, width=WIDTH_CLOCKS,
                                                 fraction=first, observed=observed)
                                record(incoming, entry, kind='pair', observed=observed,
                                       fractions=[first, second], **common)
    assert counts == dict(pristine=108, single=2268, pair=1728), counts
    failure_counts = {kind: sum(row['kind'] == kind for row in failures)
                      for kind in counts}
    return dict(bytes=art['size'], sha256=art['sha256'], cases=sum(counts.values()),
                counts=counts, failure_counts=failure_counts,
                single_placements=list(PLACEMENTS),
                pair_placements=[list(pair) for pair in PAIR_PLACEMENTS],
                critical_pairs=[list(pair) for pair in CRITICAL_PAIRS],
                physical_tail_bits=[[0], [0, 0]], observed_values=[0, 6],
                minimum_EOP_clocks=EOP_CLOCKS,
                signal_witnesses=witnesses, certificates=certificates,
                failures=failures,
                oracle='Existing test_rx_legal_dribble.receive(..., legal=False), unchanged',
                sync_scope='Periodic jitter includes SYNC; inserted crossover observations affect only the actual extra tail transitions.')


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('ack-tail-crossover-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Malformed ACK tails with crossover observations:', report['cases'],
          'cases;', len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
