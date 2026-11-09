"""Build an isolated test of the redmcg V-USB initial-sample delay.

Run with the normal AVR/LLVM toolchain on PATH. This never changes maintained
firmware or accesses hardware. Use the existing exhaustive receiver verifier
on the generated source; building this experiment is not a qualification pass.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests35 import ep0_model as h

PATCH_URL = 'https://github.com/redmcg/v-usb/commit/089effe8a21977cfab4aff92a985dac0c1eeb72c'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delay', type=int, choices=(0, 1), default=1,
                        help='Zero is the unchanged control; one tests the fork hypothesis')
    parser.add_argument('--ack', action='store_true', help='Select the separate ACK reader')
    parser.add_argument('--boot', type=lambda value: int(value, 0))
    parser.add_argument('--output', type=Path,
                        help='New experiment directory inside this target\'s ignored build directory')
    args = parser.parse_args()
    boot = args.boot if args.boot is not None else (0x1800 if args.ack else 0x1900)
    output = (args.output or ROOT / 'build/rx-entry-delay' /
              f'{"ack" if args.ack else "default"}-{args.delay}').resolve()
    if not output.is_relative_to(ROOT / 'build'):
        parser.error('--output must belong to this target\'s ignored build directory')
    if output.exists():
        parser.error('Experiment already exists; choose a new --output to preserve its evidence')

    phy_path = ROOT / 'variants/combined_rx/vusb_phy.inc'
    phy = phy_path.read_text()
    needle = '    ldi r21, 0x00\n    in r16, _SFR_IO_ADDR(PIND)\n'
    if phy.count(needle) != 1:
        parser.error('Initial-sample entry changed; review the experiment before applying it')
    changed = phy.replace(needle, '    ldi r21, 0x00\n' +
                          '    nop\n' * args.delay + '    in r16, _SFR_IO_ADDR(PIND)\n')
    # Keep the original ACK implementation as its sole owner. Only the copied
    # PHY's include spelling changes to resolve from the experiment directory.
    ack_source = (ROOT / 'variants/ack_terminal/ack_receive.inc').as_posix()
    changed = changed.replace('#include "../ack_terminal/ack_receive.inc"',
                              f'#include "{ack_source}"')
    output.mkdir(parents=True)
    (output / 'vusb_phy.inc').write_text(changed)
    source = f'#include "{(ROOT / "source/micronucleus_t88_compact.S").as_posix()}"\n'
    (output / 'micronucleus_t88_compact.S').write_text(
        f'#define USB_PHY_SOURCE "{(output / "vusb_phy.inc").as_posix()}"\n'
        '#define USB_NEXT_DATA_WAIT_COUNT 28\n'
        '#define BOOT_VERSION_BCD 0xffff\n' +
        ('#define USB_RX_ACK_TERMINAL\n' if args.ack else '') + source)
    selected = output.relative_to(ROOT).as_posix()
    art = h.build(source=selected, boot=boot)
    shutil.copyfile(art['obj'], output / 'receiver.elf')
    (output / 'receiver.body.bin').write_bytes(art['body'])
    manifest = dict(boot=boot, size=art['size'], sha256=art['sha256'],
                    obj='receiver.elf', bin='receiver.body.bin', symbols=art['symbols'],
                    elf_sha256=hashlib.sha256((output / 'receiver.elf').read_bytes()).hexdigest(),
                    base_phy_sha256=hashlib.sha256(phy_path.read_bytes()).hexdigest(),
                    added_initial_clocks=args.delay, separate_ack=args.ack,
                    reference_patch=PATCH_URL, recognized_profile=False)
    (output / 'artifact.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(bytes=art['size'], sha256=art['sha256'],
                          manifest=str(output / 'artifact.json'),
                          verifier_command=f'python3 verify_receiver.py --source {selected} '
                                           f'--boot {boot:#x} --exhaustive'), indent=2))


if __name__ == '__main__':
    main()
