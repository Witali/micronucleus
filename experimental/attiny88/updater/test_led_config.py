#!/usr/bin/env python3
"""Build LED profiles, preserve the pinned image, and reject unsafe settings.

Run test_led_config.mjs and test_usb_packets.mjs against the produced profiles
to execute the actual AVR instructions with MicroMusic's CPU.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROFILES = [
    ('verified', []),
    ('led-on', ['--led', 'on']),
    ('led-active-low', ['--led', 'active-low']),
    ('led-custom-high', ['-D', 'LED_MODE=ACTIVE_HIGH', '-D', 'LED_DDR_IO=4',
                         '-D', 'LED_PORT_IO=5', '-D', 'LED_PIN=3', '-D', 'LED_BLINK_MASK=0x80']),
    ('led-custom-low', ['--led', 'active-low', '-D', 'LED_DDR_IO=0x0d',
                        '-D', 'LED_PORT_IO=0x0e', '-D', 'LED_PIN=3', '-D', 'LED_BLINK_MASK=0x03']),
    *[(f'led-bit-{bit}-{mode}', ['--led', mode, '-D', f'LED_BLINK_MASK={1 << bit}'])
      for bit in range(8) for mode in ['on', 'active-low']],
]


def main():
    pinned = ROOT.parent/'variants/strict_usb_verified'
    snapshots = {name: (pinned/name).read_bytes() for name in
                 ['BOOTLOADER_BODY_1AC0_VERIFIED.bin', 'ISP_FULL_1AC0_VERIFIED_FRESH_ONLY.hex']}
    for name, flags in PROFILES:
        output = ROOT/'build'/name
        subprocess.run([sys.executable, str(ROOT/'build_verified.py'), *flags,
                        '--output-dir', str(output)], check=True, stdout=subprocess.PIPE)
        meta = json.loads((output/'firmware.json').read_text())
        body = (output/meta['body_file']).read_bytes()
        assert hashlib.sha256(body).hexdigest() == meta['body_sha256']
        assert len(body) == meta['code_bytes']
        assert meta['image_address'] + len(body) <= 8192
        assert meta['image_address'] % 64 == 0
        assert meta['application_bytes'] == meta['image_address'] - 4
        assert int.from_bytes(body[2:4], 'big') == meta['application_bytes']
        assert meta['application_bytes'] == (6844 if meta['led']['mode'] == 0 else 6780)
        if name.startswith('led-bit-'):
            assert meta['symbols']['led_tick_done'] - meta['symbols']['led_tick'] == 8
        elif meta['led']['mode'] and meta['led']['blink_mask'] & (meta['led']['blink_mask']-1):
            assert meta['symbols']['led_tick_done'] - meta['symbols']['led_tick'] == 12
    invalid = [
        ['LED_MODE=3'], ['LED_PIN=8'], ['LED_PIN=-1'],
        ['LED_PIN=1'], ['LED_PIN=2'], ['LED_BLINK_MASK=0'], ['LED_BLINK_MASK=256'],
        ['LED_DDR_IO=4', 'LED_PORT_IO=8'],
        ['LED_DDR_IO=0x0d', 'LED_PORT_IO=0x0e', 'LED_PIN=4'],
        ['LED_DDR_IO=4', 'LED_PORT_IO=5', 'LED_PIN=6'],
        ['LED_DDR_IO=7', 'LED_PORT_IO=8', 'LED_PIN=6'],
    ]
    for flags in invalid:
        defines = [value for flag in flags for value in ['-D', flag]]
        # An explicit invalid LED_MODE uses the same macro interface as users.
        mode = [] if flags[0].startswith('LED_MODE=') else ['--led', 'on']
        result = subprocess.run([sys.executable, str(ROOT/'build_verified.py'), *mode, *defines],
                                capture_output=True, text=True)
        assert result.returncode != 0 and 'error:' in result.stderr, (flags, result)
    for name, data in snapshots.items():
        assert (pinned/name).read_bytes() == data, 'Configured build replaced the pinned no-LED artifact'
    print(f'PASS: {len(PROFILES)} LED profiles, all eight single-bit masks/both polarities, '
          'page/descriptor limits, 11 rejected configurations, pinned artifacts unchanged')


if __name__ == '__main__':
    main()
