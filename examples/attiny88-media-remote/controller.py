#!/usr/bin/env python3
"""Windows media-remote GUI, EEPROM mapper and mute LED synchronizer. No pip packages."""
import argparse
import queue
import threading
import time
from protocol import ACTIONS
from windows_backend import RemoteDevice, audio_state


def watch(seconds, wait):
    deadline = time.monotonic() + wait
    device = None
    print('Waiting for Tiny88 Media...', flush=True)
    while device is None and time.monotonic() < deadline:
        device = RemoteDevice.find()
        if device is None:
            time.sleep(0.2)
    if device is None:
        raise SystemExit('Tiny88 Media was not connected before the timeout')
    try:
        mapping, busy = device.get_mapping()
        print('Connected; mapping:', ', '.join(next(name for name, code in ACTIONS.items() if code == value)
                                               for value in mapping), flush=True)
        print('EEPROM busy:', busy, flush=True)
        started = time.monotonic()
        previous = None
        while seconds <= 0 or time.monotonic() - started < seconds:
            try:
                muted, volume = audio_state()
            except OSError:
                device.set_mute(None)
                raise
            device.set_mute(muted)
            state = muted, round(volume, 4)
            if state != previous:
                print('t=%.2fs muted=%s volume=%.4f' % (time.monotonic() - started, muted, volume), flush=True)
                previous = state
            time.sleep(0.1)
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
    root.geometry('520x370')
    root.minsize(490, 350)
    root.configure(padx=24, pady=20)
    panel = ttk.Frame(root)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Media remote', font=('Segoe UI', 18, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w')
    ttk.Label(panel, text='Choose an action for each button. Save writes EEPROM.').grid(
        row=1, column=0, columnspan=2, pady=(6, 18), sticky='w')
    selections = []
    names = list(ACTIONS)
    for i, (pin, default) in enumerate(zip(('PC0', 'PC1', 'PC2'), ('Mute', 'Volume up', 'Volume down'))):
        ttk.Label(panel, text='Button %d  /  %s' % (i + 1, pin)).grid(row=i + 2, column=0, sticky='w', pady=6)
        variable = tk.StringVar(value=default)
        ttk.Combobox(panel, textvariable=variable, values=names, state='readonly', width=23).grid(
            row=i + 2, column=1, sticky='ew', pady=6)
        selections.append(variable)
    status = tk.StringVar(value='Waiting for Tiny88 Media...')
    sound = tk.StringVar(value='Mute state: unknown')
    ttk.Label(panel, textvariable=sound, font=('Segoe UI', 11, 'bold')).grid(
        row=5, column=0, columnspan=2, sticky='w', pady=(18, 8))
    ttk.Label(panel, textvariable=status, wraplength=465).grid(row=7, column=0, columnspan=2, sticky='w', pady=(12, 0))
    messages, commands = queue.Queue(), queue.Queue()
    stopping = threading.Event()

    def save():
        commands.put(tuple(ACTIONS[selection.get()] for selection in selections))
        button.configure(state='disabled')
        status.set('Saving and checking EEPROM...')

    button = ttk.Button(panel, text='Save to EEPROM', command=save, state='disabled')
    button.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(8, 0))
    panel.columnconfigure(1, weight=1)

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
                        mapping, busy = device.get_mapping()
                        if busy:
                            device.close(); device = None
                            stopping.wait(0.1)
                            continue
                        messages.put(('connected', mapping))
                    try:
                        mapping = commands.get_nowait()
                    except queue.Empty:
                        mapping = None
                    if mapping is not None:
                        device.set_mapping(mapping, persist=True)
                        messages.put(('saved', mapping))
                    try:
                        muted, _ = audio_state()
                    except OSError:
                        muted = None
                    device.set_mute(muted)
                    messages.put(('mute', muted))
                    stopping.wait(0.25)
                except (OSError, ValueError) as error:
                    if device is not None:
                        device.close(); device = None
                    while not commands.empty():
                        try: commands.get_nowait()
                        except queue.Empty: break
                    messages.put(('error', str(error)))
                    stopping.wait(1)
        finally:
            if device is not None:
                try: device.set_mute(None)
                except OSError: pass
                device.close()

    def refresh():
        try:
            while True:
                kind, value = messages.get_nowait()
                if kind in ('connected', 'saved'):
                    for selection, code in zip(selections, value):
                        selection.set(next(name for name, action in ACTIONS.items() if action == code))
                    status.set('Connected. Settings loaded from device.' if kind == 'connected' else 'Saved to EEPROM and verified.')
                    button.configure(state='normal')
                elif kind == 'mute':
                    sound.set('Mute state: unknown' if value is None else ('Sound muted — LED on' if value else 'Sound on — LED off'))
                elif kind == 'error':
                    status.set('Disconnected or device error: ' + value)
                    sound.set('Mute state: unknown')
                    button.configure(state='disabled')
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
    mode.add_argument('--watch', action='store_true', help='Console mute sync and audio-state log')
    mode.add_argument('--probe', action='store_true', help='Read mapping without changing EEPROM')
    mode.add_argument('--set', nargs=3, choices=list(ACTIONS), metavar='ACTION', help='Save three actions to EEPROM')
    mode.add_argument('--audio-state', action='store_true', help='Read Windows audio only')
    parser.add_argument('--seconds', type=float, default=0, help='Watch duration after connection; 0 runs until Ctrl+C')
    parser.add_argument('--wait', type=float, default=120, help='Seconds to wait for the remote in watch mode')
    args = parser.parse_args()
    if args.audio_state:
        muted, volume = audio_state()
        print('muted=%s volume=%.4f' % (muted, volume))
    elif args.watch:
        watch(args.seconds, args.wait)
    elif args.probe or args.set:
        device = RemoteDevice.find()
        if device is None:
            raise SystemExit('Tiny88 Media is not connected')
        try:
            if args.set:
                device.set_mapping(tuple(ACTIONS[name] for name in args.set))
            mapping, busy = device.get_mapping()
            print('Mapping:', ', '.join(next(name for name, code in ACTIONS.items() if code == value) for value in mapping))
            print('EEPROM busy:', busy)
        finally:
            device.close()
    else:
        gui()


if __name__ == '__main__':
    main()
