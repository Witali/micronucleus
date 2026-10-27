import queue
import unittest
from device_session import run_worker
from protocol import DEFAULTS


class StopAfterWaits:
    def __init__(self, count=1):
        self.count, self.waits = count, []

    def is_set(self):
        return len(self.waits) >= self.count

    def wait(self, seconds):
        self.waits.append(seconds)


class Device:
    def __init__(self, legacy=False, busy=False, fail_mute=False):
        self.legacy, self.busy, self.fail_mute = legacy, busy, fail_mute
        self.active_layer, self.calls = 0, []

    def get_mapping(self):
        self.calls.append(('get',))
        return DEFAULTS, self.busy

    def set_mapping(self, config, persist):
        self.calls.append(('save', config, persist))

    def select_layer(self, layer):
        self.calls.append(('select', layer))
        self.active_layer = layer

    def test_button(self, button):
        self.calls.append(('test', button))

    def set_mute(self, muted):
        self.calls.append(('mute', muted))
        if self.fail_mute:
            raise OSError('Disconnected')

    def close(self):
        self.calls.append(('close',))


class SessionTests(unittest.TestCase):
    def run_session(self, devices, commands=(), waits=1, audio=None):
        incoming, outgoing = queue.Queue(), queue.Queue()
        for command in commands:
            incoming.put(command)
        stopping = StopAfterWaits(waits)
        run_worker(incoming, outgoing, stopping, iter(devices).__next__, audio or (lambda: (True, 0.5)))
        messages = []
        while not outgoing.empty():
            messages.append(outgoing.get_nowait())
        return messages, incoming, stopping.waits

    def test_save_readback_message_order_and_shutdown_release(self):
        device = Device()
        messages, _, waits = self.run_session([device], [('save', DEFAULTS)])
        self.assertEqual(messages, [('connected', (DEFAULTS, False)), ('saved', DEFAULTS),
                                    ('state', (0, 1, True))])
        self.assertEqual(device.calls, [('get',), ('save', DEFAULTS, True), ('mute', True),
                                        ('get',), ('mute', None), ('close',)])
        self.assertEqual(waits, [0.25])

    def test_layer_is_selected_before_test_press(self):
        device = Device()
        messages, _, _ = self.run_session([device], [('test', (2, 3))])
        self.assertEqual(device.calls[1:3], [('select', 2), ('test', 3)])
        self.assertEqual(messages[-1], ('state', (2, 1, True)))

    def test_busy_and_missing_device_preserve_pending_command(self):
        busy, ready = Device(busy=True), Device()
        messages, commands, waits = self.run_session([None, busy, ready], [('test', (0, 7))], waits=3)
        self.assertEqual(waits, [0.5, 0.1, 0.25])
        self.assertEqual(busy.calls, [('get',), ('close',)])
        self.assertEqual(ready.calls[1:3], [('select', 0), ('test', 7)])
        self.assertTrue(commands.empty())
        self.assertEqual(messages[0], ('connected', (DEFAULTS, False)))

    def test_audio_failure_reports_unknown_and_keeps_legacy_readable(self):
        def missing_audio():
            raise OSError('No endpoint')
        device = Device(legacy=True)
        messages, _, _ = self.run_session([device], audio=missing_audio)
        self.assertEqual(messages, [('connected', (DEFAULTS, True)), ('state', (0, 1, None))])
        self.assertEqual(device.calls[-2:], [('mute', None), ('close',)])

    def test_error_discards_queued_commands_and_reconnects(self):
        failed, ready = Device(fail_mute=True), Device()
        messages, commands, waits = self.run_session([failed, ready],
            [('test', (0, 0)), ('test', (1, 1))], waits=2)
        self.assertEqual([kind for kind, _ in messages], ['connected', 'error', 'connected', 'state'])
        self.assertEqual(messages[1], ('error', 'Disconnected'))
        self.assertEqual(failed.calls[-1], ('close',))
        self.assertNotIn(('test', 1), ready.calls)
        self.assertTrue(commands.empty())
        self.assertEqual(waits, [1, 0.25])
