import unittest
from editor_state import EditorState
from protocol import Action, Configuration, DEFAULTS, DISABLED, mapping_report, parse_mapping


class EditorTests(unittest.TestCase):
    def test_layer_edits_and_hidden_layers_survive_view_changes(self):
        editor = EditorState()
        editor.load(DEFAULTS)
        first = list(DEFAULTS.profiles[0])
        first[0], first[7] = Action.key('F13'), None
        editor.capture(first)
        editor.select_view(2, 3, 7)
        third = list(DEFAULTS.profiles[2])
        third[0] = Action.key('F15')
        editor.capture(third)
        editor.select_view(2, 1, 7)
        self.assertEqual(editor.shown_layer, 0)
        self.assertEqual(editor.configuration(1, 7).profiles[2][0], Action.key('F15'))
        self.assertEqual(editor.profiles[0][0], Action.key('F13'))
        self.assertEqual(editor.profiles[0][7], DISABLED)
        self.assertEqual(DEFAULTS.profiles[0][0], Action.media(0xe2))

    def test_changing_reserved_switch_preserves_its_underlying_binding(self):
        editor = EditorState()
        editor.load(DEFAULTS)
        editor.select_view(0, 3, 0)
        actions = [None] + [DISABLED] * 7
        editor.capture(actions)
        config = editor.configuration(3, 0)
        self.assertEqual(config.profiles[0][0], DEFAULTS.profiles[0][0])
        self.assertEqual(parse_mapping(mapping_report(config, False))[0], config)

    def test_testing_requires_saved_configuration_and_uses_edit_layer(self):
        editor = EditorState()
        self.assertFalse(editor.connected)
        editor.load(DEFAULTS)
        self.assertTrue(editor.connected)
        editor.select_view(0, 1, 7)
        self.assertEqual(editor.test_binding(DEFAULTS, 3), (0, 3))
        editor.profiles[0][3] = Action.key('F14')
        config = editor.configuration(1, 7)
        with self.assertRaisesRegex(ValueError, 'Save the edited configuration'):
            editor.test_binding(config, 3)
        editor.saved_config = config
        self.assertEqual(editor.test_binding(config, 3), (0, 3))

    def test_reconnect_reloads_device_settings_and_legacy_is_read_only(self):
        editor = EditorState()
        editor.load(DEFAULTS)
        editor.profiles[0][0] = Action.key('C', 1)
        editor.select_view(2, 3, 255)
        editor.connected = False
        editor.load(DEFAULTS, legacy=True)
        self.assertFalse(editor.connected)
        self.assertEqual(editor.shown_layer, 0)
        self.assertEqual(editor.configuration(1, 7), DEFAULTS)
