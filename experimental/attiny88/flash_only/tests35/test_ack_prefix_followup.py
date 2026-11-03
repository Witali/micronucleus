"""A truncated ACK PID must not hide the next minimum-gap SETUP.

All seven proper prefixes of the genuine D2 PID terminate with a real EOP.
Reuse the normal recovery fixture's full authorization, payload, address,
cursor, reply, stack and caller checks. The following valid SETUP must be
received intact; merely rejecting the first malformed packet is insufficient.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_rx_resync import run


def check(art):
    bind(art)
    cases, failures = 0, []
    for prefix in range(1, 8):
        for rate in (1499250, 1500000, 1500750):
            for width in (10.72, 2 * 16000000 / rate, 24):
                for phase in (0, .25, .5, .75):
                    try:
                        run(art, 'ack_tail', rate, width, phase,
                            ack_prefix_bits=prefix)
                    except AssertionError as error:
                        failures.append(dict(prefix=prefix, rate=rate, width=width,
                                             phase=phase, error=str(error)))
                    cases += 1
    assert cases == 252
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                failures=failures, prefix_lengths=list(range(1, 8)))


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('ack-prefix-followup-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Truncated ACK PID to next minimum-gap SETUP:', report['cases'],
          'cases;', len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
