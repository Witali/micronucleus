#!/usr/bin/env python3
"""Offline-only EEPROM initialization stage for ATtiny88 Flash-only loaders.

No USB I/O and NO automatic programming. Requires LLVM AVR assembler (clang)
plus avr-ld, llvm-nm, llvm-objcopy and llvm-objdump. EEPROM data is embedded
in a temporary application. Main-app replacement requires independent success
verification; a reboot alone is insufficient.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import argparse, hashlib, json, subprocess, shutil, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host.image_core import image_from_file,pack_application,record,image_to_hex as hex_image
from host.profiles import USB_PROFILES

FLASH_BYTES=8192
PAGE_BYTES=64
EEPROM_BYTES=64
# Host-side identity table: these are the existing Pass26/Pass27 profile layouts.
KNOWN_BCD_BOOT={0x0300:0x1B80,0x0301:0x1B40,0x0302:0x1B40,
                0x0550:0x1B40,0x0551:0x1B00,0x0552:0x1B00,
                0x0400:0x1C00,0x0401:0x1B80,0x0402:0x1B80,
                0x0410:0x1C00,0x0413:0x1C00,0x0411:0x1B80,0x0412:0x1B80,
                0x0420:0x1BC0,0x0421:0x1BC0,0x0422:0x1BC0,
                0x0430:0x1C00,0x0431:0x1BC0,0x0432:0x1BC0,
                0x0440:0x1C00,0x0441:0x1BC0,0x0442:0x1BC0,
                0x0443:0x1BC0,0x0444:0x1BC0,0x0445:0x1BC0,
                0x0450:0x1BC0,0x0451:0x1BC0,0x0452:0x1BC0}
KNOWN_BCD_BOOT.update({bcd:profile[1] for bcd,profile in USB_PROFILES.items()})
STAGE_DATA_ADDR=0x60
STAGE_IMAGE_BYTES=STAGE_DATA_ADDR+EEPROM_BYTES

# This source is deliberately free of any reliance on an AVR libc runtime.
# Entered via the ordinary application postscript after Micronucleus RUN.
# It touches EEPROM only. When verified, it causes a watchdog reset so the
# Micronucleus USB bootloader re-enumerates. Failure deliberately does not reset:
# the host must time out and leave the main application alone.
ASM='''/* ATtiny88 one-shot EEPROM installer. 16 MHz (clock speed irrelevant to EEPROM).
 * ATtiny88: EECR=0x1f, EEDR=0x20, EEARL=0x21, WDTCSR=0x60.
 * EEPROM image starts at byte address 0x60 in program Flash.
 * No stack, interrupts, USB driver, RAM or static runtime required.
 */
    .section .text
    .org 0
    .global stage_reset
stage_reset:
    rjmp stage_entry
stage_entry:
    eor r1, r1
    ldi r30, 0x60
    ldi r31, 0x00
    ldi r16, 0
    ldi r17, 64
write_next:
wait_ready:
    sbic 0x1f, 1                  /* EEPE: busy? */
    rjmp wait_ready
    lpm r18, Z+                   /* next desired byte */
    out 0x21, r16                 /* EEARL: 0..63 */
    sbi 0x1f, 0                   /* EERE: read existing byte */
    in r19, 0x20
    cp r19, r18
    breq skip_write              /* preserve EEPROM endurance */
    out 0x20, r18                 /* EEDR */
    out 0x1f, r1                  /* EEPM=00, interrupts off */
    sbi 0x1f, 2                   /* EEMPE */
    sbi 0x1f, 1                   /* EEPE within four CPU cycles */
skip_write:
    inc r16
    dec r17
    brne write_next
    /* A SECOND, SEPARATE complete verify pass of all 64 EEPROM bytes. */
wait_last:
    sbic 0x1f, 1
    rjmp wait_last
    ldi r30, 0x60
    ldi r31, 0x00
    ldi r16, 0
    ldi r17, 64
verify_next:
    lpm r18, Z+
    out 0x21, r16
    sbi 0x1f, 0
    in r19, 0x20
    cp r18, r19
    brne verify_failed
    inc r16
    dec r17
    brne verify_next
    /* Verification completion requests a reboot into Micronucleus. A USB
     * reconnect alone is ambiguous; require independent success evidence
     * before replacing this temporary app with the main application.
     * The bootloader itself clears WDRF and disables WDT at entry. */
    wdr
    ldi r18, 0x18                /* WDCE | WDE */
    sts 0x60, r18
    ldi r18, 0x08                /* WDE, nominal 16ms default timeout */
    sts 0x60, r18
wait_for_watchdog:
    rjmp wait_for_watchdog
verify_failed:
    /* Never signal success on readback error. Reset/power cycle can still
     * return to the bootloader for recovery. */
    rjmp verify_failed
    .org 0x60, 0xff
stage_data:
{DATA}
'''

def load_image(path:Path)->dict[int,int]:
    """Use the same strict original-image parser as the Flash programmer."""
    return image_from_file(path)


@dataclass
class Patched:
    image:bytes
    source_reset_word:int
    boot_reset_word:int
    app_postscript_word:int
    app_target_byte:int

def patch_for_loader(raw:dict[int,int],boot_at:int)->Patched:
    """Keep the planner's geometry bound; share RESET/postscript packing."""
    if boot_at%64 or not (0x100<=boot_at<=0x1C00):
        raise ValueError('Unknown or unaligned loader boundary')
    prepared=pack_application(raw,boot_at=boot_at)
    original_reset=raw.get(0,255)|(raw.get(1,255)<<8)
    return Patched(prepared.image,original_reset,prepared.boot_reset_word,
                   prepared.postscript_reset_word,prepared.reset_target_word*2)

def make_asm(image:bytes)->str:
    if len(image)!=64:raise ValueError('ATtiny88 has exactly 64 EEPROM bytes')
    lines=['    .byte '+', '.join('0x%02X'%b for b in image[i:i+8]) for i in range(0,64,8)]
    return ASM.replace('{DATA}','\n'.join(lines))

def compile_stage(source:Path)->bytes:
    clang=shutil.which('clang');objcopy=shutil.which('llvm-objcopy');objdump=shutil.which('llvm-objdump');linker=shutil.which('avr-ld');nm=shutil.which('llvm-nm')
    if not all((clang,objcopy,objdump,linker,nm)):
        raise RuntimeError('clang (AVR backend), avr-ld, llvm-nm, llvm-objcopy and llvm-objdump are required')
    obj=source.with_suffix('.o');out=source.with_suffix('.bin')
    reloc=source.with_suffix('.reloc.o')
    subprocess.run([clang,'-target','avr','-mmcu=attiny88','-x','assembler-with-cpp','-c',str(source),'-o',str(reloc)],check=True,capture_output=True)
    subprocess.run([linker,'-m','avr25','-Ttext=0','-e','stage_reset','-o',str(obj),str(reloc)],check=True,capture_output=True)
    undefined=subprocess.run([nm,'--undefined-only',str(obj)],check=True,capture_output=True,text=True).stdout
    if undefined.strip():raise RuntimeError('Linked EEPROM stage has undefined symbols')
    rel=subprocess.run([objdump,'-r',str(obj)],check=True,capture_output=True,text=True).stdout
    if 'R_AVR_' in rel:raise RuntimeError('Assembler left unresolved AVR relocations')
    subprocess.run([objcopy,'-O','binary','-j','.text',str(obj),str(out)],check=True,capture_output=True)
    image=out.read_bytes()
    if len(image)!=STAGE_IMAGE_BYTES or image[:2]==b'\xff\xff':raise AssertionError('Unexpected EEPROM helper layout')
    return image

def make_plan(ee:bytes,application:Path,out_dir:Path,boot_at:int):
    out_dir.mkdir(parents=True,exist_ok=True)
    source=out_dir/'eeprom_stage.S';source.write_text(make_asm(ee))
    stage=compile_stage(source)
    prepared_stage=patch_for_loader(dict(enumerate(stage)),boot_at)
    prepared_main=patch_for_loader(load_image(application),boot_at)
    (out_dir/'stage_raw_application.bin').write_bytes(stage)
    (out_dir/'stage_raw_application.hex').write_text(hex_image(stage))
    (out_dir/'stage_PREPATCHED_direct_page_only.hex').write_text(hex_image(prepared_stage.image))
    (out_dir/'main_PREPATCHED_direct_page_only.hex').write_text(hex_image(prepared_main.image))
    # Nothing in this script sends any USB control transfer.
    stage_pages=list(range(0, ((len(stage)+PAGE_BYTES-1)//PAGE_BYTES)*PAGE_BYTES, PAGE_BYTES))
    stage_pages.append(boot_at-PAGE_BYTES)  # Postscript, committed last.
    stage_page_meta=[{'start':f'0x{addr:04X}', 'sha256':hashlib.sha256(prepared_stage.image[addr:addr+PAGE_BYTES]).hexdigest()} for addr in stage_pages]
    manifest={
        'format':'Micronucleus+ EEPROM staging offline plan (NOT hardware tested)',
        'boot_at':f'0x{boot_at:04X}', 'eeprom_bytes':len(ee),
        'temporary_app_bytes':len(stage),
        'optional_sparse_stage_page_plan':stage_page_meta,
        'stage_image_sha256':hashlib.sha256(prepared_stage.image).hexdigest(),
        'main_image_sha256':hashlib.sha256(prepared_main.image).hexdigest(),
        'eeprom_image_sha256':hashlib.sha256(ee).hexdigest(),
        'stage_reset_target':f'0x{prepared_stage.app_target_byte:04X}',
        'main_reset_target':f'0x{prepared_main.app_target_byte:04X}',
        'execute':False,'physical_validation':False,
        'automatic_main_installation_allowed':False,
        'independent_eeprom_success_verification_required':True,
        'steps':['Backup current Flash and EEPROM if possible, confirm correct USB device profile',
                 'Upload stage_raw_application.bin through the client matching the detected protocol (flash_only_programmer35.py for v4.1) (which patches RESET/postscript), OR use a separately validated sparse-page uploader; verify Flash',
                 'Send RUN; temporary app programs/reads back EEPROM; successful verification triggers WDT reset',
                 'Wait for bootloader USB re-enumeration with bounded timeout; no connection means failure',
                 'STOP: independently verify EEPROM-stage success before replacing it; USB re-enumeration alone is not proof',
                 'Only after independently verified EEPROM-stage success, manually upload the ORIGINAL main application through the client matching the detected protocol (flash_only_programmer35.py for v4.1); replace/verify ALL pages including stage bytes',
                 'Send RUN only after complete main Flash verification'],
        'warnings':['DO NOT feed *_PREPATCHED_direct_page_only.hex into host/flash_only_programmer35.py: double RESET/postscript patching will corrupt entry points',
                    'No separate EEPROM readback from the permanent bootloader',
                    'USB reconnect may also follow power loss or external reset and does not prove the EEPROM verification completed',
                    'No authoritative automatic stage-success mechanism is implemented; this output remains an offline plan only',
                    'Standard compact_programmer27.py writes ALL app pages; the optional 4-page sparse-stage plan needs an independently validated uploader',
                    'A power loss before installing the final app leaves the temporary app installed',
                    'Chip Erase may erase EEPROM depending on fuse EESAVE; use page erase only',
                    'Do not begin without ability to recover from RESET-page write interruption']}
    (out_dir/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--eeprom',required=True,type=Path,help='Exact 64-byte EEPROM image')
    p.add_argument('--application',required=True,type=Path,help='Final app .bin/.hex')
    p.add_argument('--bcd-device',type=lambda x:int(x,0),help='USB device revision; selects known loader boundary')
    p.add_argument('--boot-at',type=lambda x:int(x,0),help='OFFLINE manual boundary, for development candidates only')
    p.add_argument('--out',default=Path('output_stage'),type=Path)
    a=p.parse_args()
    boot=a.boot_at
    if a.bcd_device is not None:
        if a.bcd_device not in KNOWN_BCD_BOOT:
            p.error('Unknown bcdDevice; do not guess the loader boundary')
        identified=KNOWN_BCD_BOOT[a.bcd_device]
        if boot is not None and boot!=identified:
            p.error('Conflicting manual boot boundary and bcdDevice profile')
        boot=identified
    if boot is None:
        p.error('Specify --bcd-device for a known loader or --boot-at for an offline candidate')
    m=make_plan(a.eeprom.read_bytes(),a.application,a.out,boot)
    print(f'PASS: {m["temporary_app_bytes"]} byte EEPROM helper compiled; raw stage and direct-page HEX images prepared')
    print('DRY RUN ONLY, USB device unchanged. Output:',a.out)
if __name__=='__main__': main()
