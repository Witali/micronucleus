"""Build linked ATtiny88 images; measure overflow without admitting a release."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
D = {'NONE': 'no_led', 'ACTIVE_HIGH': 'led_high', 'ACTIVE_LOW': 'led_low'}


def run(arguments):
    return subprocess.run(arguments, check=True, capture_output=True, text=True).stdout


def build(where='source', led='NONE', boot=0x1A40, save=True):
    source_dir = (ROOT / where).resolve()
    if not source_dir.is_relative_to(ROOT):
        raise ValueError('Source must belong to this variant')
    output = ROOT / 'build' / source_dir.relative_to(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    stem = output / f'{led.lower()}_{boot:04x}'
    relocatable, obj, binary = (Path(str(stem) + suffix)
                               for suffix in ('.reloc.o', '.o', '.bin'))
    run(['clang', '-target', 'avr', '-mmcu=attiny88', f'-DLED_MODE={led}',
         f'-DBOOT_AT={hex(boot)}', '-I', str(ROOT / 'vendor'), '-x',
         'assembler-with-cpp', '-c', str(source_dir / 'micronucleus_t88_compact.S'),
         '-o', str(relocatable)])
    # Models and BIN export must consume linked words, not LLVM relocations.
    # Overflow measurement uses a larger region; release fit is a separate gate.
    run(['avr-ld', '-m', 'avr25', '--defsym=__TEXT_REGION_LENGTH__=0x10000',
         '-Ttext=0', '-e', 'bootloader_start', '-o', str(obj), str(relocatable)])
    assert 'R_AVR_' not in run(['llvm-objdump', '-r', str(obj)])
    assert not run(['llvm-nm', '--undefined-only', str(obj)]).strip()
    run(['llvm-objcopy', '-O', 'binary', '-j', '.text', str(obj), str(binary)])
    blob = binary.read_bytes()
    assert blob[:boot] == bytes(boot), 'Unexpected preboot code'
    body = blob[boot:]
    return dict(variant=led, boot_at=f'{boot:#06x}', bytes=len(body),
                capacity=8192 - boot, fits=len(body) <= 8192 - boot,
                sha256=hashlib.sha256(body).hexdigest(), obj=str(obj),
                bin=str(binary), symbols=run(['llvm-objdump', '-t', str(obj)]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--where', default='source')
    parser.add_argument('--boot', default=0x1A40, type=lambda value: int(value, 0))
    parser.add_argument('--all-led', action='store_true')
    parser.add_argument('--require-fit', action='store_true')
    args = parser.parse_args()
    images = [build(args.where, mode, args.boot)
              for mode in (D if args.all_led else ('NONE',))]
    for image in images:
        print(f"{image['variant']:12} {image['bytes']:4} B; limit={image['capacity']:4}, "
              f"fit={image['fits']}, SHA256={image['sha256']}")
    source_dir = (ROOT / args.where).resolve().relative_to(ROOT)
    destination = ROOT / 'build' / source_dir / f'manifest_{args.boot:04x}.json'
    destination.write_text(json.dumps([{key: value for key, value in item.items()
                                       if key != 'symbols'} for item in images], indent=2) + '\n')
    if args.require_fit and not all(image['fits'] for image in images):
        raise SystemExit('FAIL: code exceeds the requested Flash region')
