#!/usr/bin/env python3
"""Replay the bounded, native-clock V-USB16 RX/TX audit without retiming.

This preserves the original 162 RX and seven TX probe loops. Artifact
identities, raw GPIO observations and persistent JSON output are retained.
The existing model and encoders are imported unchanged from --model-root.
Exit 1 means a mandatory receiver or transmitter timing requirement failed.
This is a digital instruction/GPIO probe, not full-stack USB certification.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True

PINNED_SHA256 = 'd02ace1a8ed3538071ec8016dfe0090c240af048292e928b62a0649fa31c879a'
F_CPU = 16_000_000
ROOT = Path(__file__).resolve().parents[1]


def local_path(value, manifest):
    """Resolve the measurement's path on its original host or Windows/WSL."""
    text = str(value)
    if os.name == 'nt' and text.startswith('/mnt/') and len(text) > 7:
        text = text[5].upper() + ':/' + text[7:]
    path = Path(text)
    if not path.is_absolute():
        path = manifest.parent / path
    if path.exists():
        return path
    # Artifacts may be moved together without preserving their original root.
    sibling = manifest.parent / Path(str(value)).name
    if sibling.exists():
        return sibling
    raise FileNotFoundError(path)


def load_artifact(manifest):
    source = json.loads(manifest.read_text(encoding='utf-8'))
    binary = local_path(source['bin'], manifest)
    obj = local_path(source['obj'], manifest)
    body = binary.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    assert source['boot'] == 0, 'The original native probe loads at address zero'
    assert source['size'] == len(body) == 1178
    assert digest == source['sha256'] == PINNED_SHA256
    assert hashlib.sha256(obj.read_bytes()).hexdigest() == source['elf_sha256']
    assert source['config']['USB_CFG_CLOCK_KHZ'] == 16000
    assert source['config']['USB_CFG_IOPORTNAME'] == 'D'
    assert source['config']['USB_CFG_DMINUS_BIT'] == 1 and source['config']['USB_CFG_DPLUS_BIT'] == 2
    symbols = {name: value & 0x7fffff for name, value in source['symbols'].items()}
    # Constructor-only entry aliases; no instruction or model is replaced.
    for name in ('USB_handler', 'usb_control_process_received_packet',
                 'bootloader_poll_begin', 'bootloader_start_application'):
        symbols[name] = symbols['__vector_1']
    return dict(boot=0, obj=obj, bin=binary, symbols=symbols), source, digest


def rx_probe(artifact, h, eop_wave):
    symbols = artifact['symbols']
    packets = [b'\xd2', h.token(0x69), h.token(0x2d), h.token(0xe1),
               h.data_packet(bytes(8)), h.data_packet(bytes([255]) * 8)]
    results = []
    first_failure = None
    for packet in packets:
        for rate in (1499250, 1500000, 1500750):
            for entry in (6, 7, 8):
                for width in (10.72, 32_000_000 / rate, 24):
                    wave = eop_wave(packet, width, rate)
                    cpu = h.CPU(artifact, wave, entry)
                    cpu.m[symbols['usbTxLen']] = 0x5a
                    for _ in range(10000):
                        if cpu.pc in (symbols['se0'], symbols['overflow'], symbols['sofError']):
                            break
                        cpu.step()
                    else:
                        raise AssertionError(('RX instruction bound', packet.hex(), entry, rate, width))
                    received = bytes(cpu.m[symbols['usbRxBuf']:cpu.word(28)])
                    stop = next(name for name in ('se0', 'overflow', 'sofError')
                                if cpu.pc == symbols[name])
                    row = dict(packet=packet.hex(), rate=rate, entry=entry, width=width,
                               stop=stop, correct=stop == 'se0' and received == packet,
                               received=received.hex(), at=cpu.t)
                    results.append(row)
                    if first_failure is None and not row['correct']:
                        first_failure = dict(row, samples=cpu.io.samples[-15:])
    assert len(results) == 162
    summary = []
    for kind in ('short', 'nominal', 'long'):
        rows = [row for row in results if
                (row['width'] == 10.72 if kind == 'short' else
                 row['width'] == 24 if kind == 'long' else
                 row['width'] not in (10.72, 24))]
        summary.append(dict(kind=kind, total=len(rows), correct=sum(row['correct'] for row in rows),
                            stops={name: sum(row['stop'] == name for row in rows)
                                   for name in ('se0', 'overflow', 'sofError')}))
    return dict(cases=len(results), by_width=summary, first_failure=first_failure, results=results)


class Quiet:
    pin_edges = []

    def level(self, time):
        return 2

    def cell(self, time):
        return 'idle'


def tx_probe(artifact, h, encoded):
    symbols = artifact['symbols']
    results = []
    packets = [b'\xd2', b'\x5a', b'\x1e', h.data_packet(bytes(8)),
               h.data_packet(bytes([255]) * 8), h.data_packet(bytes([0x55]) * 8),
               h.data_packet(bytes([0xaa]) * 8)]
    for packet in packets:
        cpu = h.CPU(artifact, Quiet(), 0)
        cpu.m[symbols['usbTxLen']] = 0x5a
        if len(packet) == 1:
            cpu.r[20] = packet[0]
            cpu.pc = symbols['sendX3AndReti']
        else:
            ptr = symbols['usbTxBuf']
            cpu.m[ptr:ptr + len(packet)] = packet
            cpu.setword(28, ptr)
            cpu.r[19] = len(packet) + 1
            cpu.pc = symbols['usbSendAndReti']
        outputs = []
        byte_starts = []
        for _ in range(10000):
            if cpu.pc == symbols['doReturn']:
                break
            if cpu.pc == symbols['txByteLoop']:
                byte_starts.append(cpu.t)
            instruction = cpu.step()
            if (instruction.op in ('out', 'sbi', 'cbi')
                    and instruction.operands.startswith('0xb,')
                    and cpu.io.get(10, 0) & 6 == 6):
                outputs.append((cpu.t, cpu.io.get(11, 0) & 6))
        else:
            raise AssertionError('TX instruction bound')
        levels, stuffed = encoded(b'\x80' + packet)
        assert [value for time, value in outputs] == levels + [0, 2], (packet.hex(), outputs)
        release = next(time for time, io, value in reversed(cpu.bus_events)
                       if io == 10 and value & 6 == 0)
        results.append(dict(
            packet=packet.hex(), correct_symbols=True, stuffed_symbols=len(stuffed),
            sync_output_offsets=[time - outputs[0][0] for time, value in outputs[:8]],
            byte_start_deltas=[later - earlier for earlier, later in zip(byte_starts, byte_starts[1:])],
            last_bit_to_se0=outputs[-2][0] - outputs[-3][0],
            se0_clocks=outputs[-1][0] - outputs[-2][0],
            driven_j_clocks=release - outputs[-1][0],
            # Preserve raw observations in addition to the original summaries.
            portd_writes_while_driving=outputs, byte_start_clocks=byte_starts,
            changed_gpio_events=cpu.bus_events, ddr_release_clock=release,
            stop_pc=cpu.pc, stop_clock=cpu.t))
    assert len(results) == 7
    return dict(cases=len(results), results=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', type=Path, required=True,
                        help='Native-toggle0 artifact.json from the portable measurement')
    parser.add_argument('--model-root', type=Path, default=ROOT,
                        help='Existing experimental/attiny88/flash_only directory')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/vusb16-probe',
                        help='Directory for rx-results.json and tx-results.json')
    args = parser.parse_args()
    if any((args.output / name).exists() for name in ('rx-results.json', 'tx-results.json')):
        parser.error('Completed probe output exists; choose a fresh directory')
    artifact, source, digest = load_artifact(args.artifact.resolve())
    sys.path.insert(0, str(args.model_root.resolve()))
    from tests35 import ep0_model as h
    from tests35.phy_model import eop_wave
    from tests35.test_tx_digital import encoded

    common = dict(
        artifact_sha256=digest, artifact_size=source['size'], cpu_hz=F_CPU,
        qualified=False,
        scope='Unchanged native opcodes and existing digital model; bounded RX/TX only. '
              'No full-stack, ISR-return, analog or electrical certification.',
        model_root=str(args.model_root.resolve()), artifact_manifest=str(args.artifact.resolve()))
    rx = dict(common, **rx_probe(artifact, h, eop_wave))
    tx = dict(common, **tx_probe(artifact, h, encoded))
    # Derive the rate from emitted byte-entry clocks, not a hard-coded calendar.
    periods = sorted({delta for row in tx['results'] if row['stuffed_symbols'] == 0
                      for delta in row['byte_start_deltas']})
    assert periods and min(periods) > 0, 'No observed unstuffed-byte period'
    rates = [F_CPU * 8 / period for period in periods]
    tx['observed_unstuffed_periods'] = periods
    tx['observed_unstuffed_rates'] = rates
    assert hashlib.sha256(artifact['bin'].read_bytes()).hexdigest() == digest
    assert hashlib.sha256(artifact['obj'].read_bytes()).hexdigest() == source['elf_sha256']
    args.output.mkdir(parents=True, exist_ok=True)
    for name, report in (('rx-results.json', rx), ('tx-results.json', tx)):
        (args.output / name).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(rx_cases=rx['cases'], rx_by_width=rx['by_width'],
                          tx_cases=tx['cases'], tx_symbols_correct=True,
                          tx_unstuffed_periods=periods, tx_unstuffed_rates=rates,
                          tx_driven_j_clocks=[row['driven_j_clocks'] for row in tx['results']],
                          qualified=False), indent=2))
    return int(any(not row['correct'] for row in rx['results'])
               or any(not 1_477_500 <= rate <= 1_522_500 for rate in rates)
               or any(not 20 <= row['se0_clocks'] <= 24 for row in tx['results'])
               or any(row['driven_j_clocks'] < 32 / 3 for row in tx['results']))


if __name__ == '__main__':
    raise SystemExit(main())
