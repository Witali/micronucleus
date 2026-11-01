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
    # A next stuffed transition must not replace an actual payload one.
    # This valid input made a partial recovery ACK and publish DB instead
    # of EF. Numerical CRC storage cannot waive that payload corruption.
    # These two valid signals alias in the partial control's registers and
    # memory at its recovery decision, but require opposite payload bits.
    # Both must work; changing the inferred bit merely swaps which one fails.
    ownership = (
        ('next_stuffed_transition', bytes([0xef])*8, 1_500_750, -1, 8, 82,
         FRACTIONS[1], 'c3efefefefefefefef24e7', 1),
        ('current_transition', bytes([0xef])*7+b'\xdb', 1_499_250, 1, 5, 81,
         FRACTIONS[0], 'c3efefefefefefefdb2530', 0),
    )
    ownership_certificates = []
    for kind, payload, rate, sign, entry, index, fraction, encoded, intended_bit in ownership:
        packet = h.data_packet(payload)
        assert packet.hex() == encoded and (payload[-1] >> 2) & 1 == intended_bit
        pristine = h.Wave(packet, rate=rate,
                          jitter=lambda position, line: sign*(.55 if line == h.J else -.55))
        ownership_certificates.append(dict(kind=kind, certificate=interval_errors(pristine)))
        assert pristine.bits[index] == 0
        if kind == 'next_stuffed_transition':
            assert pristine.bits[index-6:index] == [1] * 6
        errors, _ = receive(art, packet, pristine, entry)
        assert not errors, ('pristine ownership control', kind, errors)
        incoming = single_crossover(pristine, index, width=3.36, fraction=fraction)
        errors, response = receive(art, packet, incoming, entry)
        if errors:
            failures.append(dict(kind=kind, payload=payload.hex(), index=index,
                                 fraction=fraction, entry=entry, rate=rate, sign=sign,
                                 errors=errors, response=response))
        cases += 1
    assert cases == 980
    # Four-clock-separated zero reads can hit two DIFFERENT valid pulses.
    # Explicit rail tails in the witness keep these adjacent waveforms
    # settled between edges; their differential intervals remain certified.
    packet = h.data_packet(bytes(8))
    assert packet.hex() == 'c30000000000000000bff4'
    pristine = h.Wave(packet, rate=1_500_750,
                      jitter=lambda index, line: .55 if line == h.J else -.55)
    adjacent_certificate = interval_errors(pristine)
    assert pristine.bits[12:14] == [0, 0]
    spacing_ns = (pristine.boundaries[13]-pristine.boundaries[12])*62.5
    assert spacing_ns > 500  # +250 ns tail precedes the next -250 ns start.
    errors, _ = receive(art, packet, pristine, 8)
    assert not errors, ('pristine adjacent-pulse control', errors)
    incoming = single_crossover(pristine, 13, width=3.36, fraction=FRACTIONS[1])
    single_crossover(incoming, 12, width=3.36, fraction=FRACTIONS[0])
    errors, response = receive(art, packet, incoming, 8)
    if errors:
        failures.append(dict(kind='adjacent_differently_placed_transients', value=0,
                             indexes=[12, 13], entry=8, rate=1_500_750, sign=1,
                             errors=errors, response=response))
    cases += 1
    assert cases == 981
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                pristine_controls=len(PAYLOAD_VALUES)+len(ownership)+1,
                ownership_cases=len(ownership), ownership_jitter_certificates=ownership_certificates,
                adjacent_pulse_cases=1, adjacent_jitter_certificate=adjacent_certificate,
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
