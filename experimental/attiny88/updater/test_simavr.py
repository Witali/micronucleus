#!/usr/bin/env python3
"""Build the native runner against an explicit simavr source/build directory."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    sim = Path(sys.argv[1]).resolve() / 'simavr'
    library = next(sim.glob('obj-*/libsimavr.so')).parent
    executable = ROOT / 'build/test_simavr'
    subprocess.run(['gcc', '-Wall', '-Wextra', '-Werror', '-I' + str(sim / 'sim'),
                    str(ROOT / 'test_simavr.c'), '-L' + str(library), '-Wl,-rpath,' + str(library),
                    '-lsimavr', '-lelf', '-o', str(executable)], check=True)
    metadata = json.loads((ROOT / 'build/manifest.json').read_text())
    prefix = [str(executable), str(ROOT / 'build/updater.flash.bin'),
              str(metadata['symbols']['updater_complete']), str(metadata['symbols']['updater_abort']),
              str(metadata['updater_end'])]
    subprocess.run(prefix, cwd=ROOT, check=True)
    actual = (ROOT / 'build/simavr-result.bin').read_bytes()[0x1ac0:]
    expected = (ROOT.parent / 'variants/strict_usb_1328/BOOTLOADER_BODY_1AC0_STRICT_1328.bin').read_bytes().ljust(1344,b'\xff')
    assert actual == expected, 'simavr updated image differs from the pinned strict image'
    for mode, code in [('disabled',1),('readback',4)]:
        result = subprocess.run(prefix + [mode], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 2 and f'Updater aborted: {code}' in result.stderr, result
        if mode == 'disabled':
            assert 'erased:0 written:0' in result.stderr
        else:
            assert 'reset:c03f' in result.stderr
    damaged = bytearray((ROOT / 'build/updater.flash.bin').read_bytes())
    damaged[metadata['symbols']['bootloader_image'] + 17] ^= 1
    corrupt = ROOT / 'build/corrupt-image.bin'
    corrupt.write_bytes(damaged)
    result = subprocess.run([prefix[0],str(corrupt),*prefix[2:]],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode == 2 and 'Updater aborted: 2 erased:0 written:0' in result.stderr, result
    print('PASS: simavr byte-exact target image and independent fuse/CRC/readback failure cases')


if __name__ == '__main__':
    main()
