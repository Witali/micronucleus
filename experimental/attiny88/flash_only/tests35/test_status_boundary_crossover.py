"""A legal short DATA1 status cannot end at an interior byte boundary.

USB 2.0 7.1.4.1/7.1.13.2 distinguish transition crossovers from EOP.
Section 8.5.3.1 permits a nonempty read-status inquiry. The literal packet
below has valid CRC16, so this regression does not depend on the CRC waiver.
The two monotonic transition witnesses settle separately between crossings.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_asymmetric import signal_witnesses
from tests35.test_usb_crossover import single_crossover


def check(art):
    """Require complete reception and a timely ACK after the actual EOP."""
    bind(art)
    signal_witnesses()
    packet = bytes.fromhex('4b04417c')
    assert packet == h.data_packet(b'\x04', 0x4b)
    prefix = len(h.Wave(packet[:3]).bits)
    failures = []
    cases = 0
    for rate in (1499250, 1500000, 1500750):
        for sign in (-1, 0, 1):
            for entry in (5, 8, 16, 24, 32, 38):
                for injected in (False, True):
                    wire = h.Wave(packet, rate=rate, jitter=lambda index, line:
                                  sign * (.55 if line == h.J else -.55))
                    interval_errors(wire)
                    assert wire.bits[prefix:prefix + 2] == [0, 0]
                    assert (wire.boundaries[prefix + 1] - wire.boundaries[prefix]) * 62.5 > 500
                    if injected:
                        single_crossover(wire, prefix + 1, width=3.36, fraction=20/21)
                        single_crossover(wire, prefix, width=3.36, fraction=1/21)
                    cpu = h.CPU(art, wire, entry)
                    cpu.m[0x114] = 0xe1  # A validated OUT owns this read status.
                    cpu.m[0x10f] = 4     # An immutable pending zero-length IN.
                    cpu.r[4:6] = [0x80, 0]
                    cpu.r[11] = 0xc0
                    complete = False
                    for _ in range(16000):
                        if cpu.pc == 0xfffe:
                            break
                        if cpu.pc == cpu.labels['usb_rx_framing_valid']:
                            complete |= (cpu.r[23] == len(packet) and
                                         bytes(cpu.m[0x116:0x118]) == packet[:-2])
                        cpu.step()
                    else:
                        raise AssertionError('Short status did not return')
                    early = [event for event in cpu.bus_events
                             if event[0] < wire.boundaries[-3] and
                             event[1] == 0x0a and event[2] & 6]
                    first_k = next((when for when, io, value in cpu.bus_events
                                    if io == 11 and value & 6 == h.K), None)
                    response = None if first_k is None else first_k - wire.boundaries[-2]
                    errors = []
                    if early:
                        errors.append('USB driven before actual packet EOP')
                    if not complete:
                        errors.append('Complete DATA1/payload/CRC-position count missing')
                    if response is None or not 2 * (85/8) <= response <= 6.5 * min(85/8, wire.period):
                        errors.append('ACK outside physical response window')
                    if cpu.io.get(0x0a, 0) & 6 or cpu.raw_stack:
                        errors.append('Pins or stack not released')
                    if errors:
                        failures.append(dict(rate=rate, sign=sign, entry=entry,
                                             injected=injected, errors=errors,
                                             response=response, early_drive=early))
                    cases += 1
    assert cases == 108
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                pristine_controls=54, injected_cases=54, failures=failures)


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('short-status-crossover-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Short-status interior-boundary crossover:', report['cases'],
          'cases;', len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:3]


if __name__ == '__main__':
    test()
