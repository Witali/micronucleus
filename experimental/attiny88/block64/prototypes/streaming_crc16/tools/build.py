#!/usr/bin/env python3
"""Build an isolated, read-only USB application; never programs hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import re
import subprocess

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
sys.path.insert(0, str(PROJECT/'tools'))
from avr_build import assemble
from crc_tables import render_assembly
from ack_optimizations import MODES, FROZEN_V2, transform

ORIGIN = 0x0800
PROTECTED_BOOT = 0x1B00
APPLICATION_END = PROTECTED_BOOT-4


def record(address, data, kind=0):
    raw = bytes([len(data), address>>8, address&255, kind])+data
    return ':'+(raw+bytes([(-sum(raw))&255])).hex().upper()


def build(receiver, output, ack_mode='immediate'):
    if ack_mode not in MODES or (ack_mode != 'immediate' and receiver != 'streaming-v2'):
        raise ValueError('ACK experiments require the streaming-v2 receiver')
    output.mkdir(parents=True, exist_ok=True)
    for path in (PROJECT/'source').glob('*.inc'):
        shutil.copyfile(path, output/path.name)
    main = (PROJECT/'source/micronucleus_t88_block64.S').read_text()
    # Diagnostic applications must not program either NVM, even if a mutation
    # handler is accidentally reached. Keep instruction width unchanged.
    main = main.replace('block_vendor_out:\n', 'block_vendor_out:\n    rjmp block_vendor_reject\n')
    main, spm_count = re.subn(r'(?m)^\s+spm\s*$', '\n    nop', main)
    main, ee_count = re.subn(r'(?m)^    sbi\s+T88_IO_EECR, 1\s*$', '    nop', main)
    assert spm_count == 3 and ee_count == 1
    autoexit = '    brne    L1eac\n'
    assert main.count(autoexit) == 1
    # An application trial has no bootloader postscript at ORIGIN-4. Never
    # depend on erased bytes there to suppress the inherited inactivity jump.
    main = main.replace(autoexit, 'prototype_disabled_autoexit:\n    nop\n')
    bound = '''#if (BOOT_AT & 0xff) != 64
    ldi     r20, (BOOT_AT & 0xff)
#endif
    ldi     r21, (BOOT_AT >> 8)'''
    assert main.count(bound) == 1
    main = main.replace(bound, '    ldi     r20, 0\n    ldi     r21, 0x20')
    main = '#define BOOT_AT 0x0800\n#define T88_ASSUME_RESET_STACK_INIT 0\n'+main
    main += '\nprototype_code_end:\n'
    if receiver.startswith('streaming'):
        sampler = BASE/'source'/('streaming_rx_v2.inc' if receiver == 'streaming-v2' else 'streaming_rx.inc')
        if not sampler.exists():
            raise RuntimeError('Streaming receiver prototype source is not ready')
        if ack_mode != 'immediate' and hashlib.sha256(sampler.read_bytes()).hexdigest() != FROZEN_V2:
            raise RuntimeError('ACK experiments require the audited frozen V2 source')
        shutil.copyfile(sampler, output/'streaming_rx.inc')
        phy = (output/'vusb_phy.inc').read_text()
        first, last = phy.index('USB_handler:\n'), phy.index('L1baa:\n')
        phy = phy[:first]+'#include "streaming_rx.inc"\n'+phy[last:]
        dispatch = '    cpi     r16, USB_PID_ACK\n'
        assert phy.count(dispatch) == 1
        phy = phy.replace(dispatch, 'stream_nondata_dispatch:\n'+dispatch)
        (output/'vusb_phy.inc').write_text(phy)
        empty = (output/'vusb_empty_data.inc').read_text()
        repeated_crc = '''    ldd     r16, Y+1             /* CRC low byte for an empty payload */
    ldd     r17, Y+2             /* CRC high byte */
    or      r16, r17
    brne    usb_rx_empty_invalid'''
        assert empty.count(repeated_crc) == 1
        # This classifier is reached only after the full DATA residual passed.
        # Keep DATA1/OUT guards; do not repeat the six-clock empty CRC check.
        empty = empty.replace(repeated_crc, '    /* DATA CRC already validated by the streaming sampler. */')
        minimum_length = '''    cpi     r19, 3
    brne    usb_rx_empty_invalid'''
        assert empty.count(minimum_length) == 1
        # With exact CRC/counter agreement, a FFFF-seeded B001 residual is
        # impossible with fewer than two post-PID bytes. The caller enters
        # here only for count<4, so count==3 follows. The arithmetic and
        # 48,864 actual short-frame cases establish this implication in V2;
        # the context/deferred modes independently verify normalized Y=0100.
        empty = empty.replace(minimum_length, '    /* Full DATA residual proves decoded count >=3. */')
        if ack_mode != 'immediate':
            sampler_text, phy, empty = transform(sampler.read_text(), phy, empty, ack_mode)
            (output/'streaming_rx.inc').write_text(sampler_text)
            (output/'vusb_phy.inc').write_text(phy)
            if ack_mode == 'deferred':
                shutil.copyfile(BASE/'source/streaming_ack_publish.inc', output/'streaming_ack_publish.inc')
            elif ack_mode == 'eop':
                shutil.copyfile(BASE/'source/streaming_ack_eop.inc', output/'streaming_ack_eop.inc')
        (output/'vusb_empty_data.inc').write_text(empty)
        main += '\n.org 0x1600\n'+render_assembly()
    source = output/'application.S'
    source.write_text(main)
    obj, rawfile = output/'application.o', output/'application.raw.bin'
    assemble(source, obj, rawfile)
    text = subprocess.check_output(['llvm-objdump', '-t', str(obj)], text=True)
    symbols = {m.group(2): int(m.group(1), 16) for m in
               re.finditer(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$', text, re.M)}
    raw = rawfile.read_bytes()
    assert raw[:ORIGIN] == bytes(ORIGIN)
    assert symbols['prototype_code_end'] <= 0x1600
    assert len(raw) <= APPLICATION_END
    if receiver.startswith('streaming'):
        assert symbols['stream_crc_table_low'] == 0x1600
        assert symbols['stream_crc_table_high'] == 0x1700
        assert len(raw) == 0x1800
    body = raw[ORIGIN:]
    (output/'application.bin').write_bytes(body)
    image = bytearray(b'\xff'*8192)
    image[ORIGIN:len(raw)] = body
    # The first trampoline is the format used by earlier reversible trials.
    image[:2] = (0xC03F).to_bytes(2, 'little')
    image[0x80:0x82] = (0xC000|((ORIGIN-0x82)//2)).to_bytes(2, 'little')
    (output/'application-full.bin').write_bytes(image)
    lines = [record(0, image[:2]), record(0x80, image[0x80:0x82])]
    lines += [record(a, image[a:min(a+16,len(raw))]) for a in range(ORIGIN,len(raw),16)]
    lines.append(record(0,b'',1))
    (output/'application.hex').write_text('\n'.join(lines)+'\n')
    (output/'symbols.txt').write_text('\n'.join(f'{n} 0x{a:04X}' for n,a in symbols.items())+'\n')
    manifest = {'receiver':receiver,'ack_mode':ack_mode,'image_address':ORIGIN,'body_file':'application.bin',
                'full_image_file':'application-full.bin','symbols':symbols,
                'body_bytes':len(body),'executable_end':symbols['prototype_code_end'],
                'sha256_body':hashlib.sha256(body).hexdigest(),
                'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(output.glob('*.inc'))},
                'application_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'mutation_requests_enabled':False,'spm_enabled':False,
                'eeprom_programming_enabled':False,'diagnostic_flash_read_limit':8192,
                'inactivity_application_jump_enabled':False,
                'protected_boot_address':PROTECTED_BOOT,'physical_device_programmed':False}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='symbols'},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receiver', choices=['baseline','streaming','streaming-v2'], default='streaming-v2')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--ack-mode', choices=MODES, default='immediate')
    args = parser.parse_args()
    suffix = '' if args.ack_mode == 'immediate' else '-'+args.ack_mode
    build(args.receiver, args.output_dir or BASE/'build'/(args.receiver+suffix), args.ack_mode)
