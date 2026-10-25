#!/usr/bin/env python3
"""Build an isolated size-optimized candidate; never program hardware.

The deployed verified artifacts remain pinned. Every candidate must retain
the exact 516-byte USB engine and the 40-byte CRC arithmetic from that image.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VARIANT = ROOT.parent/'variants/strict_usb_optimized'
BASELINE_SHA256 = 'ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--led', choices=['off','on','active-low'], default='off')
    parser.add_argument('-D', dest='defines', action='append', default=[], metavar='NAME=VALUE')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    allowed = {'LED_DDR_IO','LED_PORT_IO','LED_PIN','LED_BLINK_MASK'}
    for define in args.defines:
        key,sep,value = define.partition('=')
        if key not in allowed or not sep or not value:
            parser.error(f'Expected one of {sorted(allowed)} followed by =VALUE')
    mode = {'off':'NONE','on':'ACTIVE_HIGH','active-low':'ACTIVE_LOW'}[args.led]
    flags = [f'LED_MODE={mode}', *args.defines]
    spec = importlib.util.spec_from_file_location('base_builder', ROOT.parent/'build.py')
    base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
    source = VARIANT/'micronucleus_t88_optimized.S'
    # Measure at a safe zero-low-byte boundary. The nonzero-low-byte Flash
    # guard adds exactly four bytes; do not link a trial beyond device Flash.
    probe,_ = base.compile_asm(source,0x1a00,'optimized_probe',flags)
    for boot in [0x1b00,0x1ac0,0x1a80,0x1a40]:
        predicted = len(probe)+(4 if boot&255 else 0)
        if predicted > 8192-boot:
            continue
        body,symbols = base.compile_asm(source,boot,'optimized_candidate',flags)
        assert len(body) == predicted, 'Re-audit boundary-dependent size'
        break
    else:
        raise AssertionError('Candidate does not fit reserved Flash')
    reference,ref = base.compile_asm(ROOT.parent/'variants/strict_usb_verified/micronucleus_t88_verified.S',
                                     0x1ac0,'optimized_reference',['LED_MODE=NONE'])
    assert hashlib.sha256(reference).hexdigest() == BASELINE_SHA256
    engine = body[symbols['USB_handler']-boot:symbols['flash_buffer_append_word']-boot]
    original_engine = reference[ref['USB_handler']-0x1ac0:ref['usb_program_page']-0x1ac0]
    assert len(engine) == 516 and engine == original_engine, 'USB engine changed'
    crc = body[symbols['usb_crc16_append']-boot:symbols['usb_crc16_core_end']-boot]
    original_crc = reference[ref['usb_crc16_append']-0x1ac0:ref['USB_handler']-0x1ac0]
    # The inlined caller initializes X directly. Omit the original leading
    # MOVW X,R24 and trailing RET; every CRC arithmetic/store byte must match.
    assert len(crc) == 40 and crc == original_crc[2:-2], 'CRC computation changed'
    assert body[2:4] == (boot-4).to_bytes(2,'big')
    output = (args.output_dir or ROOT/'build'/f'optimized-{args.led}').resolve()
    output.mkdir(parents=True,exist_ok=True)
    (output/'bootloader.bin').write_bytes(body)
    reset = (0xc000 | ((boot//2-1)&0xfff)).to_bytes(2,'little')
    padded = body.ljust(8192-boot,b'\xff')
    lines = [base.record(0,reset)] + [base.record(boot+i,padded[i:i+16]) for i in range(0,len(padded),16)]
    (output/'isp-fresh.hex').write_text('\n'.join([*lines,base.record(0,b'',1)])+'\n')
    led = {name:symbols['led_config_'+name] for name in ['mode','ddr_io','port_io','pin','blink_mask']}
    manifest = {'target':'attiny88','image_address':boot,'application_bytes':boot-4,
                'code_bytes':len(body),'body_file':'bootloader.bin',
                'body_sha256':hashlib.sha256(body).hexdigest(), 'led':led,'symbols':symbols,
                'usb_engine_bytes':len(engine),'usb_engine_sha256':hashlib.sha256(engine).hexdigest(),
                'crc_core_bytes':len(crc),'crc_core_sha256':hashlib.sha256(crc).hexdigest(),
                'baseline_sha256':BASELINE_SHA256,'baseline_symbols':ref}
    (output/'firmware.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'PASS: {len(body)} code bytes at 0x{boot:04X}; {boot-4} application bytes; LED {args.led}')
    print('PASS: USB engine and CRC arithmetic byte-identical to deployed strict image')
    print('Output:', output/'firmware.json')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stderr or str(error),file=sys.stderr)
        sys.exit(1)
