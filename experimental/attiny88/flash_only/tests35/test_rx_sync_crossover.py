"""Acquire valid SYNC despite legal single-ended crossover observations.

USB2 7.1.4.1 applies to SYNC transitions as well as PID and data. Use the
monotonic, matched 300 ns witnesses certified by the asymmetric crossover
gate. The unique differential crossings, SOP and all data cells are unchanged.
Only incoming numeric DATA CRC16 validation/storage remain waived.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_asymmetric import signal_witnesses
from tests35.test_rx_crossover_legal import receive, RATES, ENTRIES
from tests35.test_usb_crossover import single_crossover


def check(art):
    """Require complete reception and one timely ACK after each SYNC input."""
    bind(art)
    packet = h.data_packet(bytes([255]) * 8)
    failures = []
    responses = []
    certificates = []
    cases = 0
    controls = 0

    def record(wave, entry, **context):
        nonlocal cases, controls
        errors, response = receive(art, packet, wave, entry)
        if errors:
            failures.append(dict(context, entry=entry, errors=errors))
        if response is not None:
            responses.append(response)
        if context['kind'] == 'pristine':
            controls += 1
        else:
            cases += 1

    for rate in RATES:
        for sign in (-1, 0, 1):
            def pristine():
                return h.Wave(packet, rate=rate,
                              jitter=lambda index, line: sign * (.55 if line == h.J else -.55))
            certificates.append(dict(rate=rate, sign=sign,
                                     next_paired_ns=interval_errors(pristine())))
            indexes = [index for index in range(1, 8)
                       if pristine().levels[index] != pristine().levels[index - 1]]
            assert indexes == list(range(1, 7))
            for entry in ENTRIES:
                record(pristine(), entry, kind='pristine', rate=rate, sign=sign)
                for index in indexes:
                    for fraction in (1/21, .5, 20/21):
                        wave = single_crossover(pristine(), index, width=3.36,
                                                fraction=fraction)
                        record(wave, entry, kind='single', rate=rate, sign=sign,
                               index=index, fraction=fraction)
                for fraction in (1/21, 20/21):
                    wave = pristine()
                    for index in reversed(indexes):
                        single_crossover(wave, index, width=3.36, fraction=fraction)
                    record(wave, entry, kind='all_sync_transitions', rate=rate,
                           sign=sign, fraction=fraction, transitions=len(indexes))
    assert cases == 972 + 108 and controls == 54
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                single_cases=972, repeated_cases=108, control_cases=controls,
                crossover_ns=210, signal_witnesses=signal_witnesses(),
                certificates=certificates, failures=failures,
                response_range=[min(responses), max(responses)] if responses else None)


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('sync-crossover-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('SYNC 210 ns crossover:', report['cases'], 'injected cases;',
          report['control_cases'], 'controls;', len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
