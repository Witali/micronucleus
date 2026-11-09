"""Accept fractional final-symbol stretching on DATA with a 670 ns EOP.

USB2.0 7.1.9.1 permits hub dribble to stretch the final physical symbol by a
noninteger duration; 7.1.13.2 requires reception of a 670 ns EOP. A sampler's
FIRST observations can be eleven clocks apart at 16 MHz, so that short EOP
can cover SECOND while both adjoining FIRST observations are nonzero.
The existing ACK-only fractional gate cannot establish DATA reception.

Stretch less than one bit after independently encoded valid DATA/CRC. There
are at most five final ones after normal stuffing, so every tested extension
stays below the six-one receiver limit. Numeric incoming CRC values alone
remain waived; count, payload, ownership and physical ACK timing stay strict.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import eop_wave
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_legal import ENTRIES, RATES, receive


VALUES = (0, 0x15, 0x55, 0x9f, 0xef, 0xff)


def stretched_data(packet, extra, rate, width, sign):
    """Hold the final encoded level; move only EOP and recovery boundaries."""
    assert 0 < extra < 1
    wave = eop_wave(packet, width, rate=rate,
                    jitter=lambda index, line: sign * (.55 if line == h.J else -.55))
    # Certify differential DATA timing before extending its final symbol.
    interval_errors(wave)
    run = 0
    for bit in reversed(wave.bits):
        if not bit:
            break
        run += 1
    assert run + extra < 6
    delay = extra * wave.period
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
    failures, responses = [], []
    cases = 0
    for value in VALUES:
        packet = h.data_packet(bytes([value]) * 8)
        for rate in RATES:
            for sign in (-1, 0, 1):
                for step in range(1, 16):
                    for width in (10.72, 24):
                        wave = stretched_data(packet, step / 16, rate, width, sign)
                        for entry in ENTRIES:
                            errors, response = receive(art, packet, wave, entry)
                            if errors:
                                failures.append(dict(value=value, rate=rate, sign=sign,
                                                     extra=step / 16, width=width,
                                                     entry=entry, errors=errors))
                            if response is not None:
                                responses.append(response)
                            cases += 1
    assert cases == 9720
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                short_eop_cases=4860, full_eop_cases=4860, failures=failures,
                response_range=[min(responses), max(responses)] if responses else None)


def test():
    import json
    art = h.build()
    report = check(art)
    path = h.ROOT / 'build' / ('fractional-data-' + art['sha256'][:16] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print('Fractional DATA final-symbol stretching:', report['cases'], 'cases;',
          len(report['failures']), 'failures;', report['response_range'], flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
