"""Background device exchange; no Tkinter calls or editor state."""
import queue
from windows_backend import RemoteDevice, audio_state


def run_worker(commands, messages, stopping, find_device=RemoteDevice.find, read_audio=audio_state):
    device = None
    try:
        while not stopping.is_set():
            try:
                if device is None:
                    device = find_device()
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
                    muted, _ = read_audio()
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
