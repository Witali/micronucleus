"""Tkinter views and event handlers for the eight-button layer editor."""
import queue
import threading
from protocol import Action, DISABLED, MEDIA_ACTIONS, KEYS, MODIFIERS, PINS, action_label, key_name
from editor_state import EditorState
from device_session import run_worker


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
    editor = EditorState()
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
        editor.capture(row_action(row) if index != editor.shown_cycle else None
                       for index, row in enumerate(rows))

    def cycle_button():
        cycle = cycle_choices.index(cycle_var.get()) - 1
        return 255 if cycle < 0 else cycle

    def form_config():
        capture()
        return editor.configuration(int(count_var.get()), cycle_button())

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
        for index, row in enumerate(rows):
            action = editor.profiles[editor.shown_layer][index]
            if index == editor.shown_cycle:
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
                    row['value'].set(key_name(action.code))
                for flag, variable in row['mods']:
                    variable.set(bool(action.arg & flag) if action.kind == 1 else False)

    def change_view(_=None):
        try:
            capture()
            count = int(count_var.get())
            edit_box.configure(values=tuple(str(i) for i in range(1, count + 1)))
            editor.select_view(int(edit_var.get()) - 1, count, cycle_button())
            edit_var.set(str(editor.shown_layer + 1))
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
            binding = editor.test_binding(form_config(), index)
        except (ValueError, KeyError) as error:
            status.set(str(error))
            return
        commands.put(('test', binding))
        status.set('Testing saved binding for button %d in layer %d...' % (index + 1, editor.shown_layer + 1))

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

    def refresh():
        try:
            while True:
                kind, value = messages.get_nowait()
                if kind == 'connected':
                    config, legacy = value
                    editor.load(config, legacy)
                    count_var.set(str(config.count))
                    edit_var.set('1')
                    cycle_var.set(cycle_choices[0 if config.cycle_button == 255 else config.cycle_button + 1])
                    edit_box.configure(values=tuple(str(i) for i in range(1, config.count + 1)))
                    render()
                    status.set('3-button firmware connected. Upload the 8-button layer firmware to save or test.' if legacy
                               else 'Connected. Local layers loaded from device.')
                    save_button.configure(state='normal' if editor.connected else 'disabled')
                    for row in rows:
                        row['test'].configure(state='normal' if editor.connected else 'disabled')
                elif kind == 'saved':
                    editor.saved_config = value
                    status.set('All layers saved to EEPROM and verified.')
                    save_button.configure(state='normal')
                elif kind == 'state':
                    active, count, muted = value
                    live.set('Active layer on device: %d / %d' % (active + 1, count))
                    sound.set('Mute state unknown' if muted is None else ('Sound muted / LED on' if muted else 'Sound on / LED off'))
                elif kind == 'error':
                    editor.connected = False
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
    thread = threading.Thread(target=run_worker, args=(commands, messages, stopping), daemon=True)
    thread.start()
    refresh()
    root.mainloop()
    stopping.set()
    thread.join(timeout=2.5)
