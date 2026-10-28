"""Independent emitted NRZI/stuffing and upstream source-timing regression.

USB2 7.1.15.1 explicitly allows driver-jitter/clock-accuracy tradeoff; Table
7-10 upstream totals are 95/150 ns, not the downstream 25/14 ns limits.
These GPIO checks exclude pad/crossover skew and oscillator measurement.
"""
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_standard import Quiet

FREQUENCY = 16_000_000
NOMINAL_RATE = 1_500_000
PHASE = (0, 11, 22, 32, 43, 54, 64, 75)


def crc16(payload):
    """Independent reflected USB polynomial; firmware generates the wire CRC."""
    value = 0xffff
    for byte in payload:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return ((~value) & 0xffff).to_bytes(2, 'little')


def encoded(packet, run=0, line=2):
    """Construct physical symbols, inserting a zero even after a final bit six."""
    symbols = []; stuffed = []
    for byte in packet:
        for bit in range(8):
            one = (byte >> bit) & 1
            symbols.append(one); run = run + 1 if one else 0
            if run == 6:
                stuffed.append(len(symbols)); symbols.append(0); run = 0
    levels = []
    for bit in symbols:
        if not bit: line ^= 6
        levels.append(line)
    return levels, stuffed


def capture(art, pid, payload=None, ddr=0, port=0, flags=0, phase=0):
    bind(art); cpu = h.CPU(art, Quiet()); cpu.t = phase; cpu.flags = flags
    cpu.r[2] = 0
    cpu.io.update({10: ddr & ~6, 11: port & ~6})
    if payload is None:
        packet = bytes([pid]); cpu.r[20] = pid
        cpu.pc = cpu.labels['usb_tx_prepare_handshake']
    else:
        packet = bytes([pid]) + payload + crc16(payload)
        cpu.m[0x101:0x101+len(packet)] = packet
        cpu.r[28:30] = [1, 1]; cpu.r[19] = len(payload) + 4
        cpu.pc = cpu.labels['usb_tx_acquire_bus']
    outputs = []; ownership = []
    for _ in range(20000):
        if cpu.pc == 0xfffe: break
        before = cpu.io.get(10, 0) & 6
        instruction = cpu.step(); after = cpu.io.get(10, 0) & 6
        assert cpu.io.get(10, 0) & ~6 == ddr & ~6
        assert cpu.io.get(11, 0) & ~6 == port & ~6
        if before != after: ownership.append((cpu.t, before, after))
        if instruction.op == 'out' and instruction.operands.startswith('0xb,') and after == 6:
            outputs.append((cpu.t, cpu.io.get(11, 0) & 6))
    else: raise AssertionError('TX instruction bound')
    levels, stuff = encoded(b'\x80' + packet)
    assert [line for _, line in outputs] == levels + [0, 2], packet.hex()
    assert len(ownership) == 2 and ownership[0][1:] == (0, 6) and ownership[1][1:] == (6, 0)
    assert outputs[0][0] - ownership[0][0] == 6
    assert outputs[-1][0] - outputs[-2][0] == 21
    assert ownership[-1][0] - outputs[-1][0] == 11
    assert outputs[-2][0] - outputs[-3][0] == 11
    assert all(b[0] - a[0] in (10, 11) for a, b in zip(outputs[:-3], outputs[1:-2]))
    assert cpu.io.get(10, 0) == ddr & ~6 and cpu.io.get(11, 0) & 6 == 0
    assert cpu.word(28) == cpu.word(30) == 0x100 and cpu.r[1] == 0 and cpu.r[21] == 0xa0
    assert cpu.flag(6) == bool(flags & 64) and cpu.flag(7) == bool(flags & 128)
    return outputs, stuff


def byte_certificate(art):
    """Exhaust the present two-bit loop's byte/run phase, including final stuff.

    This certifies the schedule used by the finite edge graph below. A future
    retimed loop must update this certificate and retain the protocol bounds.
    """
    cases = 0
    for value in range(256):
        for run in range(6):
            bind(art); cpu = h.CPU(art, Quiet()); cpu.t = 0
            cpu.r[2] = 0; cpu.r[16] = 2; cpu.r[17] = (255 << (8-run)) & 255 if run else 0
            cpu.r[18] = value; cpu.r[19] = 2; cpu.r[21] = 6; cpu.r[28:30] = [1, 1]
            cpu.io.update({10: 6, 11: 2}); cpu.m[0x101] = 0x55
            cpu.pc = cpu.labels['usb_tx_begin_byte']; outputs = []; started = False
            for _ in range(2000):
                if started and cpu.pc == cpu.labels['usb_tx_begin_byte']: break
                started = True; instruction = cpu.step()
                if instruction.op == 'out' and instruction.operands.startswith('0xb,'):
                    outputs.append((cpu.t, cpu.io.get(11, 0) & 6))
            else: raise AssertionError('Byte instruction bound')
            levels, stuff = encoded(bytes([value]), run)
            assert [line for _, line in outputs] == levels
            physical = 0; seen = 0
            for bit in range(8):
                assert outputs[physical][0] == 4 + PHASE[bit] + 11 * seen
                physical += 1
                if physical in stuff:
                    assert outputs[physical][0] - outputs[physical-1][0] == 11
                    physical += 1; seen += 1
            assert physical == len(outputs) and cpu.t == 85 + 11 * seen
            cases += 1
    return cases


def edge_certificate():
    """Enumerate any next edge (up to six ones plus stuff), then its pair."""
    def base(position): return 85 * (position // 8) + PHASE[position % 8]
    def edge(position, ones):
        logical = ones + 1 if ones < 6 else 6
        clocks = base(position + logical) - base(position) + (11 if ones == 6 else 0)
        return (position + logical) % 8, ones + 1, clocks
    consecutive = set(); paired = set()
    for position in range(8):
        for ones in range(7):
            after, bits, clocks = edge(position, ones); consecutive.add((bits, clocks))
            for next_ones in range(7):
                _, more_bits, more_clocks = edge(after, next_ones)
                paired.add((bits + more_bits, clocks + more_clocks))
    errors = {}
    for name, samples, limit in (('next', consecutive, 95), ('paired', paired, 150)):
        values = [(clocks/FREQUENCY - bits/NOMINAL_RATE) * 1e9 for bits, clocks in samples]
        assert all(abs(value) <= limit for value in values), (name, min(values), max(values))
        errors[name] = [min(values), max(values)]
    # The last zero is no more than six logical positions from the byte end;
    # a required final stuffed zero is already included in this same graph.
    for position in range(2, 8):
        skew = ((86-PHASE[position])/FREQUENCY - (8-position)/NOMINAL_RATE) * 1e9
        assert -40 <= skew <= 100, (position, skew)
    assert 1_477_500 <= FREQUENCY/(299/28) <= FREQUENCY/(85/8) <= 1_522_500
    return errors


def check(art):
    payloads = {bytes([value])*length for value in (0, 255, 0x55, 0xaa) for length in range(9)}
    payloads.update(bytes([value])*8 for value in range(256))
    payloads.update(bytes([value]) for value in range(256))
    # Force a final-bit stuffed zero by independently finding CRC suffixes.
    for word in range(65536):
        payload = word.to_bytes(2, 'little')
        if crc16(payload)[1] in (0xfc, 0xfd): payloads.add(payload)
        if len([p for p in payloads if len(p)==2 and crc16(p)[1] in (0xfc,0xfd)]) >= 8: break
    cases = 0; final_stuff = 0
    for pid in (0xc3, 0x4b):
        for payload in sorted(payloads):
            outputs, stuff = capture(art, pid, payload)
            final_stuff += bool(stuff and stuff[-1] == len(outputs)-3)
            cases += 1
    for pid in (0xd2, 0x5a, 0x1e): capture(art, pid); cases += 1
    assert final_stuff
    masks = [value for value in range(256) if not value & 6]
    for index, ddr in enumerate(masks):
        capture(art, 0x4b, b'\xff'*8, ddr, masks[(index*17+5)%64], (index*37)&255, (index&3)/4)
    return dict(size=art['size'], sha256=art['sha256'], packets=cases,
                gpio_mask_cases=len(masks), final_stuffed_packets=final_stuff,
                byte_run_cases=byte_certificate(art), source_error_ns=edge_certificate())


def test():
    print(json.dumps(check(h.build()), indent=2), flush=True)


if __name__ == '__main__': test()
