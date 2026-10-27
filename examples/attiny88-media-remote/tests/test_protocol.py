import unittest
from protocol import (Action, Configuration, DEFAULTS, DEFAULT_MAPPING, DISABLED, MEDIA_ACTIONS,
                      action_label, mapping_report, parse_mapping, parse_legacy, parse_action,
                      mute_report, test_report, key_name)

class ProtocolTests(unittest.TestCase):
    def test_config_length_and_first_binding(self):
        data=mapping_report(DEFAULTS)
        self.assertEqual(len(data),53)
        self.assertEqual(data[:7],bytes.fromhex('0383000107e220'))

    def test_all_layers_and_last_button_roundtrip(self):
        profiles=[list(profile) for profile in DEFAULTS.profiles]
        profiles[1][4]=Action.key('C',1)
        profiles[2][7]=Action.media(MEDIA_ACTIONS['Browser'])
        config=Configuration(3,6,tuple(tuple(p) for p in profiles))
        data=bytearray(mapping_report(config,False));data[2]=2
        actual,busy=parse_mapping(data)
        self.assertEqual(actual,config)
        self.assertFalse(busy)
        self.assertEqual(data[-2:],bytes.fromhex('9621'))

    def test_busy_legacy_and_error_status(self):
        data=bytearray(mapping_report(DEFAULTS,False));data[1]=0x53
        self.assertEqual(parse_mapping(data),(DEFAULTS,True))
        data[1]=0x23
        with self.assertRaises(OSError):parse_mapping(data)

    def test_foreign_or_invalid_payloads(self):
        base=mapping_report(DEFAULTS,False)
        for change in (lambda d:d.__setitem__(0,7),lambda d:d.__setitem__(1,2),
                       lambda d:d.__setitem__(3,4),lambda d:d.__setitem__(4,8),
                       lambda d:d.__setitem__(52,0xff),lambda d:d.__setitem__(2,1)):
            data=bytearray(base);change(data)
            with self.assertRaises(ValueError):parse_mapping(data)
        with self.assertRaises(ValueError):parse_mapping(base[:-1])

    def test_keys_modifiers_and_launcher(self):
        self.assertEqual(parse_action('Ctrl+Shift+C'),Action.key('C',3))
        self.assertEqual(parse_action('Alt'),Action(1,4,0))
        self.assertEqual(action_label(parse_action('Win+F13')),'Win+F13')
        self.assertEqual(parse_action('Email'),Action.media(0x18a))
        self.assertEqual(parse_action('Disabled'),DISABLED)
        for action in (Action(1,0,0),Action(1,16,4),Action(2,15,255),Action(3,2,0)):
            with self.assertRaises(ValueError):action.validate()

    def test_every_valid_key_label_can_be_saved_again(self):
        # A valid usage can lack a friendly name, e.g. Power (0x66).
        for code in range(4, 0x74):
            with self.subTest(code=code):
                action = Action(1, 0, code).validate()
                self.assertEqual(Action.key(action_label(action)), action)
                self.assertEqual(Action.key(key_name(code), 3), Action(1, 3, code))
        self.assertEqual(Action.key(key_name(0), 1), Action(1, 1, 0))
        with self.assertRaises(ValueError):
            Action.key('Key 0xFF')

    def test_three_button_firmware_can_be_read(self):
        config,busy=parse_legacy(bytes.fromhex('0301e200e900ea00'))
        self.assertEqual(config,DEFAULTS)
        self.assertFalse(busy)

    def test_feedback_and_button_eight(self):
        self.assertEqual(mute_report(None),b'\x02\x00')
        self.assertEqual(mute_report(True),b'\x02\x03')
        self.assertEqual(test_report(7),b'\x05\x80')
        with self.assertRaises(ValueError):test_report(8)

if __name__=='__main__':unittest.main()
