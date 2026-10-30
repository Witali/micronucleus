"""OUT STALL responses obey the physical USB response deadline.

USB 2.0 sections 7.1.18.1 and 8.5.3.4 apply to persistent protocol STALL and
new errors during a control write. A correct handshake/state change is not
sufficient if the response starts too late. Existing failures remain required.
"""
from itertools import product
import json

from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_rx_eop_matrix import ENTRIES, tails, wire


def receive(art, incoming, entry, tx_length, direction):
    """Run one valid OUT DATA packet; inspect the response and final state."""
    cpu = h.CPU(art, incoming, entry)
    cpu.m[0x100] = 7
    cpu.m[0x10f] = tx_length
    cpu.m[0x114] = 0xe1
    cpu.r[11] = direction
    cpu.r[3] = 64  # Pending WRITE4 must not be released by an OUT error.
    cpu.r[24:26] = [0xa5, 0xb6]
    cpu.r[4:6] = [0x80, 0]
    handshakes = []
    returned = False
    for _ in range(10_000):
        if cpu.pc == 0xfffe:
            returned = True
            break
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            handshakes.append((cpu.r[19], cpu.r[20]))
        cpu.step()
    first_k = next((time for time, io, value in cpu.bus_events
                    if io == 11 and value & 6 == h.K), None)
    response = None if first_k is None else first_k - incoming.boundaries[-2]
    problems = []
    if not returned:
        problems.append('handler did not return')
    if handshakes != [(2, 0x1e)]:
        problems.append('expected exactly one STALL')
    if cpu.m[0x10f] != 0x1e or cpu.m[0x114] != 0:
        problems.append('STALL/token state mismatch')
    expected_command = 64 if tx_length == 0x1e else 0
    expected_message = 7 if tx_length == 0x1e else 0xe1
    if cpu.r[3] != expected_command or cpu.m[0x100] != expected_message:
        problems.append('pending command/completion state mismatch')
    if cpu.r[4:6] != [0x80, 0]:
        problems.append('OUT error advanced the Flash cursor')
    if cpu.r[24:26] != [0xa5, 0xb6] or cpu.raw_stack:
        problems.append('caller registers/stack not restored')
    if cpu.io.get(10, 0) & 6:
        problems.append('USB pins still driven after return')
    if (response is None
            or not 2*(85/8) <= response <= 6.5*min(85/8, incoming.period)):
        problems.append('response outside recovery-J deadline')
    return dict(response=response, problems=problems)


def check(art):
    bind(art)
    groups = {name: dict(cases=0, failures=0, responses=[])
              for name in ('new_protocol_stall', 'persistent_stall')}
    errors = []
    packets = [h.data_packet(payload, pid)
               for pid in (0xc3, 0x4b) for payload in (b'', bytes([255])*8)]
    for packet in packets:
        for tail, rate, width, sign, entry in product(
                tails(packet), (1_499_250, 1_500_750), (10.72, 24),
                (-1, 0, 1), ENTRIES):
            incoming = wire(packet, tail, rate, width, sign)
            for tx_length, direction in ((12, 0), (0x1e, 0), (0x1e, 0x80)):
                name = ('persistent_stall' if tx_length == 0x1e
                        else 'new_protocol_stall')
                result = receive(art, incoming, entry, tx_length, direction)
                group = groups[name]
                group['cases'] += 1
                if result['response'] is not None:
                    group['responses'].append(result['response'])
                if result['problems']:
                    group['failures'] += 1
                    errors.append(dict(group=name, packet=packet.hex(), tail=tail,
                                       rate=rate, eop_width=width, skew=sign,
                                       entry=entry, tx_length=tx_length,
                                       direction=direction, **result))
    for group in groups.values():
        responses = group.pop('responses')
        group['response_range'] = ([min(responses), max(responses)]
                                   if responses else None)
    cases = sum(group['cases'] for group in groups.values())
    assert cases == 6048
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases,
                groups=groups, errors=errors)


def test():
    report = check(h.build())
    destination = h.ROOT / 'build' / ('out-response-' + report['sha256'][:16] + '.json')
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print('OUT STALL timing:', report['cases'], 'cases;', len(report['errors']),
          'failures;', report['bytes'], 'bytes;', report['groups'], flush=True)
    assert not report['errors'], ('OUT STALL response failures',
                                  len(report['errors']), report['errors'][:4])


if __name__ == '__main__':
    test()
