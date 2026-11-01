"""Seven final ones remain illegal at short EOP and late receive phases.

USB 2.0 section 7.1.9.1 permits at most six trailing bit times without an
NRZI transition. Sampling loops must not undercount a seventh bit after a
correctly stuffed, valid-CRC SETUP packet. This is independent of the numeric
incoming DATA CRC16 waiver and of the receiver's private phase representation.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35 import test_rx_eop_matrix as eop
from tests35.test_rx_legal_dribble import crc16, receive


def check(artifact):
    bind(artifact)
    failures = []
    cases = 0
    for value in (0xff, 0x00, 0x15, 0x9f):
        payload = bytes([value]) * 8
        packet = b'\xc3' + payload + crc16(payload)
        final_run = 0
        for bit in reversed(h.Wave(packet).bits):
            if not bit:
                break
            final_run += 1
        extra = 7 - final_run
        assert extra > 0
        for rate in (1_499_250, 1_500_000, 1_500_750):
            for width in (10.72, 64 / 3, 24):
                for sign in (-1, 0, 1):
                    wave = eop.wire(packet, extra, rate, width, sign)
                    for entry in (5, 8, 8.25, 16.5, 24.75, 32, 38.25):
                        errors = receive(artifact, 'SETUP', packet, wave, entry, legal=False)
                        if errors:
                            failures.append(dict(packet=packet.hex(), extra_ones=extra,
                                                 rate=rate, width=width, sign=sign,
                                                 entry=entry, errors=errors))
                        cases += 1
    assert cases == 756
    return dict(bytes=artifact['size'], sha256=artifact['sha256'], cases=cases,
                failures=failures)


def test():
    import json
    artifact = h.build()
    report = check(artifact)
    destination = h.ROOT / 'build' / ('terminal-bounds-' + artifact['sha256'][:16] + '.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print('Seven-one terminal bounds:', report['cases'], 'cases;',
          len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
