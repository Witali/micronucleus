#!/usr/bin/env python3
"""Build and relocate Micronucleus ATtiny88, WITHOUT modifying V-USB timing source.

Run against an upstream checkout. Produces baseline, relocated-original,
compact-candidate and diagnostics. No flashing is performed.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from audit_hex import parse_hex, FLASH_BYTES, PAGE_BYTES, POSTSCRIPT_BYTES

OLD_START=0x1A40


def change_one(txt, pattern, repl, name):
    new, n = re.subn(pattern,repl,txt,flags=re.MULTILINE)
    if n != 1:
        raise RuntimeError(f'Expected exactly one {name} occurrence, got {n}. Source version might differ.')
    return new


def run(command, cwd, check=True):
    print('+', ' '.join(map(str,command)),flush=True)
    proc=subprocess.run(command,cwd=cwd,text=True,capture_output=True)
    if proc.stdout: print(proc.stdout[-4500:],end='\n' if not proc.stdout.endswith('\n') else '')
    if proc.stderr: print(proc.stderr[-4000:],file=sys.stderr)
    if check and proc.returncode:
        raise RuntimeError(f'Command failed ({proc.returncode}): {command}')
    return proc


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture_usb_hashes(firmware):
    paths=[p for p in sorted((firmware/'usbdrv').rglob('*')) if p.is_file() and p.suffix in {'.inc','.S','.c','.h'}]
    paths.append(firmware/'usbconfig.h')
    return {str(p.relative_to(firmware)):digest(p) for p in paths if p.exists()}


def build(firmware, output, name):
    run(['make','clean'],firmware)
    p=run(['make','CONFIG=t88_default','main.hex'],firmware,check=False)
    if p.returncode:
        return None
    details=parse_hex(firmware/'main.hex')
    directory=output/name
    directory.mkdir(parents=True,exist_ok=True)
    for src,dst in [('main.hex','bootloader.hex'),('main.bin','bootloader.elf'),
                    ('main.lss','bootloader.disasm.txt'),('main.map','bootloader.map'),
                    ('usbdrv/usbdrvasm.o','usbdrvasm.o')]:
        if (firmware/src).is_file(): shutil.copy2(firmware/src,directory/dst)
    (directory/'size.json').write_text(json.dumps(details,indent=2)+'\n')
    # Compare EXACT AVR machine-code bytes of the low-level USB assembly object.
    obj=directory/'usbdrvasm.o'
    if obj.exists() and shutil.which('avr-objcopy'):
        raw=directory/'usbdrvasm-text.bin'
        run(['avr-objcopy','-O','binary','-j','.text',str(obj),str(raw)],directory)
        details['usb_asm_object_text_sha256']=digest(raw)
    return details


def set_start(makefile,addr):
    s=makefile.read_text()
    s=change_one(s,r'^BOOTLOADER_ADDRESS\s*=\s*[0-9A-Fa-f]+\s*$',
                 f'BOOTLOADER_ADDRESS = {addr:04X}','BOOTLOADER_ADDRESS')
    makefile.write_text(s)


def write_report(output, values):
    (output/'build_manifest.json').write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source',type=Path,help='Repository root, or firmware directory')
    ap.add_argument('--output',type=Path,default=Path('build_results'))
    args=ap.parse_args()
    root=args.source.resolve()
    firmware=root/'firmware' if (root/'firmware').is_dir() else root
    if not (firmware/'Makefile').is_file(): ap.error('Expected micronucleus/firmware Makefile')
    cfg=firmware/'configuration/t88_default/bootloaderconfig.h'
    mk=firmware/'configuration/t88_default/Makefile.inc'
    for name in ['avr-gcc','avr-size','avr-objdump','make']:
        if not shutil.which(name): sys.exit(f'Missing {name}; install gcc-avr avr-libc binutils-avr make')
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)

    original_cfg=cfg.read_text()
    original_mk=mk.read_text()
    usb_before=capture_usb_hashes(firmware)
    report={'baseline':None,'relocated_unmodified':None,'led_only':None,'compact':None,
            'postscript_bytes':POSTSCRIPT_BYTES,'usb_sources_untouched':False,
            'notes': ['No V-USB assembly modifications','Hardware USB testing remains necessary']}
    try:
        assert re.search(r'^F_CPU\s*=\s*16000000\s*$',original_mk,re.M), 'Expected 16 MHz t88'
        assert re.search(r'^BOOTLOADER_ADDRESS\s*=\s*1A40\s*$',original_mk,re.M), 'Expected 0x1A40 baseline'
        assert re.search(r'^#define LED_MODE\s+ACTIVE_HIGH\s*$', original_cfg, re.M)
        assert re.search(r'^#define SAVE_MCUSR\s*$', original_cfg, re.M)
        assert re.search(r'^#define OSCCAL_HAVE_XTAL\s+1\s*$',original_cfg,re.M)

        report['baseline']=build(firmware,output,'baseline')
        if not report['baseline']: raise RuntimeError('Baseline cannot be compiled with current toolchain')

        # Stage 1: unchanged C/assembly, only move the whole bootloader up.
        # Try a fitting page boundary and back off if relocation increases code size.
        unmodified_size=report['baseline']['code_bytes']
        start=FLASH_BYTES - ((unmodified_size + PAGE_BYTES-1)//PAGE_BYTES)*PAGE_BYTES
        while start>OLD_START:
            set_start(mk,start)
            x=build(firmware,output,'relocated_unmodified')
            if x and x['code_start']==start and x['code_end_exclusive'] <= FLASH_BYTES:
                report['relocated_unmodified']=x
                break
            start -=PAGE_BYTES
        mk.write_text(original_mk)

        # Stage 2: LED disabled, preserve MCUSR/reset-cause behavior.
        led_cfg=change_one(original_cfg,r'^#define LED_MODE\s+ACTIVE_HIGH\s*$',
                           '#define LED_MODE    NONE','LED_MODE')
        cfg.write_text(led_cfg)
        led_base=build(firmware,output,'led_only_at_old_address')
        if not led_base: raise RuntimeError('LED-only configuration did not compile')
        start=FLASH_BYTES-((led_base['code_bytes']+PAGE_BYTES-1)//PAGE_BYTES)*PAGE_BYTES
        while start>=OLD_START:
            set_start(mk,start)
            x=build(firmware,output,'led_only')
            if x and x['code_start']==start and x['code_end_exclusive']<=FLASH_BYTES:
                report['led_only']=x
                break
            start-=PAGE_BYTES
        if not report['led_only']: raise RuntimeError('LED-only configuration did not fit')
        mk.write_text(original_mk)

        # Stage 3: optional more compact build, MCUSR handoff is changed.
        compact_cfg=change_one(led_cfg,r'^#define SAVE_MCUSR\s*$',
                               '// #define SAVE_MCUSR // optional: disabled for reduced footprint',
                               'SAVE_MCUSR')
        cfg.write_text(compact_cfg)
        compact_base=build(firmware,output,'compact_at_old_address')
        if not compact_base: raise RuntimeError('Compact configuration did not compile')
        start=FLASH_BYTES-((compact_base['code_bytes']+PAGE_BYTES-1)//PAGE_BYTES)*PAGE_BYTES
        while start>=OLD_START:
            set_start(mk,start)
            x=build(firmware,output,'compact')
            if x and x['code_start']==start and x['code_end_exclusive']<=FLASH_BYTES:
                report['compact']=x
                break
            start-=PAGE_BYTES
        (output/'changes_bootloaderconfig.diff.txt').write_text(
            '--- original/bootloaderconfig.h\n+++ compact/bootloaderconfig.h\n'
            '-#define LED_MODE    ACTIVE_HIGH\n+#define LED_MODE    NONE\n'
            '-#define SAVE_MCUSR\n+// #define SAVE_MCUSR // disabled\n')
        if not report['compact']:
            raise RuntimeError('Compact build failed to fit even at original address')

        # LED-only is preferred whenever same flash saving: it keeps MCUSR semantics.
        preferred='led_only'
        if report['compact']['user_code_limit']>report['led_only']['user_code_limit']:
            preferred='compact'
            report['notes'].append('Smaller size requires disabling SAVE_MCUSR. See README.')
        report['preferred_variant']=preferred
        candidate=report[preferred]
        report['candidate_start']=f'0x{candidate["code_start"]:04X}'
        asm_base=report['baseline'].get('usb_asm_object_text_sha256')
        asm_opt=candidate.get('usb_asm_object_text_sha256')
        report['usb_asm_object_bytes_identical'] = bool(asm_base and asm_base == asm_opt)
        if not report['usb_asm_object_bytes_identical']:
            report['notes'].append('WARNING: USB assembly .text differs! Investigate before flashing.')
        report['candidate_user_limit']=candidate['user_code_limit']
        report['reclaimed_bytes']=candidate['user_code_limit']-report['baseline']['user_code_limit']
        if (output/'baseline/bootloader.disasm.txt').exists() and (output/preferred/'bootloader.disasm.txt').exists():
            (output/'USB_HANDLER_CHECK.txt').write_text(
                'IMPORTANT: V-USB assembly source has not been touched.\n'
                'Inspect the USB_handler and usbCrc16Append machine code in both disassembly files.\n'
                'A different link address or relaxation may alter instruction sizes.\n'
                'Use a logic analyzer / hardware USB host test before deploying.\n')
    finally:
        report['usb_sources_untouched'] = capture_usb_hashes(firmware)==usb_before
        cfg.write_text(original_cfg)
        mk.write_text(original_mk)
        write_report(output,report)
        print('\nFinished. Source configuration restored. Results:',json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
