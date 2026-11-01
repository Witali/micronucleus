"""Asymmetric crossover recovery preserves arbitrary payload bits.

All-zero and mixed data distinguish a current transition from an excursion
around the next transition. A recovered line alone must not substitute an
assumed zero for an unobserved payload bit. The voltage witness, independent
packet oracle and numeric-CRC-only waiver are shared with the asymmetric gate.
This bounded nominal-rate corpus complements its rate/jitter/entry matrix.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_asymmetric import FRACTIONS, signal_witnesses
from tests35.test_rx_crossover_legal import receive
from tests35.test_usb_crossover import single_crossover


PAYLOAD_VALUES = (0x00, 0x15, 0x9f)
ENTRIES = (8, 16, 38)


def check(art):
    bind(art)
    witnesses = signal_witnesses()
    failures = []
    counts = []
    cases = 0
    for value in PAYLOAD_VALUES:
        packet = h.data_packet(bytes([value]) * 8)
        pristine = h.Wave(packet, rate=1_500_000)
        certificate = interval_errors(pristine)
        errors, _ = receive(art, packet, pristine, ENTRIES[0])
        assert not errors, ('pristine payload control', value, errors)
        indexes = [index for index in range(8, len(pristine.bits))
                   if pristine.levels[index] != pristine.levels[index-1]]
        counts.append(dict(value=value, transitions=len(indexes),
                           cases=(len(indexes)+1)*len(FRACTIONS)*len(ENTRIES),
                           jitter_certificate=certificate))
        for index in [*indexes, None]:
            affected = [index] if index is not None else list(reversed(indexes))
            for fraction in FRACTIONS:
                for entry in ENTRIES:
                    incoming = h.Wave(packet, rate=1_500_000)
                    for edge in affected:
                        single_crossover(incoming, edge, width=3.36, fraction=fraction)
                    errors, response = receive(art, packet, incoming, entry)
                    if errors:
                        failures.append(dict(value=value, index=index, fraction=fraction,
                                             entry=entry, errors=errors, response=response))
                    cases += 1
    assert cases == sum(row['cases'] for row in counts) == 978
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                pristine_controls=len(PAYLOAD_VALUES),
                payloads=counts, signal_witnesses=witnesses, failures=failures)


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('asymmetric-payloads-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Asymmetric crossover payload preservation:', report['cases'],
          'cases;', len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
