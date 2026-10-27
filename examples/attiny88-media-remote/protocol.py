"""Eight-button HID report codec; no USB, platform or GUI dependencies."""
from dataclasses import dataclass

BUTTONS = 8
PRESETS = 3
FEATURE_BYTES = 53
PINS = ('PC0', 'PC1', 'PC2', 'PC3', 'PC4', 'PC5', 'PB0', 'PB1')
MEDIA_ACTIONS = {
    'Mute': 0xe2, 'Volume up': 0xe9, 'Volume down': 0xea,
    'Play / pause': 0xcd, 'Next track': 0xb5, 'Previous track': 0xb6, 'Stop': 0xb7,
    'Browser': 0x196, 'Email': 0x18a, 'Calculator': 0x192,
}
KEYS = {chr(65 + index): 4 + index for index in range(26)}
KEYS.update({str(value): 0x1d + value for value in range(1, 10)})
KEYS['0'] = 0x27
KEYS.update({
    'Enter': 0x28, 'Escape': 0x29, 'Backspace': 0x2a, 'Tab': 0x2b, 'Space': 0x2c,
    'Minus': 0x2d, 'Equals': 0x2e, 'Left bracket': 0x2f, 'Right bracket': 0x30,
    'Backslash': 0x31, 'Non-US hash': 0x32, 'Semicolon': 0x33, 'Apostrophe': 0x34,
    'Grave': 0x35, 'Comma': 0x36, 'Period': 0x37, 'Slash': 0x38, 'Caps Lock': 0x39,
    'Print Screen': 0x46, 'Scroll Lock': 0x47, 'Pause': 0x48, 'Insert': 0x49,
    'Home': 0x4a, 'Page Up': 0x4b, 'Delete': 0x4c, 'End': 0x4d, 'Page Down': 0x4e,
    'Right': 0x4f, 'Left': 0x50, 'Down': 0x51, 'Up': 0x52, 'Num Lock': 0x53,
    'Numpad Divide': 0x54, 'Numpad Multiply': 0x55, 'Numpad Subtract': 0x56,
    'Numpad Add': 0x57, 'Numpad Enter': 0x58, 'Numpad 0': 0x62,
    'Numpad Decimal': 0x63, 'Non-US backslash': 0x64, 'Menu': 0x65,
    'Numpad Equals': 0x67, 'Modifier only': 0,
})
KEYS.update({'F%d' % i: 0x39 + i for i in range(1, 13)})
KEYS.update({'F%d' % i: 0x68 + i - 13 for i in range(13, 25)})
KEYS.update({'Numpad %d' % i: 0x58 + i for i in range(1, 10)})
MODIFIERS = {'Ctrl': 1, 'Shift': 2, 'Alt': 4, 'Win': 8}


@dataclass(frozen=True)
class Action:
    kind: int = 0
    arg: int = 0
    code: int = 0

    def validate(self):
        if self.kind == 0:
            valid = self.arg == self.code == 0
        elif self.kind == 1:
            valid = 0 <= self.arg <= 15 and (4 <= self.code <= 0x73 or self.code == 0 and self.arg != 0)
        elif self.kind == 2:
            valid = 0 <= self.arg <= 255 and 0 <= self.code <= 255 and (self.arg << 8 | self.code) in MEDIA_ACTIONS.values()
        else:
            valid = False
        if not valid:
            raise ValueError('Unsupported or incomplete button action')
        return self

    @classmethod
    def media(cls, usage):
        return cls(2, usage >> 8, usage & 255).validate()

    @classmethod
    def key(cls, name, modifiers=0):
        return cls(1, modifiers, KEYS[name]).validate()


DISABLED = Action()
DEFAULT_MAPPING = tuple(Action.media(MEDIA_ACTIONS[name]) for name in ('Mute', 'Volume up', 'Volume down')) + (DISABLED,) * 5


@dataclass(frozen=True)
class Configuration:
    count: int
    cycle_button: int
    profiles: tuple

    def validate(self):
        if not 1 <= self.count <= PRESETS or self.cycle_button not in (*range(BUTTONS), 255):
            raise ValueError('Choose 1..3 layers and a valid switch button')
        if len(self.profiles) != PRESETS or any(len(profile) != BUTTONS for profile in self.profiles):
            raise ValueError('Each of the three stored layers needs eight bindings')
        for profile in self.profiles:
            for action in profile:
                action.validate()
        return self


DEFAULTS = Configuration(1, 7, (DEFAULT_MAPPING,) * PRESETS)


def action_label(action):
    if action.kind == 0:
        return 'Disabled'
    if action.kind == 2:
        return next(name for name, usage in MEDIA_ACTIONS.items() if usage == (action.arg << 8 | action.code))
    parts = [name for name, flag in MODIFIERS.items() if action.arg & flag]
    if action.code:
        parts.append(next((name for name, usage in KEYS.items() if usage == action.code), 'Key 0x%02X' % action.code))
    return '+'.join(parts)


def parse_action(text):
    normalized = text.strip().casefold()
    if normalized == 'disabled':
        return DISABLED
    for name, usage in MEDIA_ACTIONS.items():
        if normalized == name.casefold():
            return Action.media(usage)
    parts = [part.strip() for part in text.split('+')]
    mods = 0
    aliases = {name.casefold(): value for name, value in MODIFIERS.items()}
    while parts and parts[0].casefold() in aliases:
        mods |= aliases[parts.pop(0).casefold()]
    if not parts:
        return Action(1, mods, 0).validate()
    if len(parts) == 1:
        for name, usage in KEYS.items():
            if parts[0].casefold() == name.casefold():
                return Action(1, mods, usage).validate()
    raise ValueError('Unknown action: ' + text)


def mapping_report(config, persist=True):
    config.validate()
    data = bytearray((3, 0x83 if persist else 3, 0, config.count, config.cycle_button))
    for profile in config.profiles:
        for action in profile:
            word = (action.kind << 12) | (action.arg << 8) | action.code
            data.extend((word & 255, word >> 8))
    return bytes(data)


def parse_mapping(data):
    if len(data) != FEATURE_BYTES or data[0] != 3 or data[1] & 15 != 3 or data[1] & ~0x73:
        raise ValueError('Unknown eight-button layer protocol')
    if data[1] & 0x20:
        raise OSError('The device reported an EEPROM readback failure')
    actions = []
    for index in range(5, FEATURE_BYTES, 2):
        word = int.from_bytes(data[index:index + 2], 'little')
        actions.append(Action(word >> 12, (word >> 8) & 15, word & 255).validate())
    profiles = tuple(tuple(actions[start:start + BUTTONS]) for start in range(0, len(actions), BUTTONS))
    config = Configuration(data[3], data[4], profiles).validate()
    if data[2] >= config.count:
        raise ValueError('Invalid active layer returned by device')
    return config, bool(data[1] & 0x10)


def parse_legacy(data):
    if len(data) != 8 or data[0] != 3 or data[1] & 15 != 1 or data[1] & ~0x31:
        raise ValueError('Unknown legacy remote protocol')
    if data[1] & 0x20:
        raise OSError('Legacy firmware reported an EEPROM failure')
    mapping = []
    for index in range(2, 8, 2):
        usage = int.from_bytes(data[index:index + 2], 'little')
        mapping.append(Action.media(usage) if usage else DISABLED)
    first = tuple(mapping) + (DISABLED,) * 5
    return Configuration(1, 7, (first, DEFAULT_MAPPING, DEFAULT_MAPPING)), bool(data[1] & 0x10)


def mute_report(muted):
    return bytes((2, 0 if muted is None else 2 | int(bool(muted))))


def test_report(button):
    if not 0 <= button < BUTTONS:
        raise ValueError('Button index is outside 0..7')
    return bytes((5, 1 << button))
