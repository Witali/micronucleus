"""Frozen, table-free RX CRC feasibility probes; no active source mutations.

The firmware originates from the GPL-2.0-or-later compact Micronucleus source.
This harness only builds isolated copies and records emitted machine-code data.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

OWN = Path(__file__).resolve().parent
ROOT = OWN.parents[1]
BASELINE_SHA256 = '8d77ea1e82f572f9c550171563573941391562db99c8d1441149503f78608c65'
sys.path.insert(0, str(ROOT))
from tests27.waveform_model import Timed, FlashView, Wave, SynchronizedPinIO, data_packet, token, dec


def run(command):
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(str(command) + '\n' + result.stderr)
    return result.stdout


def build(name, source, boot=0x1C00):
    path = OWN / (name + '.S')
    if path.name == 'baseline.S':
        # The supplied input is immutable, including its original LF bytes.
        if path.read_bytes() != source.encode('utf-8'):
            raise ValueError('Refusing to overwrite the pinned baseline')
    else:
        path.write_text(source, encoding='utf-8', newline='\n')
    reloc, elf, binary = [OWN / (name + suffix) for suffix in ('.o', '.elf', '.bin')]
    run(['clang', '-target', 'avr', '-mmcu=attiny88', '-c', '-x', 'assembler', str(path), '-o', str(reloc)])
    run(['avr-ld', '-m', 'avr25', '--defsym=__TEXT_REGION_LENGTH__=0x10000', '-Ttext=0', '-e', 'bootloader_start', '-o', str(elf), str(reloc)])
    assert not run(['llvm-nm', '--undefined-only', str(elf)]).strip()
    run(['llvm-objcopy', '-O', 'binary', '-j', '.text', str(elf), str(binary)])
    symbols = {}
    for line in run(['llvm-objdump', '-t', str(elf)]).splitlines():
        match = re.match(r'^([0-9a-f]+)\s+\S+\s+(?:\.text|\*ABS\*)\s+[0-9a-f]+\s+(.+)$', line)
        if match:
            symbols[match[2]] = int(match[1], 16)
    full = binary.read_bytes()
    body = full[boot:]
    body_path = OWN / (name + '_body.bin')
    body_path.write_bytes(body)
    meta = dict(name=name, start=boot, bin=body_path, o=elf, symbols=symbols, step_limit=20000)
    manifest = dict(name=name, bytes=len(body), body_sha256=hashlib.sha256(body).hexdigest(), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return meta, manifest


def freeze():
    """Require the supplied historical input; never copy a moving source."""
    path = OWN / 'baseline.S'
    if not path.exists():
        raise FileNotFoundError('Supply the pinned baseline.S from this experiment')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != BASELINE_SHA256:
        raise ValueError('Pinned baseline.S SHA256 mismatch; do not regenerate it')
    return content.decode('utf-8')


def receive(meta, packet, entry=20, rate=1_500_000, jitter=None, trace=False):
    wave = Wave(packet, rate=rate, jitter=jitter)
    raw_decode = getattr(dec.decode, '__wrapped__', dec.decode)
    dec.decode = lru_cache(maxsize=16384)(raw_decode)
    cpu = Timed(meta, {'memory': bytearray(0x300), 'registers': [0] * 32})
    cpu.flash = FlashView(cpu.flash, cpu.base)
    cpu.pc = cpu.labels['USB_handler']
    cpu.calls = [0xFFFF]
    cpu.t = entry
    cpu.r[29] = 1
    cpu.r[0], cpu.r[24], cpu.r[25] = 0xA5, 0x5A, 0xC3
    cpu.r[26:28] = [0x34, 0x12]
    cpu.io = SynchronizedPinIO(cpu, wave)
    history = []
    result = None
    peak_stack = 2
    for _ in range(6000):
        if cpu.pc == cpu.labels['usb_rx_end_packet']:
            count = (11 - cpu.r[23]) & 255
            actual = bytes(cpu.m[0x116:0x116 + count])
            result = dict(ok=actual == packet, reason='match' if actual == packet else 'wrong bytes', actual=actual.hex(), expected=packet.hex(), cycles=cpu.t)
            break
        if cpu.pc in (0xFFFF, cpu.labels['usb_rx_overflow']):
            result = dict(ok=False, reason='overflow' if cpu.pc != 0xFFFF else 'no packet', cycles=cpu.t)
            break
        cpu.executing_pc = cpu.pc
        instruction = cpu.step()
        peak_stack = max(peak_stack, 2 * len(cpu.calls) + len(cpu.push_stack))
        if trace:
            history.append(dict(time=cpu.t, pc=cpu.executing_pc, op=instruction.op, operands=instruction.operands))
    if result is None:
        result = dict(ok=False, reason='instruction limit', cycles=cpu.t)
    result['preserved'] = cpu.r[0] == 0xA5 and cpu.r[1] == 0 and cpu.r[24:26] == [0x5A, 0xC3] and cpu.r[26:28] == [0x34, 0x12]
    result['peak_standalone_stack_bytes'] = peak_stack
    if trace:
        result['samples'], result['history'] = cpu.io.samples, history
    return result


def insertion(source, shared=False):
    """A compact inline streaming LFSR; intentionally test the timing cost.

    R19:R2 = alternate CRC state; ZL = polynomial high A0, ZH = low 01.
    NRZI SUBI already produced the decoded carry. LSL restores that carry
    from the dead FF/05 difference register before the original ROR R18.
    This avoids both an input-bit XOR and an additional bit-save register.
    """
    source = source.replace('ldi r30, ((0x100) & 0xff)', 'ldi r30, 0xa0', 1)
    # The preprocessed assembler uses numeric-expanded context expressions.
    start = source.index('usb_rx_sync_confirmed:')
    end = source.index('usb_rx_delay_complete:')
    header = source[start:end]
    header = re.sub(r'ldi r30,.*', 'ldi r30, 0xa0', header, count=1)
    source = source[:start] + header + source[end:]
    index = 0
    for temporary in ('r17', 'r16'):
        pattern = f'subi {temporary}, 0x01\nror r18'
        update = ('rcall rx_crc_step\n' if shared else
                  f'ror r19\nror r2\nbrcc .Lcrc_skip_{index}\n'
                  f'eor r2, r31\neor r19, r30\n.Lcrc_skip_{index}:\n')
        replacement = f'subi {temporary}, 0x01\n' + update + f'lsl {temporary}\nror r18'
        count = source.count(pattern)
        # There are two identical operand sites per odd/even pin register.
        while pattern in source:
            replacement = replacement.replace(f'.Lcrc_skip_{index}', f'.Lcrc_skip_{index + 1}')
            index += 1
            source = source.replace(pattern, replacement, 1)
        assert count == 2, (temporary, count)
    assert index == 4
    # Finish the prototype as a real DATA CRC checker, not a timing-only marker.
    # Reset after PID so neither SYNC nor PID contributes to the residue.
    marker = 'st Y+, r20\n'
    assert source.count(marker) == 1
    source = source.replace(marker, marker + 'cpi r28, 23\nbrne .Lcrc_payload\nldi r19, 0x15\nldi r30, 0x57\nmov r2, r30\nldi r30, 0xa0\n.Lcrc_payload:\n', 1)
    source = source.replace('usb_rx_end_packet:\n', 'usb_rx_end_packet:\neor r30, r30\n', 1)
    # Every overflow also restores Z's context low byte before token cleanup.
    source = source.replace('usb_rx_overflow:\n', 'usb_rx_overflow:\neor r30, r30\n', 1)
    source = source.replace('usb_rx_handle_data:\n', 'usb_rx_handle_data:\ncom r2\ncom r19\nor r19, r2\nbrne usb_rx_ignore_packet\n', 1)
    if shared:
        source += '\nrx_crc_step:\nror r19\nror r2\nbrcc .Lcrc_step_done\neor r2, r31\neor r19, r30\n.Lcrc_step_done:\nret\n'
        pattern = 'brbs 1, usb_rx_end_packet\n'
        source = source.replace(pattern, 'brbc 1, .Lshared_eop_continue\nrjmp usb_rx_end_packet\n.Lshared_eop_continue:\n', 1)
    else:
        # The inline copy also pushes five old 7-bit branches out of range.
        # Expand each affected conditional explicitly; do not accept truncated
        # relocations or pretend that their additional cycles are free.
        for number, (op, flag, target) in enumerate([
            ('brbs', 1, 'usb_rx_end_packet'),
            ('brbc', 0, 'usb_rx_unstuff_even_bit'),
            ('brbc', 0, 'usb_rx_unstuff_odd_bit'),
            ('brbs', 0, 'usb_rx_sample_even_bit'),
            ('brbc', 0, 'usb_rx_decode_bit6')]):
            pattern = f'{op} {flag}, {target}\n'
            inverse = 'brbc' if op == 'brbs' else 'brbs'
            count = 0
            while pattern in source:
                label = f'.Llong_{number}_{count}'
                source = source.replace(pattern, f'{inverse} {flag}, {label}\nrjmp {target}\n{label}:\n', 1)
                count += 1
    return source


if __name__ == '__main__':
    source = freeze()
    baseline, before = build('baseline', source)
    assert before['bytes'] == 1144, before
    print(before)
    reports = []
    for shared in (False, True):
        name = 'shared_crc' if shared else 'inline_crc'
        candidate_source = insertion(source, shared)
        try:
            candidate, after = build(name, candidate_source)
        except RuntimeError as error:
            (OWN / (name + '-build-error.txt')).write_text(str(error))
            raise
        rows = []
        for packet_name, packet in [('zero8', data_packet(bytes(8))), ('ff8', data_packet(bytes([255]) * 8)), ('ramp8', data_packet(bytes(range(8)))), ('empty', data_packet(b'', 0x4B))]:
            for phase in (5, 20, 30, 40):
                a, b = receive(baseline, packet, phase), receive(candidate, packet, phase)
                rows.append(dict(packet=packet_name, entry=phase, baseline=a, candidate=b))
        reports.append(dict(before=before, after=after, delta_bytes=after['bytes'] - before['bytes'], cases=rows))
        print(after, 'delta', after['bytes'] - before['bytes'])
        print('baseline', sum(r['baseline']['ok'] for r in rows), 'candidate', sum(r['candidate']['ok'] for r in rows), 'of', len(rows))
    (OWN / 'insertion-results.json').write_text(json.dumps(reports, indent=2) + '\n')
