"""Export actual-opcode USB probes for the independent MicroMusic executor.

Run with the existing tests35 toolchain. Generated data is an offline model
comparison, never a substitute for each USB acceptance/timing oracle.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import from_bits
TIMING = sys.modules[h.SynchronizedPinIO.__module__]


def crc5(field):
    state = 31
    for _ in range(11):
        feedback = (state ^ field) & 1
        state >>= 1
        if feedback:
            state ^= 20
        field >>= 1
    return state ^ 31


def token(pid, address, endpoint=0, flip=0):
    field = address | (endpoint << 7)
    return bytes([pid]) + (field | ((crc5(field) ^ flip) << 11)).to_bytes(2, 'little')


def artifact(path):
    if not path:
        return h.build()
    filename = Path(path).resolve()
    art = json.loads(filename.read_text(encoding='utf-8-sig'))
    for key in ('obj', 'bin'):
        p = Path(art[key])
        art[key] = p if p.is_absolute() else filename.parent / p
    art['body'] = art['bin'].read_bytes()
    assert hashlib.sha256(art['body']).hexdigest() == art['sha256'], 'Artifact hash mismatch'
    assert len(art['body']) == art['size'], 'Artifact size mismatch'
    return art


def make_case(art, name, bits, rate, width, entry, memory=None, registers=None, wire=None):
    wire = wire if wire is not None else from_bits(bits, rate=rate, width=width)
    cpu = h.CPU(art, wire, entry)
    cpu.m[0x10f] = 0x5a
    for address, value in (memory or {}).items():
        cpu.m[address] = value
    for reg, value in (registers or {}).items():
        cpu.r[reg] = value
    names = [label for label in ('usb_rx_end_packet', 'usb_rx_handle_in',
             'usb_rx_handle_setup_or_out', 'usb_rx_handle_data', 'usb_rx_accept_ack')
             if label in art['symbols']]
    labels = {art['symbols'][label]: label for label in names}
    checkpoints = []
    for _ in range(30000):
        if cpu.pc == 0xfffe:
            break
        if cpu.pc in labels:
            checkpoints.append(dict(label=labels[cpu.pc], time=cpu.t,
                                    count=cpu.r[23], Y=cpu.word(28)))
        cpu.step()
    else:
        raise AssertionError(('Handler did not return', name))
    assert not cpu.raw_stack, ('Unbalanced reference stack', name)
    return dict(name=name, wave=dict(boundaries=wire.boundaries, levels=wire.levels,
                labels=wire.labels, start=wire.start, end=wire.end), entry=entry,
                flagPriority='set' if TIMING.CLEAR_SET_WINS else 'clear',
                aperture=TIMING.APERTURE, flagDriver='external', checkpoints=names,
                memory=memory or {}, registers=registers or {},
                expected=dict(cycles=cpu.t, registers=cpu.r, sreg=cpu.flags,
                    memory=list(cpu.m[0x100:0x12c]), events=cpu.bus_events,
                    pinReads=cpu.io.samples, checkpoints=checkpoints))


def generate(art, dense=False, jitter=False):
    bind(art)
    cases = []
    rates = (1499250, 1500000, 1500750) if dense else (1500000,)
    entries = (8, 8.25, 8.5, 8.75, 16) if dense else (8, 8.25)
    for active in (0, 1, 63, 127):
        for pid in (0x69, 0x2d, 0xe1):
            for endpoint, flip in ((0, 0), (1, 0), (0, 1)):
                packet = token(pid, active, endpoint, flip)
                bits = h.Wave(packet).bits
                for rate in rates:
                    for entry in entries:
                        for width in (10.72, 32_000_000 / rate, 24):
                            name = f'token-{packet.hex()}-{rate}-{entry}-{width}'
                            cases.append(make_case(art, name, bits, rate, width, entry,
                                {0x10c: active}, {8: crc5(active) << 3}))
    # Successful SETUP publication, status DATA, invalid tail/truncation, and
    # ACK ownership all run through the same CPU hooks. Flash SPM is excluded.
    for payload in (bytes([0x40, 3, 0, 0, 0x80, 0, 0, 0]), bytes([0xff] * 8)):
        packet = h.data_packet(payload, 0xc3)
        bits = h.Wave(packet).bits
        for tail in ([], [1], [1] * 6, [0], [0, 1]):
            for rate in rates:
                for entry in entries:
                    cases.append(make_case(art, f'data-{packet.hex()}-{tail}-{rate}-{entry}',
                        bits + tail, rate, 10.72, entry, {0x114: 0x2d}, {24: 0xa5, 25: 0xb6}))
        for missing in (1, 4, 8):
            cases.append(make_case(art, f'truncated-{packet.hex()}-{missing}',
                bits[:-missing], 1500000, 64 / 3, 8, {0x114: 0x2d}))
    for tail in ([], [1], [1] * 4, [0], [1] * 7):
        cases.append(make_case(art, f'ack-{tail}', h.Wave(b'\xd2').bits + tail,
            1500000, 64 / 3, 8, {0x10f: 12, 0x113: 0x24}, {2: 12}))
    if jitter:
        from tests35.rx_jitter_patterns import corners
        from tests35.phy_model import eop_wave
        payload = bytes([0xff] * 8)
        vectors = [(token(0x69, 0), {}, {}),
                   (token(0x69, 63), {0x10c: 63}, {8: crc5(63) << 3}),
                   (h.data_packet(payload, 0xc3), {0x114: 0x2d}, {})]
        for packet, memory, registers in vectors:
            for rate in rates:
                for width in (10.72, 32_000_000 / rate, 24):
                    for corner, wire in enumerate(corners(eop_wave(packet, width, rate))):
                        for entry in entries:
                            cases.append(make_case(art,
                                f'jitter-{packet.hex()}-{rate}-{width}-{corner}-{entry}',
                                None, rate, width, entry, memory, registers, wire=wire))
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', help='Frozen build metadata; default builds current source')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--dense', action='store_true', help='All three rate extremes and five phases')
    parser.add_argument('--jitter', action='store_true', help='Add certified 75/45 ns input-edge corners')
    args = parser.parse_args()
    art = artifact(args.artifact)
    cases = generate(art, args.dense, args.jitter)
    metadata = {key: art[key] for key in ('boot', 'bin', 'size', 'sha256', 'symbols')}
    metadata['bin'] = str(metadata['bin'])
    output = dict(schema='micronucleus-micromusic-usb-v1', artifact=metadata,
                  reference='tests35 actual-opcode model; synchronized PIN input', cases=cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'Exported {len(cases)} CPU/wire comparisons; body {art["size"]} B, SHA256 {art["sha256"]}')


if __name__ == '__main__':
    main()
