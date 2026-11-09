"""Emit bounded byte-publication schedules for the EXTRA6 receiver.

These are real AVR unit schedules, not a complete packet receiver. The
unfunded final-one/run-zero and final-one/phase-zero entries are deliberately
absent. FIRST, SECOND and EXTRA remain at +0, +2 and +6 on normal DATA ones.
"""
from pathlib import Path
import argparse
import itertools
import json

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path, default=HERE / 'build')
args = parser.parse_args()
OUTPUT = args.output_dir.resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
serial = itertools.count()
meta = dict(entries={}, firsts={}, stops={}, tags={}, stores={})


def ins(s):
    return '    ' + s


def first(name, p, line, run):
    meta['firsts'][name] = dict(phase=p, line=line, run=run)
    return [name + ':', ins('in r16, 9')]


def stop(name, p, line, run, prefix):
    meta['stops'][name] = dict(phase=p, line=line, run=run, prefix=prefix)
    return first(name, p, line, run) + [ins('ret')]


def tag(name, kind):
    meta['tags'][name] = kind
    return [name + ':', ins('ret')]


def store(name):
    meta['stores'][name] = 23
    return [name + ':', ins('st Y+, r23')]


def prefix(name, p, line, run, delayed=False):
    """Consume the first new bit; delayed=True stores after one earlier bit."""
    other = 'K' if line == 'J' else 'J'
    expect = 20 if line == 'J' else 21
    np = (p + 1) % 3
    dif, zero, eop = (name + suffix for suffix in ('_different', '_zero', '_eop'))
    body = first(name, p, line, run) + [
        ins('andi r16, 6'), ins('in r17, 9'),
        ins(f'cpse r16, r{expect}'), ins('rjmp ' + dif)]
    cold = []
    if run == 6:
        body += tag(name + '_missing', 'missing_stuff')
    else:
        body += [ins('andi r17, 6'), ins('in r19, 9'), ins('breq ' + eop)]
        if delayed:
            body += [ins('asr r18')] + store(name + '_store_one')
            body += stop(name + '_next_one', np, line, run + 1, 'shift_one')
        else:
            body += [ins('ldi r18, 0xc0')]
            if p:
                body += store(name + '_store_one')
                body += stop(name + '_next_one', np, line, run + 1, 'seed_one')
            else:
                body += [ins('nop')]
                cp, cb = prefix(name + '_pending', np, line, run + 1, True)
                cold += cp
                body += cb
    cold += [dif + ':', ins('breq ' + zero)]
    if run == 6:
        cold += store(name + '_store_stuff')
        cold += [ins('nop') if delayed else ins('ldi r18, 0x80')]
        if p:
            cold += [ins('nop')]
        cold += stop(name + '_next_stuff', np, other, 0,
                     'retain_one' if delayed else 'seed_empty')
    else:
        cold += [ins('lsr r18') if delayed else ins('ldi r18, 0x40')]
        cold += store(name + '_store_zero')
        if p:
            cold += [ins('nop')]
        cold += stop(name + '_next_zero', np, other, 0,
                     'shift_zero' if delayed else 'seed_zero')
    # Cold EOP here is an observable unit stop. No ACK or packet admission.
    cold += [zero + ':'] + tag(eop, 'unqualified_eop')
    return cold, body


out = ['/* Offline unit fixture: no packet admission or hardware use. */',
       '    .text', '    .org BOOT_AT', '    .global bootloader_start',
       'bootloader_start:', 'USB_handler:', ins('ret')]
for p, line, run, bit in itertools.product(range(3), ('J', 'K'), range(6), (0, 1)):
    if bit and (p == 0 or run == 0):
        continue
    name = f'last_p{p}_{line}_r{run}_b{bit}'
    n = next(serial)
    other = 'K' if line == 'J' else 'J'
    following_line = line if bit else other
    following_run = run + 1 if bit else 0
    target = name + '_prefix'
    pre, follow = prefix(target, (p + 1) % 3, following_line, following_run)
    meta['entries'][name] = dict(phase=p, line=line, run=run, bit=bit)
    # The fixture entry models the actual final DATA-symbol classifier.
    main = first(name, p, line, run) + [ins('andi r16, 6'), ins('in r17, 9'),
        ins(f'cpse r16, r{20 if line == "J" else 21}'), ins('rjmp ' + name + '_different')]
    cold = []
    if bit:
        main += [ins('andi r17, 6'), ins('in r19, 9'), ins('breq ' + name + '_eop'),
                 ins('asr r18'), ins('brcc ' + name + '_not_full_one'),
                 ins('mov r23, r18')] + follow
        cold += stop(name + '_not_full_one', (p + 1) % 3, line, run + 1, 'not_full_one')
        cold += [name + '_different:'] + tag(name + '_wrong', 'outside_unit_entry_contract')
        cold += tag(name + '_eop', 'unqualified_eop')
    else:
        # FIRST differs, so RJMP arrives at +6; Z still describes FIRST.
        main += tag(name + '_wrong', 'outside_unit_entry_contract')
        cold += [name + '_different:', ins('breq ' + name + '_eop'),
                 ins('lsr r18'), ins('brcc ' + name + '_not_full_zero'),
                 ins('mov r23, r18')]
        if p:
            cold += [ins('nop')]
        cold += follow
        # BRCC taken arrives at +10. Phase1/2 retain the next clock at +11.
        cold += [name + '_not_full_zero:']
        if p:
            cold += [ins('nop')]
        cold += stop(name + '_not_full_zero_first', (p + 1) % 3, other, 0, 'not_full_zero')
        cold += tag(name + '_eop', 'unqualified_eop')
    out += pre + cold + main
out += ['usb_control_process_received_packet:', 'bootloader_poll_begin:',
        'bootloader_start_application:', ins('ret')]
(OUTPUT / 'publication.S').write_text('\n'.join(out) + '\n')
(OUTPUT / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
print(json.dumps(dict(entries=len(meta['entries']), source=str(OUTPUT / 'publication.S'))))
