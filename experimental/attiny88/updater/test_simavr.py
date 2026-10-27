#!/usr/bin/env python3
"""Build the native runner against an explicit simavr source/build directory."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simavr_source', type=Path)
    parser.add_argument('--build-dir', type=Path, default=ROOT/'build')
    parser.add_argument('--initial-flash', type=Path,
                        help='Optional complete Flash with the old loader and uploaded updater')
    args = parser.parse_args()
    sim = args.simavr_source.resolve() / 'simavr'
    build = args.build_dir.resolve()
    library = next(sim.glob('obj-*/libsimavr.so')).parent
    executable = build / 'test_simavr'
    subprocess.run(['gcc', '-Wall', '-Wextra', '-Werror', '-I' + str(sim / 'sim'),
                    str(ROOT / 'test_simavr.c'), '-L' + str(library), '-Wl,-rpath,' + str(library),
                    '-lsimavr', '-lelf', '-o', str(executable)], check=True)
    metadata = json.loads((build / 'manifest.json').read_text())
    boot = metadata['image_address']
    initial = args.initial_flash.resolve() if args.initial_flash else build / 'updater.flash.bin'
    assert len(initial.read_bytes()) == 8192, 'Initial Flash must contain8192 bytes'
    prefix = [str(executable), str(initial),
              str(metadata['symbols']['updater_complete']), str(metadata['symbols']['updater_abort']),
              str(metadata['updater_end']), str(boot)]
    subprocess.run(prefix, cwd=build, check=True)
    actual = (build / 'simavr-result.bin').read_bytes()[boot:]
    expected = (build / metadata['image_file']).read_bytes()
    assert hashlib.sha256(expected).hexdigest() == metadata['padded_image_sha256']
    assert actual == expected, 'simavr updated image differs from the selected image'
    for mode, code in [('disabled',1),('readback',4)]:
        result = subprocess.run(prefix + [mode], cwd=build, capture_output=True, text=True)
        assert result.returncode == 2 and f'Updater aborted: {code}' in result.stderr, result
        if mode == 'disabled':
            assert 'erased:0 written:0' in result.stderr
        else:
            assert 'reset:c03f' in result.stderr
    damaged = bytearray(initial.read_bytes())
    damaged[metadata['symbols']['bootloader_image'] + 17] ^= 1
    corrupt = build / 'corrupt-image.bin'
    corrupt.write_bytes(damaged)
    result = subprocess.run([prefix[0],str(corrupt),*prefix[2:]],cwd=build,capture_output=True,text=True)
    assert result.returncode == 2 and 'Updater aborted: 2 erased:0 written:0' in result.stderr, result
    print('PASS: simavr byte-exact target image and independent fuse/CRC/readback failure cases')


if __name__ == '__main__':
    main()
