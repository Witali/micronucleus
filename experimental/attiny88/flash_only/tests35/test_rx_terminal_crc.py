"""Final odd5-stuffed CRC classes retain legal tails and reject partial data.

These four CRC endings complement the older 00/80/C0/E0/F0/F8/FC/FE corpus.
All packets have independently generated correct CRC16. The project waives
numeric incoming CRC validation and storage, never symbol positions or framing.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import Bits, bind
from tests35 import test_data_framing as framing
from tests35 import test_rx_eop_matrix as eop
from tests35.test_rx_crossover_legal import receive

CRC_HIGH_BYTES = (0x3f, 0x7f, 0xbf, 0xff)


def check(art):
    bind(art)
    packets = framing.ending_packets(True, 8, targets=CRC_HIGH_BYTES)
    legal_cases = negative_cases = 0
    failures = []
    for packet, payload in packets:
        encoded = Bits(packet).bits
        final_run = framing.final_ones(encoded)
        for tail in range(7 - final_run):
            for rate in (1_499_250, 1_500_000, 1_500_750):
                wave = eop.wire(packet, tail, rate, 10.72)
                for entry in eop.ENTRIES:
                    errors, response = receive(art, packet, wave, entry)
                    if errors:
                        failures.append(dict(kind='legal', crc_high=packet[-1],
                                             tail=tail, rate=rate, entry=entry,
                                             errors=errors, response=response))
                    legal_cases += 1

        def check_state(cpu, expected, context):
            problems = []
            if (cpu.r[3] == 11) != expected or bool(cpu.bus_events) != expected:
                problems.append('packet acceptance/response')
            if cpu.word(4) != 0x80 or cpu.m[0x10f] != 0x5a:
                problems.append('cursor/TX ownership')
            if not expected and (cpu.r[3] != 0 or
                    cpu.r[12:16] + cpu.r[6:8] != [0x11, 0x22, 0x88, 0, 0x33, 0x44]):
                problems.append('invalid packet changed pending SETUP/shadow')
            if expected and cpu.r[12:16] + cpu.r[6:8] != list(payload[2:]):
                problems.append('valid packet changed payload')
            if (cpu.r[24:26] != [0, 0] or cpu.r[1] or cpu.raw_stack or
                    cpu.word(28) != 0x100 or cpu.word(30) != 0x100):
                problems.append('caller/zero register/stack/context restoration')
            if cpu.io.get(0x0a, 0) & 6:
                problems.append('USB pins still driven')
            if any(art['body'][pc - art['boot']:pc - art['boot'] + 2] == b'\xe8\x95'
                   for pc in cpu.visited if art['boot'] <= pc < art['boot'] + art['size']):
                problems.append('SPM executed during SETUP reception')
            if problems:
                failures.append(dict(kind='framing', crc_high=packet[-1],
                                     context=context, expected=expected, errors=problems))

        for length in range(8):
            for pattern in range(1 << length):
                tail = [(pattern >> bit) & 1 for bit in range(length)]
                expected = pattern == (1 << length) - 1 and final_run + length <= 6
                cpu = framing.receive(art, packet, tail, True)
                check_state(cpu, expected, ('tail', length, pattern))
                negative_cases += 1
        for removed in range(1, 8):
            cpu = framing.receive(art, packet, (), True, encoded[:-removed])
            check_state(cpu, False, ('truncated symbols', removed))
            negative_cases += 1
    assert legal_cases == 450 and negative_cases == 1048
    return dict(bytes=art['size'], sha256=art['sha256'], legal_cases=legal_cases,
                framing_cases=negative_cases, failures=failures)


def test():
    import json
    art = h.build()
    report = check(art)
    destination = h.ROOT / 'build' / ('terminal-crc-' + art['sha256'][:16] + '.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print('Final CRC/stuffing/tail classes:', report['legal_cases'], 'legal;',
          report['framing_cases'], 'framing;', len(report['failures']), 'failures', flush=True)
    assert not report['failures'], report['failures'][:4]


if __name__ == '__main__':
    test()
