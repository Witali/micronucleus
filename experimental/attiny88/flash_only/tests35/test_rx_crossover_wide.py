"""Centered 210 ns GPIO excursions with a matched 300 ns monotonic witness.

For voltages clipped to 0..3.3 V, define F(t_ns) as:
  t < -105: 0.6 + (t+105)*1.24/90;
  -105 <= t <= 105: 1.3 + t*0.7/105;
  t > 105: 2.0 + (t-105)*1.24/90.
Use D+ = F(t), D- = F(-t), or the reversed pair. Crossing voltage is 1.3 V.
At VIH = 2 V both are low between -105 and +105 ns. The 10..90% rise/fall
times are exactly 300 ns and match. USB2.0 7.1.2.1/7.1.4.1 permit these limits.
Only centered excursions have this witness; endpoint-placed stress remains
separate. Digital instruction tests do not certify an analog board.
"""
from tests35 import ep0_model as h
from tests35 import test_rx_crossover_legal as ordinary
from tests35 import test_rx_crossover_jitter as jitter
from tests35 import test_rx_crossover_corners as corners


def witness():
    """Check the voltage/timing arithmetic used to construct the fixture."""
    slope = 1.24 / 90
    ten = -105 + (0.33 - 0.6) / slope
    ninety = 105 + (2.97 - 2.0) / slope
    assert abs(ninety - ten - 300) < 1e-9
    assert abs(1.3 - 105 * 0.7 / 105 - 0.6) < 1e-9
    assert abs(1.3 + 105 * 0.7 / 105 - 2.0) < 1e-9


def check(art):
    witness()
    reports = {
        'ordinary': ordinary.check(art, width_ns=210),
        'jitter': jitter.check(art, width_ns=210),
        'corners': corners.check(art, width_ns=210),
        'repeated': corners.check_repeated(art, width_ns=210),
    }
    assert sum(row['cases'] for row in reports.values()) == 12780
    return dict(bytes=art['size'], sha256=art['sha256'], cases=12780,
                crossover_ns=210, rise_fall_ns=300, reports=reports)


def test():
    import json
    art = h.build()
    result = check(art)
    path = h.ROOT / 'build' / ('crossover-wide-' + art['sha256'][:16] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    failures = [(name, row['failures']) for name, row in result['reports'].items()
                if row['failures']]
    print('Monotonic 210 ns crossover:', result['cases'], 'cases;',
          sum(len(errors) for _, errors in failures), 'failures', flush=True)
    assert not failures, [(name, errors[:3]) for name, errors in failures]


if __name__ == '__main__':
    test()
