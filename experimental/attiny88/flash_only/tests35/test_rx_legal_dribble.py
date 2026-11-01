"""Receive valid-CRC SETUP and ACK final-one tails, with exact ownership.

Derived from the independent Pass40 USB audit's two counterexamples. USB2.0
7.1.9.1 permits up to six final bit times without an NRZI transition. Seven
ones without the mandatory stuffed zero remain an error. This encoder does
not use the firmware's classifier or the existing packet encoder.
"""
import os

from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import complete_frame_entries


def crc16(payload):
    """USB reflected CRC16, including initial value and final complement."""
    value = 0xffff
    for byte in payload:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return (value ^ 0xffff).to_bytes(2, 'little')


def encode(packet, extra, rate, width):
    """Append tail ones after normal packet stuffing, including final CRC."""
    bits = []
    run = 0
    for byte in b'\x80' + packet:
        for shift in range(8):
            bit = (byte >> shift) & 1
            bits.append(bit)
            run = run + 1 if bit else 0
            if run == 6:
                bits.append(0)
                run = 0
    legal = run + extra <= 6
    bits.extend([1] * extra)
    wave = h.Wave(b'')
    wave.packet = packet
    wave.start = 0
    wave.period = 16_000_000 / rate
    wave.bits, wave.boundaries, wave.levels, wave.labels = bits, [], [], []
    line = h.J
    for index, bit in enumerate(bits):
        if not bit:
            line = h.K if line == h.J else h.J
        wave.boundaries.append(index * wave.period)
        wave.levels.append(line)
        wave.labels.append(index)
    end = len(bits) * wave.period
    wave.boundaries.extend((end, end + width, end + width + wave.period))
    wave.levels.extend((0, h.J, h.J))
    wave.labels.extend(('SE0', 'EOP_J', 'idle'))
    wave.end = wave.boundaries[-1]
    wave.pin_edges = []
    previous = h.J
    for time, line in zip(wave.boundaries, wave.levels):
        if (previous ^ line) & 4:
            wave.pin_edges.append(time)
        previous = line
    return wave, legal


def receive(art, kind, packet, wave, entry, legal):
    cpu = h.CPU(art, wave, entry)
    cpu.r[24:26] = [0xa5, 0xb6]
    cpu.r[4:6] = [0x80, 0]
    cpu.m[0x10f] = 12 if kind == 'ACK' else 0x5a
    cpu.m[0x10c], cpu.m[0x113] = 6, 0x24
    cpu.r[2] = 12 if kind == 'ACK' else 0
    cpu.m[0x114] = 0x2d if kind == 'SETUP' else 0
    accepted = complete = spm = False
    frames = complete_frame_entries(art)
    replies = []
    for _ in range(16000):
        if cpu.pc == 0xfffe:
            break
        if cpu.pc in frames:
            meaningful = len(packet) - 2 if kind == 'SETUP' else len(packet)
            complete |= (cpu.r[23] == len(packet) and
                         bytes(cpu.m[0x116:0x116 + meaningful]) == packet[:meaningful])
        if cpu.pc == cpu.labels['usb_rx_accept_ack']:
            accepted = True
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            replies.append((cpu.r[19], cpu.r[20]))
        offset = cpu.pc - art['boot']
        spm |= art['body'][offset:offset + 2] == b'\xe8\x95'
        cpu.step()
    else:
        raise AssertionError('Final-one receiver did not return')

    errors = []
    if legal:
        if not complete:
            errors.append('complete PID/payload/CRC positions')
        if kind == 'ACK':
            if not accepted or cpu.r[2] or cpu.m[0x10f] != 0x5a or cpu.m[0x10c] != 0x24:
                errors.append('eligible ACK did not retire DATA/apply address')
        elif (cpu.r[3] != 11 or cpu.r[2] or cpu.m[0x114] or
              cpu.r[12:16] + cpu.r[6:8] != list(packet[3:-2])):
            errors.append('SETUP fields/token ownership')
    elif accepted or cpu.r[3] == 11 or cpu.m[0x10c] != 6:
        errors.append('seven unstuffed ones authorized a packet')
    expected_replies = [(2, 0xd2)] if legal and kind == 'SETUP' else []
    if replies != expected_replies:
        errors.append(('wire reply', replies))
    if (spm or cpu.word(4) != 0x80 or cpu.r[24:26] != [0xa5, 0xb6] or
            cpu.r[1] or cpu.raw_stack or cpu.word(28) != 0x100 or cpu.word(30) != 0x100):
        errors.append('SPM/cursor/caller restoration')
    if cpu.io.get(0x0a, 0) & 6:
        errors.append('USB GPIO not released')
    driven = [(when, io, value) for when, io, value in cpu.bus_events
              if io == 0x0a and value & 6]
    if any(when < wave.boundaries[-2] for when, _, _ in driven):
        errors.append('USB drive before recovery J')
    if legal and kind == 'SETUP':
        start = next((when for when, io, value in cpu.bus_events
                      if io == 11 and value & 6 == h.K), None)
        response = None if start is None else start - wave.boundaries[-2]
        if response is None or not 2 * (85 / 8) <= response <= 6.5 * min(85 / 8, wave.period):
            errors.append(('physical ACK turnaround', response))
    return errors


def check(art):
    bind(art)
    assert crc16(b'123456789') == bytes.fromhex('c8b4')
    payload = bytes.fromhex('8006000100001200')
    setup = b'\xc3' + payload + crc16(payload)
    phases = ([step / 3 for step in range(64)]
              if os.environ.get('USB_PHY_EXHAUSTIVE') == '1'
              else (0, 1 / 3, 1, 2, 8, 10.5, 16, 21))
    cases = 0
    failures = []
    for kind, packet, extras in (('ACK', b'\xd2', range(6)),
                                ('SETUP', setup, range(4))):
        for rate in (1499250, 1500000, 1500750):
            for width in (10.72, 64 / 3, 24):
                for extra in extras:
                    wave, legal = encode(packet, extra, rate, width)
                    for entry in phases:
                        errors = receive(art, kind, packet, wave, entry, legal)
                        if errors:
                            failures.append(dict(kind=kind, extra=extra, rate=rate,
                                                 width=width, entry=entry, errors=errors))
                        cases += 1
    return dict(bytes=art['size'], sha256=art['sha256'], cases=cases, failures=failures)


def test():
    import json
    art = h.build()
    report = check(art)
    destination = h.ROOT / 'build' / ('legal-dribble-' + art['sha256'][:16] + '.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print('Independent legal ACK/SETUP tails:', report['cases'], 'cases;',
          len(report['failures']), 'failures', flush=True)
    assert not report['failures'], ('Final-one acceptance/ownership', report['failures'][:4])


if __name__ == '__main__':
    test()
