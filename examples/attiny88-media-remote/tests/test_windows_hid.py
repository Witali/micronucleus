import ctypes as ct
import unittest
from unittest.mock import Mock
import windows_backend
from windows_hid import RemoteDevice
from windows_audio import audio_state
from protocol import DEFAULTS, mapping_report


class HidTransportTests(unittest.TestCase):
    def make_device(self, legacy=False):
        hid, kernel = Mock(), Mock()
        return RemoteDevice(123, hid, kernel, legacy), hid, kernel

    def test_old_imports_keep_the_same_device_and_audio_api(self):
        self.assertIs(windows_backend.RemoteDevice, RemoteDevice)
        self.assertIs(windows_backend.audio_state, audio_state)

    def test_output_report_payloads_and_idempotent_close(self):
        device, hid, kernel = self.make_device()
        payloads = []
        hid.HidD_SetOutputReport.side_effect = lambda handle, buffer, size: payloads.append(
            (handle, ct.string_at(buffer, size))) or True
        device.set_mute(True)
        device.set_mute(None)
        device.test_button(7)
        device.select_layer(2)
        self.assertEqual(payloads, [(123, b'\x02\x03'), (123, b'\x02\x00'),
                                    (123, b'\x05\x80'), (123, b'\x06\x02')])
        device.close()
        device.close()
        kernel.CloseHandle.assert_called_once_with(123)

    def test_feature_read_tracks_active_layer_busy_and_legacy_import(self):
        device, hid, _ = self.make_device()
        data = bytearray(mapping_report(DEFAULTS, False))
        data[1] = 0x53  # Protocol 3, busy and imported legacy mapping.
        def get(handle, buffer, size):
            self.assertEqual((handle, size), (123, 53))
            self.assertEqual(buffer.raw[0], 3)
            ct.memmove(buffer, bytes(data), size)
            return True
        hid.HidD_GetFeature.side_effect = get
        self.assertEqual(device.get_mapping(), (DEFAULTS, True))
        self.assertTrue(device.legacy_loaded)
        self.assertEqual(device.active_layer, 0)

    def test_legacy_firmware_is_readable_and_rejects_expanded_writes(self):
        device, hid, _ = self.make_device(legacy=True)
        data = bytes.fromhex('0301e200e900ea00')
        hid.HidD_GetFeature.side_effect = lambda handle, buffer, size: ct.memmove(buffer, data, size) or True
        self.assertEqual(device.get_mapping(), (DEFAULTS, False))
        for operation in (lambda: device.set_mapping(DEFAULTS), lambda: device.test_button(0),
                          lambda: device.select_layer(0)):
            with self.assertRaises(ValueError):
                operation()
        hid.HidD_SetFeature.assert_not_called()
        hid.HidD_SetOutputReport.assert_not_called()

    def test_persist_flag_and_readback_verification(self):
        device, hid, _ = self.make_device()
        payloads = []
        hid.HidD_SetFeature.side_effect = lambda handle, buffer, size: payloads.append(ct.string_at(buffer, size)) or True
        device.get_mapping = Mock(return_value=(DEFAULTS, False))
        device.set_mapping(DEFAULTS, persist=True)
        device.set_mapping(DEFAULTS, persist=False)
        self.assertEqual(payloads, [mapping_report(DEFAULTS, True), mapping_report(DEFAULTS, False)])
        device.get_mapping.return_value = (None, False)
        with self.assertRaisesRegex(OSError, 'readback did not match'):
            device.set_mapping(DEFAULTS)
