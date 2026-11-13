"""Exercise certified threshold excursions in both SYNC and packet bits."""

import json
import os

from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_asymmetric import signal_witnesses as se0_witnesses
from tests35.test_rx_crossover_legal import ENTRIES, RATES, receive as receive_data
from tests35.test_rx_crossover_se1 import WIDTH_CLOCKS, signal_witnesses as se1_witnesses
from tests35.test_rx_legal_dribble import receive as receive_final_ones
from tests35.test_usb_crossover import single_crossover


def entry_phases(exhaustive):
    if not exhaustive:
        return ENTRIES
    return ENTRIES + tuple(base + phase for base in (*ENTRIES, 39, 40)
                           for phase in (.25, .5, .75))


def check(art, exhaustive):
    """Require complete SETUP DATA reception and retirement of eligible ACK."""
    witnesses = dict(se0=se0_witnesses(), se1=se1_witnesses())
    entries = entry_phases(exhaustive)
    bind(art)
    failures = []
    counts = dict(pristine=0, injected=0)
    patterns = (('ACK', b'\xd2'), ('FF DATA', h.data_packet(b'\xff' * 8)),
                ('EF DATA', h.data_packet(b'\xef' * 8)))

    def record(wave, entry, label, packet, **context):
        if label == 'ACK':
            errors = receive_final_ones(art, 'ACK', packet, wave, entry, True)
            response = None
        else:
            errors, response = receive_data(art, packet, wave, entry)
        counts['pristine' if context['placement'] == 'pristine' else 'injected'] += 1
        if errors:
            failures.append(dict(context, packet=packet.hex(), kind=label,
                                 entry=entry, errors=errors, response=response))

    for label, packet in patterns:
        for rate in RATES:
            for sign in (-1, 0, 1):
                def pristine():
                    return h.Wave(packet, rate=rate, jitter=lambda _, line:
                                  sign * (.55 if line == h.J else -.55))

                reference = pristine()
                interval_errors(reference)
                edges = [index for index in range(1, len(reference.bits))
                         if reference.levels[index] != reference.levels[index - 1]]
                assert edges[:6] == list(range(1, 7)) and edges[6] >= 8
                # Each voltage witness is settled outside -250..+250 ns.
                # This separation lets us compose placements on consecutive
                # transitions while preserving the differential jitter proof.
                assert all((reference.boundaries[b] - reference.boundaries[a]) * 62.5 > 500
                           for a, b in zip(edges, edges[1:]))
                for entry in entries:
                    record(reference, entry, label, packet, rate=rate, sign=sign,
                           placement='pristine', observed=None)
                for observed in (0, h.J | h.K):
                    for placement in ('before', 'after', 'alternating', 'reverse-alternating'):
                        wave = pristine()
                        for edge in reversed(edges):
                            before = (placement == 'before' or
                                      (placement == 'alternating' and edge % 2 == 1) or
                                      (placement == 'reverse-alternating' and edge % 2 == 0))
                            single_crossover(wave, edge, width=WIDTH_CLOCKS,
                                             fraction=20/21 if before else 1/21,
                                             observed=observed)
                        for entry in entries:
                            record(wave, entry, label, packet, rate=rate, sign=sign,
                                   placement=placement, observed=observed)
    assert counts == dict(pristine=27 * len(entries), injected=216 * len(entries))
    return dict(bytes=art['size'], sha256=art['sha256'], cases=sum(counts.values()),
                counts=counts, exhaustive=exhaustive, voltage_witnesses=witnesses,
                failures=failures)


def test():
    art = h.build()
    report = check(art, os.environ.get('USB_PHY_EXHAUSTIVE') == '1')
    output = h.ROOT / 'build' / ('combined-crossover-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Combined SYNC/packet crossover:', report['counts'],
          'failures:', len(report['failures']), flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
