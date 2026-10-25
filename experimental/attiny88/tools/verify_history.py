#!/usr/bin/env python3
"""Verify the handoff and rebuild every historical assembly checkpoint offline."""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from hashlib import sha256
import csv
import io
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT.parents[1] / 'docs/attiny88-history'
HANDOFF_SHA256 = '32a173304db4b43a42219d2f99b0fd283f26d06c2a001c8c1a06bb05c5ada4fc'

# Archive name, member root, source, expected body, load address.
BUILDS = [
    ('micronucleus_t88_asm_optimized.zip', 'micronucleus_t88_asm',
     'deliverables/micronucleus_t88_optimized.S', 'deliverables/micronucleus_t88_bootloader_body.bin', 0x1B00),
    ('Micronucleus_ATtiny88_official_instruction_audit_2026-10-25.zip', 'Micronucleus_ATtiny88_Audited',
     'source/micronucleus_t88_audited.S', 'firmware/bootloader_1256.bin', 0x1B00),
    ('Micronucleus_Tiny88_Asm_Optimization_Pass2_2026-10-25.zip', 'Micronucleus_Tiny88_Asm_Optimization_Pass2',
     'source/micronucleus_t88_optimized.S', 'firmware/bootloader_1230_body.bin', 0x1B00),
    ('Micronucleus_Tiny88_VUSB_Optimized_Pass3_2026-10-25.zip', 'Micronucleus_Tiny88_VUSB_Pass3',
     'source/micronucleus_t88_vusb_optimized.S', 'firmware/BOOTLOADER_BODY_1B40_1216.bin', 0x1B40),
    ('Micronucleus_Tiny88_EEPROM_Flash_Read_2026-10-25.zip', 'Micronucleus_Tiny88_FlashRead_EEPROM_2026-10-25',
     'source/micronucleus_t88_plus.S', 'firmware/BOOTLOADER_BODY_1A80_PLUS.bin', 0x1A80),
    ('Micronucleus_Tiny88_Size_Optimization_Pass4_2026-10-25.zip',
     'Micronucleus_Tiny88_Size_Optimization_Pass4_2026-10-25/Fast_2_8_8byte',
     'source/micronucleus_t88_plus.S', 'firmware/BOOTLOADER_BODY_1A80_PLUS.bin', 0x1A80),
    ('Micronucleus_Tiny88_Size_Optimization_Pass4_2026-10-25.zip',
     'Micronucleus_Tiny88_Size_Optimization_Pass4_2026-10-25/Compact_2_9_1byte',
     'source/micronucleus_t88_plus.S', 'firmware/BOOTLOADER_BODY_1AC0_COMPACT.bin', 0x1AC0),
    ('Micronucleus_Tiny88_Fast_8byte_Pass5_1344B_2026-10-25.zip', 'Micronucleus_Tiny88_Fast_Pass5',
     'source/micronucleus_t88_plus.S', 'firmware/BOOTLOADER_BODY_1AC0_PLUS.bin', 0x1AC0),
    ('Micronucleus_Tiny88_CRC_Shared_Pass6_2026-10-25.zip', 'Micronucleus_Tiny88_CRC_Shared_Pass6',
     'source/micronucleus_t88_plus.S', 'firmware/BOOTLOADER_BODY_CRC_PLUS.bin', 0x19C0),
    ('Micronucleus_Tiny88_Fast_1320B_Pass7_2026-10-25.zip', 'Micronucleus_Tiny88_Fast_Pass7',
     'source/micronucleus_t88_plus.S', 'firmware/BOOTLOADER_BODY_1AC0_PLUS.bin', 0x1AC0),
    ('Micronucleus_Tiny88_Fast_1320B_Pass7_2026-10-25.zip', 'Micronucleus_Tiny88_Fast_Pass7',
     'variants/strict_usb_1328/micronucleus_t88_plus_strict.S',
     'variants/strict_usb_1328/BOOTLOADER_BODY_1AC0_STRICT_1328.bin', 0x1AC0),
]


def run(*args):
    subprocess.run(args, check=True, capture_output=True)


def main():
    handoff = (HISTORY / 'original-handoff.zip').read_bytes()
    assert sha256(handoff).hexdigest() == HANDOFF_SHA256, 'The original handoff changed'
    with ZipFile(io.BytesIO(handoff)) as outer:
        assert outer.testzip() is None
        archives = {PurePosixPath(n).name: outer.read(n) for n in outer.namelist()
                    if '/02_ORIGINAL_ARCHIVES/' in n and n.endswith('.zip')}
    assert len(archives) == 10
    with (HISTORY / 'import-map.csv').open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    assert {r['source_archive'] for r in rows} == set(archives)
    for row in rows:
        assert sha256(archives[row['source_archive']]).hexdigest() == row['archive_sha256']
    for data in archives.values():
        with ZipFile(io.BytesIO(data)) as z:
            assert z.testzip() is None
    print('PASS: complete handoff SHA-256, ten nested ZIPs, and import-map hashes')
    with tempfile.TemporaryDirectory(prefix='micronucleus-history-') as temporary:
        temp = Path(temporary)
        for archive, root, source, binary, boot in BUILDS:
            with ZipFile(io.BytesIO(archives[archive])) as z:
                src, expected = z.read(f'{root}/{source}'), z.read(f'{root}/{binary}')
            (temp / 'firmware.S').write_bytes(src)
            run('clang', '-target', 'avr', '-mmcu=attiny88', f'-DBOOT_AT=0x{boot:X}',
                '-c', '-x', 'assembler-with-cpp', str(temp / 'firmware.S'), '-o', str(temp / 'firmware.o'))
            run('avr-ld', '--entry=bootloader_start', '-Ttext=0', str(temp / 'firmware.o'),
                '-o', str(temp / 'firmware.elf'))
            run('llvm-objcopy', '-O', 'binary', '-j', '.text', str(temp / 'firmware.elf'),
                str(temp / 'firmware.bin'))
            full = (temp / 'firmware.bin').read_bytes()
            assert full[:boot] == bytes(boot)
            assert full[boot:] == expected, f'Historical binary differs: {archive}/{binary}'
            print(f'PASS: {len(expected):4d} bytes at 0x{boot:04X}: {source}')
    print('PASS: all eleven historical assembly bodies reproduced exactly; no hardware accessed')


if __name__ == '__main__':
    main()
