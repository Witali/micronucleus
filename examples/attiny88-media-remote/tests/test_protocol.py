import struct
import unittest
from protocol import DEFAULTS, mapping_report, parse_mapping, mute_report


class ProtocolTests(unittest.TestCase):
    def test_persistent_mapping_is_little_endian(self):
        self.assertEqual(mapping_report(DEFAULTS), bytes.fromhex('0381e200e900ea00'))

    def test_pending_save_and_complete_readback(self):
        for status, busy in ((0x11, True), (1, False)):
            self.assertEqual(parse_mapping(struct.pack('<BB3H', 3, status, *DEFAULTS)), (DEFAULTS, busy))

    def test_failed_or_foreign_reports_are_rejected(self):
        with self.assertRaises(OSError):
            parse_mapping(struct.pack('<BB3H', 3, 0x21, *DEFAULTS))
        for data in (b'', bytes(8), struct.pack('<BB3H', 3, 1, 0xffff, 0, 0),
                     struct.pack('<BB3H', 3, 0x41, *DEFAULTS)):
            with self.assertRaises(ValueError):
                parse_mapping(data)

    def test_only_supported_mapping_actions(self):
        for mapping in ((0xe2,), (1, 2, 3), (0xe2, 0xe9, 0xffff)):
            with self.assertRaises(ValueError):
                mapping_report(mapping)

    def test_mute_feedback_has_unknown_and_known_states(self):
        self.assertEqual(mute_report(None), b'\x02\x00')
        self.assertEqual(mute_report(False), b'\x02\x02')
        self.assertEqual(mute_report(True), b'\x02\x03')


if __name__ == '__main__':
    unittest.main()
