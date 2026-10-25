#!/usr/bin/env python3
"""Reproduce the packet-corrected loader, optionally with compile-time LED code.

Historical sources/images stay unchanged. USB RX/TX bit-engine bytes remain
identical; routing and RAM/Flash response copying are outside that engine.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DEFAULT_SHA256 = 'ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--led', choices=['off', 'on', 'active-low'],
                        help='LED_MODE override; on means ACTIVE_HIGH on PD0 by default')
    parser.add_argument('-D', dest='defines', action='append', default=[], metavar='NAME=VALUE',
                        help='Override LED_MODE, LED_DDR_IO, LED_PORT_IO, LED_PIN or LED_BLINK_MASK')
    parser.add_argument('--output-dir', type=Path, help='Separate output directory (never flashes hardware)')
    args = parser.parse_args()
    allowed = {'LED_MODE', 'LED_DDR_IO', 'LED_PORT_IO', 'LED_PIN', 'LED_BLINK_MASK'}
    defines = {}
    for define in args.defines:
        name, sep, value = define.partition('=')
        if name not in allowed or not sep or not value:
            parser.error(f'Expected one of {sorted(allowed)} followed by =VALUE')
        defines[name] = value
    if args.led:
        if 'LED_MODE' in defines:
            parser.error('Use either --led or -D LED_MODE, not both')
        defines['LED_MODE'] = {'off': 'NONE', 'on': 'ACTIVE_HIGH', 'active-low': 'ACTIVE_LOW'}[args.led]
    flags = [f'{key}={value}' for key, value in defines.items()]
    spec = importlib.util.spec_from_file_location('base_builder',ROOT.parent/'build.py')
    base = importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    spec = importlib.util.spec_from_file_location('image_records',ROOT/'build.py')
    helper = importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    source = (ROOT.parent/'variants/strict_usb_1328/micronucleus_t88_plus_strict.S').read_text()
    assert 'r2,' not in source and 'r2\n' not in source
    # WDRF forces WDE on real hardware. Preserve/reset MCUSR before the
    # watchdog-disable sequence, instead of waiting until application exit.
    save_reset = '    in      r24, 0x34\n    out     0x1e, r24\n    out     0x34, r1\n'
    assert source.count(save_reset)==1
    source = source.replace(save_reset,'',1)
    source = source.replace('main:\n    wdr\n','main:\n    wdr\n'+save_reset,1)
    source = source.replace('    ldd     r24, Y+23\n    andi    r24, 0x60',
                            '    mov     r2, r1    /* New SETUP defaults to a Flash response. */\n'
                            '    ldd     r24, Y+23\n    andi    r24, 0x60',1)
    source = source.replace('L1dce:\n    mov     r7, r1\n',
                            'L1dce:\n    mov     r7, r1\n'
                            '    cpi     r25, 0xa0\n    brlo    legacy_vendor\n'
                            '    rjmp    L1f0c\nlegacy_vendor:\n',1)
    source = source.replace('    lpm     r25, Z+  /* same read and advance; LPM Rd,Z+ supported on tiny88 */',
                            '    sbrc    r2, 0\n    ld      r25, Z+\n'
                            '    sbrs    r2, 0\n    lpm     r25, Z+ /* Flash and SRAM have distinct address spaces. */',1)
    source = source.replace('    ldi     r19, 0x01                        /* repeated 16-bit pointer high */',
                            '    ldi     r19, 0x01                        /* repeated 16-bit pointer high */\n'
                            '    mov     r2, r19    /* Standard/EEPROM response buffer is SRAM. */',1)
    # GET_CONFIGURATION used a second SRAM pointer path. Reuse the same
    # one-byte RAM reply helper without increasing the image size.
    source = source.replace('L1f7a:\n    ldi     r18, 0x15\n    ldi     r19, 0x01\n    ldi     r24, 0x01\n\nmain_tail:\n    rjmp    L1f22',
                            'L1f7a:\n    ldd     r18, Y+21\n    std     Y+10, r18\n    ldi     r24, 0x01\n\nmain_tail:\n    rjmp    L1f34',1)
    # Shared includes keep LED settings intact when this source is regenerated.
    # NONE expands to zero instructions at all three hooks.
    source = source.replace('#ifndef BOOT_AT',
                            '#include "led_config.h"\n#include "led_macros.inc"\n\n#ifndef BOOT_AT', 1)
    source = source.replace('    /* Removed 0x1d30: sbi     0xa, 0 (size-optimized, see CHANGES.md) */',
                            'led_init:\n    LED_INIT\nled_init_done:', 1)
    source = source.replace('L1e7c:\n', 'L1e7c:\nled_tick:\n    LED_TICK\nled_tick_done:\n', 1)
    source = source.replace('L1eac:\n', 'L1eac:\nled_exit:\n    LED_EXIT\nled_exit_done:\n', 1)
    out = ROOT.parent/'variants/strict_usb_verified'
    out.mkdir(exist_ok=True)
    asm = out/'micronucleus_t88_verified.S';asm.write_text(source)
    # Measure at a safe page boundary, then reserve complete 64-byte pages.
    boot = 0x1a80
    body, symbols = base.compile_asm(asm, boot, 'verified_probe', flags)
    measured_boot = (8192 - len(body)) & ~63
    assert 0x1800 <= measured_boot <= 0x1ac0, 'Unexpected loader size'
    if measured_boot != boot:
        boot = measured_boot
        body, symbols = base.compile_asm(asm, boot, 'verified_configured', flags)
    assert len(body) <= 8192 - boot, 'Loader exceeds reserved Flash'
    old, oldsym = base.compile_asm(ROOT.parent/'variants/strict_usb_1328/micronucleus_t88_plus_strict.S',0x1ac0,'strict_reference')
    for start,end in [('usb_crc16_append','USB_handler'),('USB_handler','usb_program_page')]:
        assert body[symbols[start]-boot:symbols[end]-boot]==old[oldsym[start]-0x1ac0:oldsym[end]-0x1ac0]
    sha256 = hashlib.sha256(body).hexdigest()
    led = {key: symbols[f'led_config_{key}'] for key in ['mode', 'ddr_io', 'port_io', 'pin', 'blink_mask']}
    if led['mode'] == 0:
        assert boot == 0x1ac0 and sha256 == DEFAULT_SHA256, 'No-LED image changed'
    build = args.output_dir or ROOT/'build'/('verified' if not defines else f'led-{args.led or "configured"}')
    build.mkdir(parents=True, exist_ok=True)
    (build/'bootloader.bin').write_bytes(body)
    image=bytearray(b'\xff'*8192)
    image[:2]=(0xc000 | ((boot//2 - 1) & 0xfff)).to_bytes(2,'little')
    image[boot:boot+len(body)]=body
    lines=[helper.record(0,image[:2])]+[helper.record(a,image[a:a+16]) for a in range(boot,8192,16)]
    lines.append(helper.record(0,b'',1))
    hex_text = '\n'.join(lines)+'\n'
    (build/'isp-fresh.hex').write_text(hex_text)
    manifest = {'target': 'attiny88', 'image_address': boot, 'code_bytes': len(body),
                'application_bytes': boot-4, 'body_file': 'bootloader.bin',
                'body_sha256': sha256, 'led': led, 'symbols': symbols}
    (build/'firmware.json').write_text(json.dumps(manifest, indent=2)+'\n')
    if not defines and led['mode'] == 0:
        (ROOT/'build/verified-symbols.json').write_text(json.dumps(symbols))
        (out/'BOOTLOADER_BODY_1AC0_VERIFIED.bin').write_bytes(body)
        (out/'ISP_FULL_1AC0_VERIFIED_FRESH_ONLY.hex').write_text(hex_text)
    print(f'PASS: {len(body)} code bytes at 0x{boot:04X}; {boot-4} application bytes; LED mode {led["mode"]}')
    print('PASS: CRC and low-level USB handler byte-identical to strict reference')
    print('sha256:', sha256)
    print('Output:', build/'firmware.json')


if __name__=='__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stderr or str(error), file=sys.stderr)
        sys.exit(1)
