"""Audit the pinned USBtiny receive excerpt at its native 12 MHz.

Only a software model is executed. This is not a port or a programming image.
An observed 670 ns receiver EOP is compared with nominal/full-width controls.
A failed receiver requirement returns nonzero, even for a known reference.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests35 import ep0_model as h
from tests35.phy_model import eop_wave

COMMIT = '6895f68e2bbfbd90287eb654abc3c5a70027148f'
SOURCE_BLOB = '5cd75ad6e76422262cd732fc7390075b29a5c626'
SOURCE_URL = f'https://raw.githubusercontent.com/rgwan/USBtiny/{COMMIT}/usbtiny/int.S'
SOURCE_PAGE = f'https://github.com/rgwan/USBtiny/blob/{COMMIT}/usbtiny/int.S'
F_CPU = 12_000_000


def load_source(args):
    """Read only the exact reviewed public source, preserving its attribution."""
    if args.source is not None:
        if args.source.stat().st_size > 65536:
            raise ValueError('Expected the small pinned USBtiny source')
        body = args.source.read_bytes()
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
            body = response.read(65537)
    identity = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
    if len(body) > 65536 or identity != SOURCE_BLOB:
        raise ValueError('USBtiny source differs from the pinned public Git blob')
    cache = ROOT / 'build/external_usb/usbtiny-int.S'
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(body)
    return body.decode('utf-8')


def fixture(text):
    """Keep the actual eight-bit loop/stuffers; expand only GNU aliases.

    Native-clock IRQ/SYNC prologue and packet dispatch are deliberately outside
    this component. It is given a correctly centered first PID observation.
    """
    begin = text.index('\tin\teven, USB_IN\t\t; sample bit 0')
    end = text.index('; end-of-packet detected', begin)
    core = text[begin:end]
    core = re.sub(r'\bcbr\s+byte,\s*\(1<<7\)', 'andi byte, 0x7f', core)
    core = re.sub(r'\bsbr(\s+)', r'ori\1', core)
    return '''#define count r16
#define usbmask r17
#define odd r18
#define byte r19
#define fixup r20
#define even r22
#define USB_IN 9
#define USB_MASK 6
#define nop2 rjmp .+0
    .text
    .org BOOT_AT
    .global bootloader_start
bootloader_start:
USB_handler:
''' + core + '''
eop2:
    ret
ignore:
usb_control_process_received_packet:
bootloader_poll_begin:
bootloader_start_application:
    ret
'''


def exercise(art):
    """Execute emitted words using 12 MHz ticks and real packet bit lengths."""
    packets = [bytes([0xd2]), h.token(0x69), h.token(0x2d), h.token(0xe1),
               h.data_packet(bytes(8))]
    results = []
    for packet in packets:
        for rate in (1499250, 1500000, 1500750):
            period = F_CPU / rate
            for phase in (3, 4, 5):
                for name, width in (('minimum_receiver_eop', .670e-6 * F_CPU),
                                    ('nominal_two_bits', 2 * period),
                                    ('source_upper_eop', 1.5e-6 * F_CPU)):
                    # Wave's rate parameter is a 16 MHz tick-to-period factory.
                    # Scale that parameter; actual times here are 12 MHz ticks.
                    wave = eop_wave(packet, width, rate=16_000_000 / period)
                    cpu = h.CPU(art, wave, 8 * period + phase + .5)
                    cpu.r[16:23] = [11, 6, h.K, 0, 0, 0, 0]
                    cpu.r[28:30] = [0x16, 1]
                    for _ in range(5000):
                        if cpu.pc in (cpu.labels['eop2'], cpu.labels['ignore']):
                            break
                        cpu.step()
                    else:
                        raise AssertionError('USBtiny core instruction bound')
                    reached = cpu.pc == cpu.labels['eop2']
                    published = bytes(cpu.m[0x116:cpu.word(28)])
                    results.append(dict(packet=packet.hex(), physical_rate=rate,
                                        pid0_phase=phase, input_eop=name,
                                        eop_cycles=width, reached_eop=reached,
                                        correct_packet=reached and published == packet,
                                        published=published.hex()))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--source', type=Path, help='Previously downloaded pinned int.S')
    source.add_argument('--download', action='store_true', help='Download the pinned public int.S')
    args = parser.parse_args()
    emitted = fixture(load_source(args))
    directory = ROOT / 'build/external_usb/usbtiny_probe'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'micronucleus_t88_compact.S').write_text(emitted)
    art = h.build(source='build/external_usb/usbtiny_probe', boot=0x1b00)
    assert art['size'] == 236 and art['sha256'] == (
        '863392d65fe03828fc7c0e54d941f3520e4f88f0381055007eb74a3e4cafce40')
    results = exercise(art)
    failures = sum(not row['correct_packet'] for row in results)
    report = dict(source=SOURCE_PAGE, git_blob=SOURCE_BLOB, cpu_hz=F_CPU,
                  core_bytes=art['size'], sha256=art['sha256'], cases=len(results),
                  failures=failures, qualified=False, results=results,
                  scope='Receive excerpt only, ideal native-clock SYNC phase; no protocol/vector port.')
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    for name in ('minimum_receiver_eop', 'nominal_two_bits', 'source_upper_eop'):
        rows = [row for row in results if row['input_eop'] == name]
        print(name, ':', sum(row['correct_packet'] for row in rows), '/', len(rows),
              'correct packets', flush=True)
    print('Mandatory receiver failures:', failures, '; this reference is not qualified')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
