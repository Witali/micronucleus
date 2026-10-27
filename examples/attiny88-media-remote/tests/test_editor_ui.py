"""Opt-in real Tk smoke test; uses a fake device and never sends HID reports."""
import os
import queue
import unittest
from unittest.mock import patch
from protocol import Action, Configuration, DEFAULTS


@unittest.skipUnless(os.environ.get('TINY88_TEST_TK') == '1', 'Set TINY88_TEST_TK=1 for a hidden Tk test')
class EditorUiTests(unittest.TestCase):
    def test_render_edit_save_and_saved_binding_test(self):
        import tkinter as tk
        from tkinter import ttk
        import editor_ui
        profiles = [list(profile) for profile in DEFAULTS.profiles]
        profiles[0][0] = Action(1, 0, 0x66)
        config = Configuration(3, 7, tuple(tuple(profile) for profile in profiles))
        saved, tested, errors = [], [], []
        root = tk.Tk()
        root.withdraw()
        root.report_callback_exception = lambda *error: (errors.append(error[1]), root.destroy())

        def worker(commands, messages, stopping):
            messages.put(('connected', (config, False)))
            messages.put(('state', (2, 3, False)))
            while not stopping.is_set():
                try:
                    kind, value = commands.get(timeout=0.01)
                except queue.Empty:
                    continue
                if kind == 'save':
                    saved.append(value)
                    messages.put(('saved', value))
                elif kind == 'test':
                    tested.append(value)

        def guarded(callback):
            def invoke():
                try:
                    callback()
                except Exception as error:
                    errors.append(error)
                    root.destroy()
            return invoke

        def widgets():
            panel = root.winfo_children()[0]
            settings = panel.grid_slaves(row=2, column=0)[0]
            controls = [child for child in settings.winfo_children() if isinstance(child, ttk.Combobox)]
            return panel, controls

        def check_loaded():
            panel, (_, _, edit) = widgets()
            key = panel.grid_slaves(row=4, column=2)[0]
            self.assertEqual(key.get(), 'Key 0x66')
            self.assertEqual(edit.get(), '1')
            label = panel.grid_slaves(row=13, column=0)[0]
            self.assertEqual(root.getvar(str(label.cget('textvariable'))), 'Active layer on device: 3 / 3')
            panel.grid_slaves(row=14, column=0)[0].invoke()
            root.after(150, guarded(edit_layers))

        def edit_layers():
            self.assertEqual(saved, [config])  # Unknown usage survives a real UI save.
            panel, (_, _, edit) = widgets()
            key = panel.grid_slaves(row=4, column=2)[0]
            key.set('F13')
            panel.grid_slaves(row=4, column=6)[0].invoke()
            status = panel.grid_slaves(row=15, column=0)[0]
            self.assertIn('Save the edited configuration', root.getvar(str(status.cget('textvariable'))))
            self.assertEqual(tested, [])
            edit.set('2')
            edit.event_generate('<<ComboboxSelected>>', when='now')
            root.update()
            kind = panel.grid_slaves(row=4, column=1)[0]
            kind.set('Keyboard')
            kind.event_generate('<<ComboboxSelected>>', when='now')
            key.set('F14')
            edit.set('1')
            edit.event_generate('<<ComboboxSelected>>', when='now')
            root.update()
            self.assertEqual(key.get(), 'F13')
            panel.grid_slaves(row=14, column=0)[0].invoke()
            root.after(150, guarded(test_saved))

        def test_saved():
            self.assertEqual(saved[-1].profiles[0][0], Action.key('F13'))
            self.assertEqual(saved[-1].profiles[1][0], Action.key('F14'))
            panel, _ = widgets()
            panel.grid_slaves(row=4, column=6)[0].invoke()
            root.after(100, guarded(finish))

        def finish():
            self.assertEqual(tested, [(0, 0)])
            root.destroy()

        with patch.object(tk, 'Tk', return_value=root), patch.object(editor_ui, 'run_worker', worker):
            root.after(150, guarded(check_loaded))
            root.after(4000, guarded(lambda: self.fail('UI test timed out')))
            editor_ui.gui()
        if errors:
            raise errors[0]
