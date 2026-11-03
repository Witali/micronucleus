"""Generate an experimental RX component from a verified, pinned V-USB source.

No upstream assembly is vendored by this tool. The caller supplies the original
file, or explicitly requests the pinned public download. This does not produce
a bootloader or a hardware-programming image.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
from urllib.request import urlopen

COMMIT = '801242072fa035e1839e3571df0d9a18e9cec95c'
UPSTREAM_PATH = 'usbdrv/usbdrvasm165.inc'
SOURCE_SHA256 = 'c49621176e700f98162c3db66fe49d110e471a6d984731f5cd314fe643119780'
SOURCE_GIT_BLOB = 'fb79742794342b2a453ab22c2913e09bb6dfc468'
URL = f'https://raw.githubusercontent.com/obdev/v-usb/{COMMIT}/{UPSTREAM_PATH}'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Pinned source transformation does not match exactly once')
    return text.replace(old, new, 1)


def within(text, begin, end, transform):
    start = text.index(begin)
    stop = text.index(end, start + len(begin))
    return text[:start] + transform(text[start:stop]) + text[stop:]


def phase_update(block, replacement):
    block, count = re.subn(r'^    or\s+phase, r0[^\n]*\n', replacement, block, flags=re.M)
    if count != 1:
        raise ValueError('Phase update transformation does not match exactly once')
    return block


def generate(data, raw_register=23, stuff4_delay=False):
    """Keep source identity and exact cold-path transformations reviewable."""
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('The supplied source differs from the pinned upstream SHA256')
    if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != SOURCE_GIT_BLOB:
        raise ValueError('Pinned upstream Git blob mismatch')
    if raw_register not in (0, 23):
        raise ValueError('Only the measured R0 control and R23 remap are supported')
    text = data.decode('utf-8')
    text = text[text.index('continueWithBit5:'):text.index('macro POP_STANDARD')]
    text = re.sub(r'~(0x[0-9a-fA-F]+)', r'(255 ^ \1)', text)
    # Baseline 16 MHz retime: earlier bit4 and no shared delay before bit7.
    text = once(text, 'didUnstuff5:                ;[   ]\n    nop2                    ;[074]\n',
                'didUnstuff5:                ;[   ]\n')
    text = once(text, 'didUnstuff3:                ;[   ]\n    breq    unstuff3        ;[042] *** unstuff escape\n    nop                     ;[043]\n',
                'didUnstuff3:                ;[   ]\n    breq    unstuff3        ;[042] *** unstuff escape\n')
    # Discard three normal votes; retain the sampling/read budget separately.
    for begin, end in [('rxLoop:', 'rxbit1:'), ('didUnstuff1:', 'didUnstuff2:'),
                       ('didUnstuff4:', '\n\n')]:
        text = within(text, begin, end, lambda b: phase_update(b, ''))
    # A delta contributes D− only if that SAME delta also has D+ set. Partial
    # GPIO observations cannot combine merely through the accumulator's OR.
    for begin, end in [('continueWithBit5:', '    sbrc    phase, USBMINUS'),
                       ('didUnstuff7:', '\nunstuff7:'),
                       ('didUnstuff0:', '\ndidUnstuff1:'),
                       ('didUnstuff2:', '\ndidUnstuff3:')]:
        text = within(text, begin, end,
                      lambda b: phase_update(b, '    sbrc r0, 2\n\\g<0>'))
    text = text.replace('    eor     phase, x1', '    eor     phase, phase')
    for begin, end in [('\nunstuff5:', '\nunstuff6:'),
                       ('\nunstuff2:', '\nunstuff3:'),
                       ('\nunstuff3:', '\nunstuff4:')]:
        text = within(text, begin, end, lambda b: phase_update(b, '    nop\n'))
    text = within(text, '\nunstuff7:', '\nunstuff5:',
                  lambda b: once(b, '    nop                     ;[088]\n', ''))
    text = once(text, '    lpm                     ;[059] optional nop3; modifies r0',
                '    nop2')
    # Move raw references without disturbing counter carry or bit-stuff flags.
    text = once(text, '    eor     x2, x1          ;[005]\n    in      r0, USBIN       ;[006] <-- phase\n',
                '    in      r0, USBIN\n    eor     x2, x1\n')
    text = once(text, '    subi    cnt, 1          ;[026] overflow check\n    brcs    overflow        ;[027]\n    in      r0, USBIN       ;[028] <-- phase\n',
                '    subi    cnt, 1\n    in      r0, USBIN\n    brcs    overflow\n')
    text = once(text, '    eor     r0, x1          ;[048]\n    in      r0, USBIN       ;[050] <-- phase\n',
                '    in      r0, USBIN\n    nop\n')
    text = once(text, '    eor     phase, phase       ;[067]\n    eor     x2, x1          ;[068]\n    bst     x2, USBMINUS    ;[069]\n    bld     shift, 6        ;[070]\ndidUnstuff6:                ;[   ]\n    in      r0, USBIN       ;[071] <-- phase\n',
                '    eor     x2, x1\n    bst     x2, USBMINUS\n    bld     shift, 6\ndidUnstuff6:\n    in      r0, USBIN\n    eor     phase, phase\n')
    text = within(text, '\nunstuff6:', '\nunstuff0:',
                  lambda b: once(b, '    nop2                    ;[078]\n', '    nop\n'))
    text = within(text, '\ndidUnstuff2:', '\ndidUnstuff3:',
                  lambda b: once(b, '    in      r0, USBIN       ;[039] <-- phase\n', ''))
    text = once(text, '    rjmp    continueWithBit5;[053]\n',
                '    nop\n    rjmp    continueWithBit5\n')
    text = once(text, '    sbrc    phase, USBMINUS',
                'pll_decision:\n    sbrc    phase, USBMINUS')
    # Upstream bracketed times no longer describe the retimed instructions.
    text = '\n'.join(line.split(';', 1)[0].rstrip() for line in text.splitlines()) + '\n'
    if stuff4_delay:
        # BF's steady-state stuffed symbol follows bit4. Keep the timed read
        # unchanged; one later clock corrects the short 95-clock byte path.
        text = once(text, '    ori     shift, 0x10\n    rjmp    didUnstuff4\n',
                    '    ori     shift, 0x10\n    nop\n    rjmp    didUnstuff4\n')
    if raw_register == 23:
        text = re.sub(r'\br0\b', 'r23', text)
    if re.search(r'^\s*lpm\b', text, flags=re.M):
        raise ValueError('Unexpected implicit R0-clobbering LPM remains')
    header = f'''/* Experimental, centered-entry receive-core component.
 * Derived from obdev/v-usb {COMMIT}, {UPSTREAM_PATH}.
 * Original copyright: OBJECTIVE DEVELOPMENT Software GmbH.
 * Upstream GPLv2/GPLv3/commercial licensing remains applicable.
 * Not a loader: SYNC, qualified EOP and protocol/Flash ownership are absent.
 * Raw phase uses R{raw_register}; the optional delay is a two-clock RJMP.
 */
#define x1 r18
#define x2 r19
#define x3 r20
#define phase r21
#define cnt r22
#define shift r16
#define USBIN 9
#define USBMINUS 1
#define USBMASK 6
#define nop2 rjmp .+0
    .text
    .org 0x1b00
    .global bootloader_start
bootloader_start:
'''
    footer = '''se0:
overflow:
usb_control_process_received_packet:
bootloader_poll_begin:
bootloader_start_application:
    ret
    .set USB_handler, rxLoop
'''
    return header + text + footer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--input', type=Path, help='Original pinned upstream .inc')
    group.add_argument('--download', action='store_true', help='Fetch only the pinned public source')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--raw-register', type=int, choices=(0, 23), default=23)
    parser.add_argument('--stuff4-delay', action='store_true',
                        help='Add the measured after-read stuffed4 delay (288-byte component)')
    args = parser.parse_args()
    data = urlopen(URL, timeout=30).read() if args.download else args.input.read_bytes()
    source = generate(data, args.raw_register, args.stuff4_delay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding='utf-8', newline='\n')
    args.output.with_suffix('.provenance.json').write_text(json.dumps(dict(
        upstream_commit=COMMIT, upstream_path=UPSTREAM_PATH, upstream_sha256=SOURCE_SHA256,
        upstream_git_blob=SOURCE_GIT_BLOB, generated_sha256=hashlib.sha256(source.encode()).hexdigest(),
        raw_register=args.raw_register, stuff4_delay=args.stuff4_delay), indent=2) + '\n')
    print(str(args.output))


if __name__ == '__main__':
    main()
