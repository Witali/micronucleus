#!/usr/bin/env python3
"""Build a scratch-limited protocol 3.0 application; never program hardware."""
from pathlib import Path
import hashlib
import json
import shutil

from build_candidate import checked_build
from check_build import build
from host.compact_programmer27 import record, parse_intel_hex

ROOT = Path(__file__).resolve().parent
ORIGIN = 0x1000
SCRATCH_RANGES = ((0x0040, 0x0080), (0x00C0, 0x0FC0), (0x14C0, 0x1AC0))


def is_scratch(page):
    return any(start <= page < end for start, end in SCRATCH_RANGES)


def replace_once(text, old, new):
    """Refuse to patch a different source layout silently."""
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    out = ROOT / 'build/benchmark30'
    out.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'source').iterdir():
        if path.is_file():
            shutil.copyfile(path, out / path.name)
    main_source = (out / 'micronucleus_t88_compact.S').read_text()
    original_guard = '''#if LOW8(BOOT_AT) == 0
    cpi r31, HIGH8(BOOT_AT)
#else
    cpi r30, LOW8(BOOT_AT)
    ldi r18, HIGH8(BOOT_AT)
    cpc r31, r18
#endif
    brsh bootloader_clear_command'''
    # This is the final common executor for BOTH erase and page commit. Check
    # the aligned physical page, protecting RESET, entry, code and both loaders.
    main_source = replace_once(main_source, original_guard, '''    tst r31
    brne .Lbenchmark_high_page
    cpi r30, 0x40
    breq .Lbenchmark_spm_allowed
    cpi r30, 0xc0
    breq .Lbenchmark_spm_allowed
    rjmp bootloader_clear_command
.Lbenchmark_high_page:
    cpi r31, 0x0f
    brlo .Lbenchmark_spm_allowed
    brne .Lbenchmark_upper_pages
    cpi r30, 0xc0
    brlo .Lbenchmark_spm_allowed
    rjmp bootloader_clear_command
.Lbenchmark_upper_pages:
    cpi r30, 0xc0
    ldi r18, 0x14
    cpc r31, r18
    brlo bootloader_clear_command
    cpi r30, 0xc0
    ldi r18, 0x1a
    cpc r31, r18
    brsh bootloader_clear_command
.Lbenchmark_spm_allowed:''')
    # No software RUN or inactivity exit is allowed in the benchmark harness.
    main_source = replace_once(main_source,
                              '    brbc SREG_Z, bootloader_start_application',
                              '    rjmp usb_poll_resynchronize')
    source = out / 'micronucleus_t88_benchmark30.S'
    source.write_text('#define BOOT_VERSION_BCD 0x0391\n' + main_source)
    memory = out / 'compact_memory.inc'
    memory.write_text(replace_once(memory.read_text(),
                                  '    breq bootloader_queue_command',
                                  '    breq usb_reply_empty'))
    artifact = build(source, 'NONE', ORIGIN)
    production = checked_build('NONE', ORIGIN)
    def phy(item):
        start, end = (item['symbols'][name] - ORIGIN for name in
                      ('USB_handler', 'flash_buffer_append_word'))
        return item['body'][start:end]
    assert phy(artifact) == phy(production), 'Production USB PHY must stay byte-identical'
    assert ORIGIN + artifact['size'] <= SCRATCH_RANGES[-1][0]
    assert int.from_bytes(artifact['body'][32:34], 'little') == 0x0391

    from tests27 import nvm_opcodes as nvm
    cases = 0
    for page in range(0, 0x10000, 64):
        for operation in (3, 5):
            machine = nvm.new_machine(artifact)
            cursor = page if operation == 3 else (page + 64) & 0xFFFF
            nvm.set_pointer(machine, cursor)
            machine.r[3] = operation
            machine.run('bootloader_dispatch_command', stop=('bootloader_clear_command',))
            assert bool(machine.spms) == is_scratch(page)
            if machine.spms:
                assert machine.spms[0][:2] == (operation, page)
            cases += 1
    for cursor in (0, SCRATCH_RANGES[0][0], ORIGIN, 0x1B00, 0x8000):
        machine = nvm.new_machine(artifact)
        nvm.set_pointer(machine, cursor)
        machine.r[25] = 4
        machine.run('bootloader_check_set_flash_address', stop=('usb_reply_empty',))
        assert machine.r[3] == 0 and machine.r[8] == 0 and not machine.spms
    nvm.check_eeprom_write4(artifact)

    entry_source = out / 'micronucleus_t88_benchmark_entry.S'
    entry_source.write_text('''    .text
    .org 0x80
    .global bootloader_start
bootloader_start:
    cli
    ldi r16, 2
    out 0x3e, r16
    ldi r16, 0xff
    out 0x3d, r16
    clr r1
    .word 0xc7b9
''')
    entry = build(entry_source, 'NONE', 0x80)['body']
    assert len(entry) == 14 and entry[-2:] == b'\xb9\xc7'
    lines = [record(0, b'\x3f\xc0'), record(0x80, entry)]
    lines += [record(ORIGIN + at, artifact['body'][at:at + 16])
              for at in range(0, artifact['size'], 16)]
    text = '\n'.join(lines + [record(0, b'', 1)]) + '\n'
    image = parse_intel_hex(text)
    assert max(image) < 0x1AC0
    assert not any(is_scratch(at) or 0xFC0 <= at < ORIGIN for at in image)
    (out / 'application.hex').write_bytes(text.encode('ascii'))
    (out / 'body.bin').write_bytes(artifact['body'])
    manifest = dict(protocol='3.0', bcdDevice='0x0391', application_only=True,
                    origin=ORIGIN, body_bytes=artifact['size'],
                    flash_mutation_ranges=SCRATCH_RANGES,
                    flash_test_bytes=sum(end - start for start, end in SCRATCH_RANGES),
                    eeprom_bytes=64, run_enabled=False, inactivity_exit_enabled=False,
                    installed_loader='2.8 at 0x1B00, unchanged', phy_identical=True,
                    page_guard_opcode_cases=cases,
                    body_sha256=hashlib.sha256(artifact['body']).hexdigest(),
                    hex_sha256=hashlib.sha256(text.encode('ascii')).hexdigest())
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
