"""Receive ACK across certified single-ended SE0 and SE1 crossovers.

The DATA crossover gates certify both 210 ns voltage witnesses. This checks
the same observations in each ACK PID transition, with independent rate/jitter
certificates, minimum-width EOP and full ACK/address/caller ownership checks.
No assumption about an internal decoder loop or numeric CRC waiver is used.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_rx_legal_dribble import receive
from tests35.test_usb_crossover import single_crossover
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_asymmetric import signal_witnesses as se0_witnesses
from tests35.test_rx_crossover_se1 import signal_witnesses as se1_witnesses


def check(art):
    witnesses = dict(se0=se0_witnesses(), se1=se1_witnesses())
    bind(art)
    cases = 0
    failures = []
    certificates = []
    for rate in (1499250, 1500000, 1500750):
        for sign in (-1, 0, 1):
            for width in (10.72, 24):
                def pristine():
                    wave = h.Wave(b'\xd2', rate=rate,
                                  jitter=lambda index, line: sign * (.55 if line == h.J else -.55))
                    start = wave.boundaries[-3]
                    wave.boundaries[-2] = start + width
                    wave.boundaries[-1] = start + width + wave.period
                    wave.end = wave.boundaries[-1]
                    previous = h.J
                    wave.pin_edges = []
                    for time, line in zip(wave.boundaries, wave.levels):
                        if (previous ^ line) & 4:
                            wave.pin_edges.append(time)
                        previous = line
                    return wave
                base = pristine()
                certificates.append(dict(rate=rate, sign=sign, width=width,
                                         intervals=interval_errors(base)))
                indexes = [index for index in range(8, len(base.bits))
                           if base.levels[index] != base.levels[index - 1]]
                assert indexes == [8, 10, 11, 13]
                for entry in (5, 8, 16, 24, 32, 38):
                    def record(wave, **context):
                        nonlocal cases
                        errors = receive(art, 'ACK', b'\xd2', wave, entry, True)
                        if errors:
                            failures.append(dict(rate=rate, sign=sign, width=width,
                                                 entry=entry, errors=errors, **context))
                        cases += 1
                    record(pristine(), kind='pristine')
                    for observed in (0, 6):
                        for index in indexes:
                            for fraction in (1/21, 20/21):
                                wave = single_crossover(pristine(), index, width=3.36,
                                                        fraction=fraction, observed=observed)
                                record(wave, kind='single', index=index,
                                       fraction=fraction, observed=observed)
                        for mode in ('after', 'before', 'mixed'):
                            wave = pristine()
                            for index in reversed(indexes):
                                fraction = (20/21 if mode == 'before' or
                                            (mode == 'mixed' and index % 2) else 1/21)
                                single_crossover(wave, index, width=3.36,
                                                 fraction=fraction, observed=observed)
                            record(wave, kind='repeated', mode=mode, observed=observed)
            print('Completed rate/sign', rate, sign, 'cases', cases,
                  'failures', len(failures), flush=True)
    assert cases == 2484
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                control_cases=108, single_cases=1728, repeated_cases=648,
                failures=failures, certificates=certificates,
                signal_witnesses=witnesses,
                note='No added SYNC excursions; periodic jitter includes SYNC; no board certification')


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('ack-crossover-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('ACK crossover control:', report['cases'], 'cases;',
          len(report['failures']), 'failures;', output, flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
