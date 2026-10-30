"""Receive legal centered low-speed crossovers without losing SETUP DATA.

USB2.0 section 7.1.2.1 permits monotonic 75..300 ns low-speed rise/fall
times, matched within 20%, and differential crossover voltage 1.3..2.0 V.
Section 7.1.4.1 permits single-ended thresholds 0.8..2.0 V and requires
receiver logic not to interpret a <=210 ns both-below-VIH crossover as SE0.

The nominal differential crossing is the center of this 150 ns excursion.
A timing witness is D+ = clamp(1.3 + (0.7/75)*t_ns, 0, 3.3) and
D- = clamp(1.3 - (0.7/75)*t_ns, 0, 3.3), or the reversed pair. Their
differential voltages cross at t=0 and 1.3 V. At single-ended threshold
2.0 V, the falling pin crosses VIH at -75 ns and the rising pin at +75 ns.
Both monotonic 10..90% transitions take 282.857 ns and match exactly.
The GPIO both-low interval therefore surrounds the differential crossing;
it is not an additional 150 ns delay of the differential data edge.

No jitter is injected. This signal-timing witness does not certify physical
loads, an actual AVR input threshold, a board or complete electrical compliance.
It does not claim that the older endpoint-placed 210 ns stress inputs are all
physically realizable. Only numeric incoming CRC16 storage is waived.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import complete_frame_entries
from tests35.test_usb_crossover import single_crossover


RATES = (1_499_250, 1_500_000, 1_500_750)
ENTRIES = (5, 8, 16, 24, 32, 38)
CROSSOVER_CLOCKS = 150 * 16_000_000 / 1_000_000_000


def receive(art, packet, incoming, entry):
    cpu = h.CPU(art, incoming, entry)
    cpu.r[24:26] = [0xa5, 0xb6]
    cpu.r[4:6] = [0x80, 0]
    cpu.r[12:16] = [0x11, 0x22, 0x88, 0]
    cpu.r[6:8] = [0x33, 0x44]
    cpu.m[0x114] = 0x2d  # Valid SETUP token owns the following DATA0.
    cpu.m[0x10f] = 0x5a
    cpu.r[2:4] = [0, 0]  # No old IN ACK window or pending command.
    frames = complete_frame_entries(art)
    complete = False
    replies = []
    spm = False
    premature_publication = False
    for _ in range(16000):
        if cpu.pc == 0xfffe:
            break
        if cpu.pc in frames:
            # Count includes both CRC byte positions. Their numeric values
            # alone are excluded under the existing incoming-CRC16 waiver.
            complete |= (cpu.r[23] == len(packet) and
                         bytes(cpu.m[0x116:0x116 + len(packet) - 2]) == packet[:-2])
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            replies.append((cpu.r[19], cpu.r[20]))
        offset = cpu.pc - art['boot']
        spm |= art['body'][offset:offset + 2] == b'\xe8\x95'
        cpu.step()
        if cpu.t < incoming.boundaries[-3] and cpu.r[3] == 11:
            premature_publication = True
    else:
        raise AssertionError('Centered crossover handler did not return')

    errors = []
    if not complete:
        errors.append('complete PID/payload/CRC-position count not received')
    if replies != [(2, 0xd2)]:
        errors.append(('SETUP DATA ACK', replies))
    if (cpu.r[3] != 11 or cpu.r[2] != 0 or
            cpu.r[12:16] + cpu.r[6:8] != list(packet[3:-2]) or
            cpu.word(4) != 0x80 or cpu.m[0x10f] != 0x5a or
            cpu.m[0x114] != 0 or spm):
        errors.append('SETUP publication/ACK/cursor ownership')
    if (cpu.r[24:26] != [0xa5, 0xb6] or cpu.r[1] != 0 or
            cpu.raw_stack or cpu.word(28) != 0x100 or cpu.word(30) != 0x100):
        errors.append('caller/register/stack restoration')
    if cpu.io.get(0x0a, 0) & 6:
        errors.append('USB pins not released')
    if any(when < incoming.boundaries[-3] and io == 0x0a and value & 6
           for when, io, value in cpu.bus_events):
        errors.append('premature USB drive')
    if premature_publication:
        errors.append('premature SETUP publication')
    start = next((when for when, io, value in cpu.bus_events
                  if io == 11 and value & 6 == h.K), None)
    response = None if start is None else start - incoming.boundaries[-2]
    if response is None or not 2 * (85 / 8) <= response <= 6.5 * min(85 / 8, incoming.period):
        errors.append(('physical ACK response timing', response))
    return errors, response


def check(art):
    bind(art)
    packet = h.data_packet(bytes([255]) * 8)
    cases = 0
    failures = []
    responses = []
    for rate in RATES:
        pristine = h.Wave(packet, rate=rate)
        indexes = [index for index in range(8, len(pristine.bits))
                   if pristine.levels[index] != pristine.levels[index - 1]]
        assert len(indexes) == 22
        for index in indexes:
            incoming = single_crossover(h.Wave(packet, rate=rate), index,
                                        width=CROSSOVER_CLOCKS, fraction=0.5)
            for entry in ENTRIES:
                errors, response = receive(art, packet, incoming, entry)
                if errors:
                    failures.append(dict(rate=rate, index=index, entry=entry, errors=errors))
                if response is not None:
                    responses.append(response)
                cases += 1
    assert cases == 396, cases
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                crossover_ns=150, injected_jitter=False, failures=failures,
                response_range=[min(responses), max(responses)] if responses else None)


def test():
    import json
    art = h.build()
    report = check(art)
    output = h.ROOT / 'build' / ('legal-crossover-' + art['sha256'][:16] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Centered 150 ns, zero-jitter crossover:', report['cases'], 'cases;',
          len(report['failures']), 'failures;', report['response_range'], flush=True)
    assert not report['failures'], ('legal crossover receive failures', report['failures'][:4])


if __name__ == '__main__':
    test()
