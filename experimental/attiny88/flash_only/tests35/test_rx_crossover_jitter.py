"""Combine the centered 150 ns crossover witness with certified edge jitter.

The monotonic transition witness is documented by test_rx_crossover_legal.
Moving its differential center by a legal source-edge offset preserves that
local voltage/timing construction. Every pristine waveform is independently
checked against both next- and paired-transition input-jitter limits before
the single-ended threshold excursion is inserted.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_legal import CROSSOVER_CLOCKS, ENTRIES, RATES, receive
from tests35.test_usb_crossover import single_crossover


def check(art):
    bind(art)
    packet = h.data_packet(bytes([255]) * 8)
    failures = []
    responses = []
    certificates = []
    cases = 0
    for rate in RATES:
        for sign in (-1, 1):
            def pristine():
                return h.Wave(packet, rate=rate,
                              jitter=lambda index, line: sign * (.55 if line == h.J else -.55))
            wave = pristine()
            certificate = interval_errors(wave)
            certificates.append(dict(rate=rate, sign=sign, errors_ns=certificate))
            indexes = [index for index in range(8, len(wave.bits))
                       if wave.levels[index] != wave.levels[index - 1]]
            assert len(indexes) == 22
            for index in indexes:
                incoming = single_crossover(pristine(), index,
                                            width=CROSSOVER_CLOCKS, fraction=0.5)
                for entry in ENTRIES:
                    errors, response = receive(art, packet, incoming, entry)
                    if errors:
                        failures.append(dict(rate=rate, sign=sign, index=index,
                                             entry=entry, errors=errors))
                    if response is not None:
                        responses.append(response)
                    cases += 1
    assert cases == 792
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                crossover_ns=150, certificates=certificates, failures=failures,
                response_range=[min(responses), max(responses)] if responses else None)


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('crossover-jitter-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Certified jitter plus centered 150 ns crossover:', report['cases'],
          'cases;', len(report['failures']), 'failures', flush=True)
    assert not report['failures'], ('Jitter/crossover receive failures', report['failures'][:4])


if __name__ == '__main__':
    test()
