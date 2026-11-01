"""Accept a stretched final ACK bit with a minimum-width received EOP.

USB2.0 section 7.1.9.1 describes hub dribble as stretching the final data
bit. Its duration need not be a whole number of bit periods. D2 ends with
two ones, so extending its final level by strictly less than four periods
stays within the six-one allowance. Section 7.1.13.2 requires 670 ns reception.
The independent encoder, address ownership and caller/GPIO oracle are shared
with the whole-bit dribble gate; no expected protocol behavior is relaxed.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_rx_legal_dribble import encode, receive


def stretched_ack(extra, rate, width):
    """Delay only SE0 and subsequent boundaries, holding the last level."""
    assert 0 < extra < 4
    whole = int(extra)
    wave, legal = encode(b'\xd2', whole, rate, width)
    assert legal
    delay = (extra-whole)*wave.period
    for index in (-3, -2, -1):
        wave.boundaries[index] += delay
    wave.end = wave.boundaries[-1]
    wave.pin_edges = []
    previous = h.J
    for when, level in zip(wave.boundaries, wave.levels):
        if (previous ^ level) & 4:
            wave.pin_edges.append(when)
        previous = level
    return wave


def check(art):
    bind(art)
    cases = 0
    failures = []
    for step in range(1, 32):
        if step % 8 == 0:
            continue  # Whole-bit tails already have their exhaustive gate.
        extra = step/8
        for rate in (1_499_250, 1_500_000, 1_500_750):
            for width in (10.72, 24):
                for entry in (5, 8, 16, 24, 32, 38):
                    wave = stretched_ack(extra, rate, width)
                    errors = receive(art, 'ACK', b'\xd2', wave, entry, True)
                    if errors:
                        failures.append(dict(extra=extra, rate=rate, width=width,
                                             entry=entry, errors=errors))
                    cases += 1
    assert cases == 1008
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                short_eop_cases=504, full_eop_cases=504, failures=failures)


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT/'build'/('fractional-dribble-'+art['sha256'][:16]+'.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n')
    print('Fractional final-bit stretching:', report['cases'], 'cases;',
          len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
