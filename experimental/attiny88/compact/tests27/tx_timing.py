#!/usr/bin/env python3
"""Check emitted TX NRZI/stuffing and USB 2.0 digital timing limits.

Measurements assume exactly 16 MHz. Transition pairs follow Figure 7-49;
SE0 skew follows Figure 7-50. These finite sweeps exclude analog effects and
oscillator error. Source requirements and accepted protocol exceptions are in
docs/USB_TIMING.md and docs/USB_PROTOCOL.md.
"""
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests27 import cooperative_usb as model
from tests27.waveform_model import Wave, crc16, J


def trace(packet, handshake=False):
    """Drive the real PHY with a packet; capture every PORT and DDR write."""
    memory, registers = bytearray(0x300), [0] * 32
    pointer = 20 if handshake else 0x101
    memory[pointer:pointer + len(packet)] = packet
    if handshake:
        registers[20] = packet[0]
    registers[28:32] = [pointer & 255, pointer >> 8, 0, 1]
    registers[19] = len(packet) + 1  # Includes the generated SYNC byte.
    cpu = model.CPU(model.meta, {'memory': memory, 'registers': registers})
    cpu.flash = model.FlashView(cpu.flash, cpu.base)
    cpu.pc = cpu.labels['usb_tx_acquire_bus']
    cpu.calls.append(0xFFFE)
    cpu.io.update({9: J, 10: 0, 11: J, 0x1B: 0})
    writes, released = [], None
    for _ in range(10000):
        if cpu.pc == 0xFFFE:
            break
        instruction = cpu.step()
        if instruction.op == 'out' and instruction.operands.startswith('0xb,'):
            writes.append((cpu.t, cpu.io.get(11, 0) & 6))
        if instruction.op == 'out' and instruction.operands.startswith('0xa,'):
            if cpu.io.get(10, 0) & 6 == 0:
                released = cpu.t
    else:
        raise AssertionError('TX failed to return')
    se0 = next(i for i, (_, level) in enumerate(writes) if level == 0)
    samples, eop, idle = writes[:se0], writes[se0], writes[se0 + 1]
    expected = Wave(packet)
    assert [level for _, level in samples] == expected.levels[:-3], (
        'NRZI/stuffing mismatch', packet.hex())
    assert idle[1] == J and released - idle[0] == 11
    assert 20 <= idle[0] - eop[0] <= 24
    assert idle[0] - eop[0] == (22 if handshake else 23)
    assert cpu.r[28:30] == [0, 1] and cpu.r[21] == 0xA0
    edges = [0] + [i for i in range(1, len(samples))
                   if samples[i][1] != samples[i - 1][1]]
    # Integer thirds avoid rounding at rational 10 2/3-cycle bit boundaries.
    def error(right, left):
        return (3 * (samples[right][0] - samples[left][0])
                - 32 * (right - left)) * 62.5 / 3
    next_errors = [error(edges[i], edges[i - 1]) for i in range(1, len(edges))]
    pair_errors = [error(edges[i], edges[i - 2]) for i in range(2, len(edges))]
    skew = (3 * (eop[0] - samples[edges[-1]][0])
            - 32 * (len(samples) - edges[-1])) * 62.5 / 3
    assert all(-95 <= value <= 95 for value in next_errors), packet.hex()
    assert all(-150 <= value <= 150 for value in pair_errors), packet.hex()
    assert -40 <= skew <= 100, (packet.hex(), skew)
    return next_errors, pair_errors, skew


def check(artifact):
    """Cover valid packets and every byte/trailing-ones history combination."""
    model.configure(artifact)
    rng = random.Random(0x493B)
    payloads = [bytes([value]) * length for length in range(9)
                for value in (0, 255, 0x55, 0xAA, 0x81, 0x7E, 0x3F, 0xFC)]
    payloads += [rng.randbytes(rng.randrange(9)) for _ in range(500)]
    next_errors, pair_errors, skews = [], [], []
    count = 0
    def measure(packet, handshake=False):
        nonlocal count
        next_values, pairs, skew = trace(packet, handshake)
        next_errors.extend(next_values)
        pair_errors.extend(pairs)
        skews.append(skew)
        count += 1
    for payload in payloads:
        for pid in (0xC3, 0x4B):
            measure(bytes([pid]) + payload + crc16(payload))
    # These raw states exercise the generator, rather than packet CRC validity.
    for pid in (0xC3, 0x4B):
        for prefix in (0, 0x80, 0xC0, 0xE0, 0xF0, 0xF8):
            for byte in range(256):
                measure(bytes([pid, prefix, byte]))
    for pid in (0xD2, 0x5A):
        measure(bytes([pid]), handshake=True)
    print('PASS', artifact['mode'], count, 'TX waveform/state cases;',
          'next jitter ns', (min(next_errors), max(next_errors)),
          'paired ns', (min(pair_errors), max(pair_errors)),
          'SE0 skew ns', (min(skews), max(skews)), '; J 11 cycles')


if __name__ == '__main__':
    from build_candidate import checked_build
    from host import compact_programmer27 as host
    for mode, version in (('NONE', 0x0300), ('ACTIVE_HIGH', 0x0301), ('ACTIVE_LOW', 0x0302)):
        check(checked_build(mode, host.USB_PROFILES[version][1]))
