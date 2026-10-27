#!/usr/bin/env python3
"""Eight-button, three-layer controller. Layer switching itself runs on the MCU."""
import argparse
import queue
import threading
import time
from protocol import (Action, Configuration, DEFAULTS, DEFAULT_MAPPING, DISABLED,
                      MEDIA_ACTIONS, KEYS, MODIFIERS, PINS, action_label, parse_action)
from windows_backend import RemoteDevice, audio_state


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


def gui():
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('Tiny88 Media Remote')
    root.geometry('940x650')
    root.minsize(900, 620)
    root.configure(padx=22, pady=18)
    panel = ttk.Frame(root)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Eight-button remote', font=('Segoe UI', 18, 'bold')).grid(
        row=0, column=0, columnspan=7, sticky='w')
    ttk.Label(panel, text='Three local layers. The switch button and layer LEDs work without this app.').grid(
        row=1, column=0, columnspan=7, sticky='w', pady=(5, 14))
    settings = ttk.Frame(panel)
    settings.grid(row=2, column=0, columnspan=7, sticky='ew', pady=(0, 14))
    count_var, edit_var = tk.StringVar(value='1'), tk.StringVar(value='1')
    cycle_choices = ['None'] + ['Button %d (%s)' % (i + 1, pin) for i, pin in enumerate(PINS)]
    cycle_var = tk.StringVar(value=cycle_choices[8])
    ttk.Label(settings, text='Layer count').pack(side='left')
    count_box = ttk.Combobox(settings, textvariable=count_var, values=('1', '2', '3'), width=3, state='readonly')
    count_box.pack(side='left', padx=(8, 18))
    ttk.Label(settings, text='Switch button').pack(side='left')
    cycle_box = ttk.Combobox(settings, textvariable=cycle_var, values=cycle_choices, width=18, state='readonly')
    cycle_box.pack(side='left', padx=(8, 18))
    ttk.Label(settings, text='Edit layer').pack(side='left')
    edit_box = ttk.Combobox(settings, textvariable=edit_var, values=('1',), width=3, state='readonly')
    edit_box.pack(side='left', padx=(8, 0))
    for col, title in enumerate(('Button / GPIO', 'Type', 'Action / key', 'Ctrl', 'Shift', 'Alt / Win', 'Saved binding')):
        ttk.Label(panel, text=title).grid(row=3, column=col, sticky='w', padx=(0, 8), pady=(0, 6))

    rows = []
    profiles = [list(profile) for profile in DEFAULTS.profiles]
    shown_layer, shown_cycle = 0, 7
    saved_config = None
    connected = False
    messages, commands = queue.Queue(), queue.Queue()
    stopping = threading.Event()
    status = tk.StringVar(value='Waiting for Tiny88 Media...')
    live = tk.StringVar(value='Active layer: unknown')
    sound = tk.StringVar(value='Mute state: unknown')

    def row_action(row):
        kind, name = row['kind'].get(), row['value'].get()
        if kind == 'Disabled':
            return DISABLED
        if kind == 'Media':
            return Action.media(MEDIA_ACTIONS[name])
        modifiers = sum(flag for flag, variable in row['mods'] if variable.get())
        return Action.key(name, modifiers)

    def capture():
        for index, row in enumerate(rows):
            if index != shown_cycle:
                profiles[shown_layer][index] = row_action(row)

    def form_config():
        capture()
        cycle = cycle_choices.index(cycle_var.get()) - 1
        return Configuration(int(count_var.get()), 255 if cycle < 0 else cycle,
                             tuple(tuple(profile) for profile in profiles)).validate()

    def options(index, preserve=True):
        row = rows[index]
        kind = row['kind'].get()
        values = list(MEDIA_ACTIONS) if kind == 'Media' else list(KEYS) if kind == 'Keyboard' else ('Disabled',)
        old = row['value'].get()
        row['action_box'].configure(values=values, state='readonly' if kind in ('Media', 'Keyboard') else 'disabled')
        row['value'].set(old if preserve and old in values else values[0])
        for checkbox in row['checks']:
            checkbox.configure(state='normal' if kind == 'Keyboard' else 'disabled')

    def render():
        nonlocal shown_cycle
        cycle = cycle_choices.index(cycle_var.get()) - 1
        shown_cycle = 255 if cycle < 0 else cycle
        for index, row in enumerate(rows):
            action = profiles[shown_layer][index]
            if index == shown_cycle:
                row['kind'].set('Layer switch')
                row['type_box'].configure(state='disabled')
                row['value'].set('Next layer')
                row['action_box'].configure(values=('Next layer',), state='disabled')
                for checkbox in row['checks']:
                    checkbox.configure(state='disabled')
            else:
                kind = {0: 'Disabled', 1: 'Keyboard', 2: 'Media'}[action.kind]
                row['kind'].set(kind)
                row['type_box'].configure(state='readonly')
                options(index, False)
                if kind == 'Media':
                    row['value'].set(action_label(action))
                elif kind == 'Keyboard':
                    row['value'].set(next(name for name, code in KEYS.items() if code == action.code))
                for flag, variable in row['mods']:
                    variable.set(bool(action.arg & flag) if action.kind == 1 else False)

    def change_view(_=None):
        nonlocal shown_layer
        try:
            capture()
            count = int(count_var.get())
            edit_box.configure(values=tuple(str(i) for i in range(1, count + 1)))
            selected = min(int(edit_var.get()), count) - 1
            edit_var.set(str(selected + 1))
            shown_layer = selected
            render()
        except (ValueError, KeyError) as error:
            status.set(str(error))

    def save():
        try:
            config = form_config()
        except (ValueError, KeyError) as error:
            status.set(str(error))
            return
        commands.put(('save', config))
        save_button.configure(state='disabled')
        status.set('Saving all three layers to EEPROM and checking readback...')

    def test(index):
        try:
            if form_config() != saved_config:
                status.set('Save the edited configuration before testing a binding.')
                return
        except (ValueError, KeyError) as error:
            status.set(str(error))
            return
        commands.put(('test', (shown_layer, index)))
        status.set('Testing saved binding for button %d in layer %d...' % (index + 1, shown_layer + 1))

    for index, pin in enumerate(PINS):
        row = {'kind': tk.StringVar(value='Disabled'), 'value': tk.StringVar(value='Disabled'),
               'mods': [(flag, tk.BooleanVar()) for flag in MODIFIERS.values()]}
        ttk.Label(panel, text='%d  /  %s' % (index + 1, pin)).grid(row=index + 4, column=0, sticky='w', pady=7)
        row['type_box'] = ttk.Combobox(panel, textvariable=row['kind'],
                                      values=('Disabled', 'Media', 'Keyboard'), width=13, state='readonly')
        row['type_box'].grid(row=index + 4, column=1, padx=(0, 10))
        row['type_box'].bind('<<ComboboxSelected>>', lambda event, i=index: options(i, False))
        row['action_box'] = ttk.Combobox(panel, textvariable=row['value'], values=('Disabled',), width=21, state='disabled')
        row['action_box'].grid(row=index + 4, column=2, sticky='ew', padx=(0, 10))
        row['checks'] = []
        for j, (_, variable) in enumerate(row['mods']):
            column = 3 + j if j < 2 else 5
            holder = panel if j < 2 else row.get('alt_win')
            if j == 2:
                row['alt_win'] = ttk.Frame(panel)
                row['alt_win'].grid(row=index + 4, column=5, sticky='w')
                holder = row['alt_win']
            checkbox = ttk.Checkbutton(holder, variable=variable, text=('Alt' if j == 2 else 'Win') if j >= 2 else '')
            if j < 2:
                checkbox.grid(row=index + 4, column=column, sticky='w')
            else:
                checkbox.pack(side='left')
            row['checks'].append(checkbox)
        row['test'] = ttk.Button(panel, text='Test', command=lambda i=index: test(i), width=8, state='disabled')
        row['test'].grid(row=index + 4, column=6, sticky='ew')
        rows.append(row)

    ttk.Separator(panel).grid(row=12, column=0, columnspan=7, sticky='ew', pady=(10, 12))
    ttk.Label(panel, textvariable=live, font=('Segoe UI', 11, 'bold')).grid(row=13, column=0, columnspan=3, sticky='w')
    ttk.Label(panel, textvariable=sound).grid(row=13, column=3, columnspan=4, sticky='w')
    save_button = ttk.Button(panel, text='Save all layers to EEPROM', command=save, state='disabled')
    save_button.grid(row=14, column=0, columnspan=7, sticky='ew', pady=(14, 8))
    ttk.Label(panel, textvariable=status, wraplength=880).grid(row=15, column=0, columnspan=7, sticky='w')
    panel.columnconfigure(2, weight=1)
    count_box.bind('<<ComboboxSelected>>', change_view)
    edit_box.bind('<<ComboboxSelected>>', change_view)
    cycle_box.bind('<<ComboboxSelected>>', change_view)
    render()

    def worker():
        device = None
        try:
            while not stopping.is_set():
                try:
                    if device is None:
                        device = RemoteDevice.find()
                        if device is None:
                            stopping.wait(0.5)
                            continue
                        config, busy = device.get_mapping()
                        if busy:
                            device.close()
                            device = None
                            stopping.wait(0.1)
                            continue
                        messages.put(('connected', (config, device.legacy)))
                    try:
                        kind, value = commands.get_nowait()
                    except queue.Empty:
                        kind, value = None, None
                    if kind == 'save':
                        device.set_mapping(value, persist=True)
                        messages.put(('saved', value))
                    elif kind == 'test':
                        layer, button = value
                        device.select_layer(layer)
                        device.test_button(button)
                    try:
                        muted, _ = audio_state()
                    except OSError:
                        muted = None
                    device.set_mute(muted)
                    config, _ = device.get_mapping()
                    messages.put(('state', (device.active_layer, config.count, muted)))
                    stopping.wait(0.25)
                except (OSError, ValueError) as error:
                    if device is not None:
                        device.close()
                        device = None
                    while not commands.empty():
                        try:
                            commands.get_nowait()
                        except queue.Empty:
                            break
                    messages.put(('error', str(error)))
                    stopping.wait(1)
        finally:
            if device is not None:
                try:
                    device.set_mute(None)
                except OSError:
                    pass
                device.close()

    def refresh():
        nonlocal profiles, shown_layer, saved_config, connected
        try:
            while True:
                kind, value = messages.get_nowait()
                if kind == 'connected':
                    config, legacy = value
                    profiles = [list(profile) for profile in config.profiles]
                    saved_config, shown_layer, connected = config, 0, not legacy
                    count_var.set(str(config.count))
                    edit_var.set('1')
                    cycle_var.set(cycle_choices[0 if config.cycle_button == 255 else config.cycle_button + 1])
                    edit_box.configure(values=tuple(str(i) for i in range(1, config.count + 1)))
                    render()
                    status.set('3-button firmware connected. Upload the 8-button layer firmware to save or test.' if legacy
                               else 'Connected. Local layers loaded from device.')
                    save_button.configure(state='normal' if connected else 'disabled')
                    for row in rows:
                        row['test'].configure(state='normal' if connected else 'disabled')
                elif kind == 'saved':
                    saved_config = value
                    status.set('All layers saved to EEPROM and verified.')
                    save_button.configure(state='normal')
                elif kind == 'state':
                    active, count, muted = value
                    live.set('Active layer on device: %d / %d' % (active + 1, count))
                    sound.set('Mute state unknown' if muted is None else ('Sound muted / LED on' if muted else 'Sound on / LED off'))
                elif kind == 'error':
                    connected = False
                    status.set('Device error: ' + value)
                    save_button.configure(state='disabled')
                    for row in rows:
                        row['test'].configure(state='disabled')
        except queue.Empty:
            pass
        if not stopping.is_set():
            root.after(100, refresh)

    def close():
        stopping.set()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', close)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    refresh()
    root.mainloop()
    stopping.set()
    thread.join(timeout=2.5)


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
