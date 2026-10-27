"""Local editing state, independent of Tkinter and the device's active layer."""
from protocol import Configuration, DEFAULTS


class EditorState:
    def __init__(self):
        self.load(DEFAULTS)
        self.saved_config = None
        self.connected = False

    def load(self, config, legacy=False):
        self.profiles = [list(profile) for profile in config.profiles]
        self.shown_layer = 0
        self.shown_cycle = config.cycle_button
        self.saved_config = config
        self.connected = not legacy

    def capture(self, actions):
        for index, action in enumerate(actions):
            if index != self.shown_cycle:
                self.profiles[self.shown_layer][index] = action

    def select_view(self, layer, count, cycle):
        self.shown_layer = min(layer, count - 1)
        self.shown_cycle = cycle

    def configuration(self, count, cycle):
        return Configuration(count, cycle, tuple(tuple(profile) for profile in self.profiles)).validate()

    def test_binding(self, config, index):
        if config != self.saved_config:
            raise ValueError('Save the edited configuration before testing a binding.')
        return self.shown_layer, index
