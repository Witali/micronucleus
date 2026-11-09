"""Measure pinned native V-USB16 and loader code without touching hardware.

Run with the AVR GCC/binutils and LLVM tools on PATH. Upstream is a separate
clean checkout: no third-party source or compiled image is added to this repo.
Partitions are disjoint linked address ranges, not standalone callable APIs.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build import build

PIN = '801242072fa035e1839e3571df0d9a18e9cec95c'


def run(arguments):
    return subprocess.check_output([str(x) for x in arguments], text=True,
                                   stderr=subprocess.STDOUT)


def optional_commit(directory):
    # A Windows worktree's .git pointer may be unreadable from Linux/WSL.
    # Linked body identities remain mandatory even when this metadata is absent.
    try:
        return run(['git', '-C', directory, 'rev-parse', 'HEAD']).strip()
    except subprocess.CalledProcessError:
        return None


def symbols(elf):
    """Keep all linked labels, including zero-size assembly aliases."""
    result = {}
    for line in run(['avr-nm', '-an', elf]).splitlines():
        fields = line.split()
        if len(fields) == 3:
            try:
                result[fields[2]] = int(fields[0], 16)
            except ValueError:
                pass
    return result


def ranges(sym, groups):
    """Count each explicit interval once and reject overlapping assignments."""
    used, counts = set(), {}
    for name, bounds in groups.items():
        count = 0
        for first, last in bounds:
            start = sym[first] if isinstance(first, str) else first
            end = sym[last] if isinstance(last, str) else last
            assert start <= end and start % 2 == end % 2 == 0, (name, start, end)
            addresses = set(range(start, end))
            assert not used.intersection(addresses), name
            used.update(addresses)
            count += end - start
        counts[name] = count
    return counts


def native_partition(sym, size):
    groups = {
        'descriptors': [('usbDescriptorConfiguration', '__ctors_start')],
        'sync_entry': [('__vector_1', 'unstuff6')],
        'rx_stuff_early_framing': [('unstuff6', 'overflow')],
        'eop_final_tail': [('se0', 'handleSetupOrOut')],
        'packet_and_transaction_state': [('overflow', 'se0'), ('handleSetupOrOut', 'bitstuffN')],
        'tx_symbols_and_eop': [('bitstuffN', 'usbPoll')],
        'crc16_and_ep0': [('usbCrc16', '__vector_1'), ('usbPoll', 'usbInit')],
    }
    counts = ranges(sym, groups)
    counts['initialization_loader_and_other'] = size - sum(counts.values())
    assert counts['initialization_loader_and_other'] >= 0
    return counts


def loader_partition(sym, size, boot):
    terminal_start = min(sym[name] for name in (
        'usb_rx_terminal_early_confirm', 'usb_rx_terminal_stuff7', 'usb_rx_terminal_bit6'))
    groups = {
        'descriptors': [(boot + 2, 'USB_handler')],
        'sync_entry': [('USB_handler', 'usb_rx_unstuff_bit6')],
        'rx_stuff_early_framing': [('usb_rx_unstuff_bit6', 'usb_rx_ignore_packet')],
        'eop_final_tail': [('usb_rx_end_packet', 'usb_rx_recovered_j'),
                           (terminal_start, 'startup')],
        'packet_and_transaction_state': [('usb_rx_ignore_packet', 'usb_rx_end_packet'),
                                         ('usb_rx_recovered_j', 'usb_tx_send_ack'),
                                         ('usb_tx_bus_released', 'flash_buffer_ack_write4')],
        'tx_symbols_and_eop': [('usb_tx_send_ack', 'usb_tx_bus_released')],
        'crc16_and_ep0': [('usb_tx_prepare_pending_reply', 'bootloader_check_idle_timeout'),
                         ('usb_validate_setup', 'bootloader_handle_vendor_request')],
    }
    counts = ranges(sym, groups)
    counts['initialization_loader_and_other'] = size - sum(counts.values())
    assert counts['initialization_loader_and_other'] >= 0
    return counts


def build_native(upstream, output, toggle):
    """Build only EP0, no strings except language zero, no application logic."""
    directory = output / f'native-toggle{toggle}'
    directory.mkdir(parents=True, exist_ok=True)
    config = dict(USB_CFG_IOPORTNAME='D', USB_CFG_DMINUS_BIT=1, USB_CFG_DPLUS_BIT=2,
        USB_CFG_CLOCK_KHZ=16000, USB_CFG_HAVE_INTRIN_ENDPOINT=0,
        USB_CFG_HAVE_INTRIN_ENDPOINT3=0, USB_CFG_IMPLEMENT_HALT=0,
        USB_CFG_IMPLEMENT_FN_READ=0, USB_CFG_IMPLEMENT_FN_WRITE=0,
        USB_CFG_IMPLEMENT_FN_WRITEOUT=0, USB_CFG_HAVE_FLOWCONTROL=0,
        USB_CFG_LONG_TRANSFERS=0, USB_CFG_CHECK_CRC=0, USB_USE_FAST_CRC=0,
        USB_CFG_VENDOR_NAME_LEN=0, USB_CFG_DEVICE_NAME_LEN=0, USB_CFG_SERIAL_NUMBER_LEN=0,
        USB_CFG_DEVICE_CLASS=255, USB_CFG_DEVICE_SUBCLASS=0,
        USB_CFG_INTERFACE_CLASS=255, USB_CFG_INTERFACE_SUBCLASS=0, USB_CFG_INTERFACE_PROTOCOL=0,
        USB_CFG_DEVICE_VERSION='0x70, 0x04', USB_CFG_VENDOR_ID='0xd0, 0x16',
        USB_CFG_DEVICE_ID='0x53, 0x07', USB_CFG_MAX_BUS_POWER=100,
        USB_COUNT_SOF=0, USB_CFG_USE_SWITCH_STATEMENT=0, USB_CFG_CHECK_DATA_TOGGLING=toggle)
    (directory / 'usbconfig.h').write_text('#include "usbconfig-prototype.h"\n' + ''.join(
        f'#undef {key}\n#define {key} {value}\n' for key, value in config.items()))
    main = directory / 'main.c'
    main.write_text('''#include <avr/io.h>
#include <avr/interrupt.h>
#include "usbdrv.h"
usbMsgLen_t usbFunctionSetup(uchar data[8]) { (void)data; return 0; }
int main(void) { usbInit(); sei(); for(;;) { usbPoll(); } }
''')
    flags = ['avr-gcc', '-mmcu=attiny88', '-DF_CPU=16000000UL', '-DDEBUG_LEVEL=0',
             '-Os', '-g', '-gdwarf-2', '-ffunction-sections', '-fdata-sections',
             '-I' + str(directory), '-I' + str(upstream / 'usbdrv')]
    objects = []
    for source in (upstream / 'usbdrv/usbdrv.c', upstream / 'usbdrv/usbdrvasm.S', main):
        obj = directory / (source.stem + '.o')
        run(flags + ['-c', source, '-o', obj])
        objects.append(obj)
    elf, binary = directory / 'reference.elf', directory / 'reference.bin'
    run(['avr-gcc', '-mmcu=attiny88', '-Wl,--gc-sections',
         '-Wl,-Map=' + str(directory / 'reference.map'), *objects, '-o', elf])
    run(['avr-objcopy', '-O', 'binary', elf, binary])
    for name, arguments in (
            ('sizes.txt', ['avr-size', '-A', elf]),
            ('functions.txt', ['avr-nm', '-S', '--size-sort', elf]),
            ('disassembly.txt', ['avr-objdump', '-d', elf])):
        (directory / name).write_text(run(arguments))
    body = binary.read_bytes()
    result = dict(kind=f'vusb-toggle{toggle}', boot=0, size=len(body),
                  sha256=hashlib.sha256(body).hexdigest(), obj=str(elf), bin=str(binary),
                  elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                  symbols=symbols(elf), config=config)
    result['groups'] = native_partition(result['symbols'], result['size'])
    (directory / 'artifact.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    upstream, output = args.upstream.resolve(), args.output.resolve()
    if (output / 'measurement.json').exists():
        parser.error('Completed report already exists; choose a fresh output directory')
    if run(['git', '-C', upstream, 'rev-parse', 'HEAD']).strip() != PIN:
        parser.error('Upstream differs from the reviewed November9 pin')
    # Interpret Windows CRLF checkout and mounted executable bits consistently.
    if run(['git', '-c', 'core.filemode=false', '-c', 'core.autocrlf=true',
            '-C', upstream, 'status', '--porcelain']).strip():
        parser.error('Upstream checkout is modified')
    output.mkdir(parents=True, exist_ok=True)
    images = [build_native(upstream, output, toggle) for toggle in (0, 1)]
    for name, source, boot in (
            ('combined', 'variants/combined_rx', 0x1900),
            ('ack', 'variants/ack_terminal', 0x1800),
            ('strict', 'source', 0x1a40),
            ('archive', 'reference_pass35', 0x1a40),
            ('archive-same-placement', 'reference_pass35', 0x1900)):
        artifact = build(where=source, boot=boot)
        directory = output / name
        directory.mkdir(exist_ok=True)
        elf, binary = directory / 'receiver.elf', directory / 'receiver.body.bin'
        shutil.copyfile(artifact['obj'], elf)
        binary.write_bytes(Path(artifact['bin']).read_bytes()[boot:])
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == artifact['sha256']
        row = dict(kind=name, boot=boot, size=artifact['bytes'], sha256=artifact['sha256'],
                   obj=str(elf), bin=str(binary), symbols=symbols(elf), source=source, led='NONE',
                   elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())
        row['phy_span_bytes'] = row['symbols']['startup'] - row['symbols']['USB_handler']
        if name == 'combined':
            row['groups'] = loader_partition(row['symbols'], row['size'], boot)
        (directory / 'artifact.json').write_text(json.dumps(row, indent=2) + '\n')
        images.append(row)
    report = dict(upstream_commit=PIN, hardware_tested=False,
                  scope='No installation; native EP0 example has no loader commands',
                  partition='Disjoint physical code ranges; shared paths counted once',
                  compiler=run(['avr-gcc', '--version']).splitlines()[0],
                  assembler=run(['clang', '--version']).splitlines()[0],
                  loader_commit=optional_commit(ROOT),
                  loader_source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                                        for folder in ('source', 'vendor', 'variants/combined_rx', 'variants/ack_terminal',
                                                       'variants/strict_usb_verified', 'reference_pass35')
                                        for path in sorted((ROOT / folder).rglob('*'))
                                        if path.suffix in ('.S', '.inc', '.h')},
                  flags='-Os, function/data sections, gc-sections; no LTO or relax', images=images)
    (output / 'measurement.json').write_text(json.dumps(report, indent=2) + '\n')
    for image in images:
        print(image['kind'], image['size'], image['sha256'])
        if 'groups' in image:
            assert sum(image['groups'].values()) == image['size']
            print(json.dumps(image['groups'], sort_keys=True))


if __name__ == '__main__':
    main()
