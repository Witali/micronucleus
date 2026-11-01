"""Centered 150 ns crossover reception across certified 75/45 ns edge corners.

Differential-edge intervals are certified before inserting one single-ended
crossover witness. The local monotonic timing witness and receive oracle are
owned by test_rx_crossover_legal; numeric incoming DATA CRC16 alone is waived.
"""
from copy import deepcopy

from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import corners, interval_errors
from tests35.test_rx_crossover_legal import ENTRIES, RATES, receive
from tests35.test_usb_crossover import single_crossover


def check(art, target_indices=None, stop_after=None, width_ns=150):
    bind(art)
    assert width_ns in (150, 210)
    width = width_ns * 16_000_000 / 1_000_000_000
    packet = h.data_packet(bytes([255]) * 8)
    failures, responses, certificates = [], [], []
    cases = 0
    for rate in RATES:
        for pristine in corners(h.Wave(packet, rate=rate)):
            errors_ns = interval_errors(pristine)
            certificate = dict(pristine.jitter_certificate, rate=rate, errors_ns=errors_ns)
            certificates.append(certificate)
            indices = [index for index in range(8, len(pristine.bits))
                       if pristine.levels[index] != pristine.levels[index-1]]
            assert len(indices) == 22
            if target_indices is not None:
                indices = [index for index in indices if index in target_indices]
                assert len(indices) == len(target_indices)
            for index in indices:
                incoming = single_crossover(deepcopy(pristine), index,
                                            width=width, fraction=0.5)
                for entry in ENTRIES:
                    errors, response = receive(art, packet, incoming, entry)
                    cases += 1
                    if response is not None:
                        responses.append(response)
                    if errors:
                        row = dict(rate=rate, pattern=certificate['pattern'],
                                   rotation=certificate['rotation'], sign=certificate['sign'],
                                   scale=certificate['scale'], index=index, entry=entry,
                                   errors_ns=errors_ns, errors=errors, response=response)
                        failures.append(row)
                        if len(failures) == 1:
                            print('FIRST certified crossover corner failure:', row, flush=True)
                        if stop_after is not None and len(failures) >= stop_after:
                            return report(art, cases, failures, responses, certificates, False, width_ns)
    expected = 28 * len(RATES) * (len(target_indices) if target_indices is not None else 22) * len(ENTRIES)
    assert cases == expected
    return report(art, cases, failures, responses, certificates, True, width_ns)


def report(art, cases, failures, responses, certificates, completed, width_ns=150):
    return dict(bytes=art['size'], sha256=art['sha256'], boot=hex(art['boot']),
                cases=cases, completed=completed, crossover_ns=width_ns,
                certificates=certificates, failures=failures,
                response_range=[min(responses), max(responses)] if responses else None)


def check_repeated(art, width_ns=150):
    """Exercise all 22 data crossings together, keeping SYNC untouched."""
    bind(art)
    assert width_ns in (150, 210)
    width = width_ns * 16_000_000 / 1_000_000_000
    packet = h.data_packet(bytes([255]) * 8)
    failures, responses, certificates = [], [], []
    cases = 0
    for rate in RATES:
        for pristine in corners(h.Wave(packet, rate=rate)):
            errors_ns = interval_errors(pristine)
            certificates.append(dict(pristine.jitter_certificate, rate=rate,
                                     errors_ns=errors_ns))
            indices = [index for index in range(8, len(pristine.bits))
                       if pristine.levels[index] != pristine.levels[index-1]]
            assert len(indices) == 22
            incoming = deepcopy(pristine)
            # Descending insertion retains every original physical bit index.
            for index in reversed(indices):
                single_crossover(incoming, index, width=width, fraction=0.5)
            for entry in ENTRIES:
                errors, response = receive(art, packet, incoming, entry)
                if errors:
                    failures.append(dict(rate=rate, entry=entry, errors=errors,
                                         certificate=pristine.jitter_certificate))
                if response is not None:
                    responses.append(response)
                cases += 1
    assert cases == 504
    return report(art, cases, failures, responses, certificates, True, width_ns)


def test():
    import json
    art = h.build()
    result = check(art)
    repeated = check_repeated(art)
    result['repeated_crossovers'] = repeated
    path = h.ROOT / 'build' / ('crossover-corners-' + art['sha256'][:16] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print('Certified edge corners plus centered 150 ns crossover:', result['cases'],
          'single and', repeated['cases'], 'repeated cases;',
          len(result['failures']) + len(repeated['failures']), 'failures', flush=True)
    assert not result['failures'], ('Certified corner/crossover receive failures',
                                    result['failures'][:4])
    assert not repeated['failures'], ('Repeated certified crossover receive failures',
                                      repeated['failures'][:4])


if __name__ == '__main__':
    test()
