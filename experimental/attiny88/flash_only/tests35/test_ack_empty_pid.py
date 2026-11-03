"""SYNC followed directly by EOP cannot authorize an ACK transaction."""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import from_bits
from tests35.test_rx_legal_dribble import receive


def check(art):
    bind(art)
    sync = h.Wave(b'').bits
    assert sync == [0, 0, 0, 0, 0, 0, 0, 1]
    cases, failures = 0, []
    for rate in (1499250, 1500000, 1500750):
        for width in (10.72, 64 / 3, 24):
            for sign in (-1, 0, 1):
                wave = from_bits(sync, rate=rate, width=width)
                for index, line in enumerate(wave.levels[:-3]):
                    wave.boundaries[index] += sign * (.55 if line == h.J else -.55)
                wave.pin_edges = []
                before = h.J
                for time, line in zip(wave.boundaries, wave.levels):
                    if (before ^ line) & 4:
                        wave.pin_edges.append(time)
                    before = line
                for entry in (5, 8, 16, 24, 32, 38):
                    errors = receive(art, 'ACK', b'\xd2', wave, entry, False)
                    if errors:
                        failures.append(dict(rate=rate, width=width, sign=sign,
                                             entry=entry, errors=errors))
                    cases += 1
    assert cases == 162
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                failures=failures, raw_pid_bits=0,
                oracle='Existing test_rx_legal_dribble.receive(..., legal=False), unchanged')


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('ack-empty-pid-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('SYNC without a PID:', report['cases'], 'cases;',
          len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
