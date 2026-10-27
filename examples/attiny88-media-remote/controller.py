#!/usr/bin/env python3
"""Eight-button, three-layer controller. Layer switching itself runs on the MCU."""
import argparse
import time
from protocol import Configuration, action_label, parse_action
from editor_ui import gui
from windows_hid import RemoteDevice
from windows_audio import audio_state


def wait_device(wait):
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        device = RemoteDevice.find()
        if device is not None:
            return device
        time.sleep(0.2)
    raise SystemExit('Tiny88 Media was not connected before the timeout')


def watch(seconds, wait):
    print('Waiting for Tiny88 Media...', flush=True)
    device = wait_device(wait)
    try:
        config, _ = device.get_mapping()
        print('Firmware:', 'legacy / 3 buttons' if device.legacy else '8 buttons / local layers', flush=True)
        started, previous = time.monotonic(), None
        while seconds <= 0 or time.monotonic() - started < seconds:
            muted, volume = audio_state()
            device.set_mute(muted)
            config, _ = device.get_mapping()
            state = muted, round(volume, 4), device.active_layer
            if state != previous:
                print('t=%.2fs muted=%s volume=%.4f layer=%d/%d' %
                      (time.monotonic() - started, muted, volume, device.active_layer + 1, config.count), flush=True)
                previous = state
            time.sleep(0.2)
    finally:
        try:
            device.set_mute(None)
        except OSError:
            pass
        device.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--watch', action='store_true')
    mode.add_argument('--probe', action='store_true')
    mode.add_argument('--set', nargs=8, metavar='ACTION', help='Eight bindings for the selected layer')
    mode.add_argument('--test', type=int, choices=range(1, 9), help='Test one saved binding')
    mode.add_argument('--audio-state', action='store_true')
    parser.add_argument('--layer', type=int, choices=(1, 2, 3), default=1)
    parser.add_argument('--layers', type=int, choices=(1, 2, 3))
    parser.add_argument('--cycle-button', type=int, choices=range(0, 9), help='0 disables the layer switch')
    parser.add_argument('--seconds', type=float, default=0)
    parser.add_argument('--wait', type=float, default=120)
    args = parser.parse_args()
    if args.audio_state:
        muted, volume = audio_state()
        print('muted=%s volume=%.4f' % (muted, volume))
    elif args.watch:
        watch(args.seconds, args.wait)
    elif args.probe or args.set or args.test or args.layers is not None or args.cycle_button is not None:
        device = RemoteDevice.find()
        if device is None:
            raise SystemExit('Tiny88 Media is not connected')
        try:
            config, busy = device.get_mapping()
            if args.set or args.layers is not None or args.cycle_button is not None:
                profiles = list(config.profiles)
                if args.set:
                    profiles[args.layer - 1] = tuple(parse_action(text) for text in args.set)
                count = config.count if args.layers is None else args.layers
                cycle = config.cycle_button if args.cycle_button is None else (255 if args.cycle_button == 0 else args.cycle_button - 1)
                device.set_mapping(Configuration(count, cycle, tuple(profiles)))
                config, busy = device.get_mapping()
            if args.test:
                device.select_layer(args.layer - 1)
                device.test_button(args.test - 1)
            print('Firmware:', 'legacy / 3 buttons' if device.legacy else '8 buttons / local layers')
            print('Layers:', config.count, 'active:', device.active_layer + 1, 'switch:', config.cycle_button + 1 if config.cycle_button != 255 else 'disabled')
            for index, profile in enumerate(config.profiles[:config.count]):
                print('Layer %d:' % (index + 1), ', '.join(action_label(action) for action in profile))
            print('EEPROM busy:', busy)
        finally:
            device.close()
    else:
        gui()


if __name__ == '__main__':
    main()
