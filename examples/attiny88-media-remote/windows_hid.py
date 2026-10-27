"""Discover and exchange reports with the Tiny88 vendor HID collection."""
import ctypes as ct
from ctypes import wintypes as wt
import os
import time
from protocol import FEATURE_BYTES, mapping_report, parse_mapping, parse_legacy, mute_report, test_report
from windows_types import GUID, function


class InterfaceData(ct.Structure):
    _fields_ = [('size', wt.DWORD), ('guid', GUID), ('flags', wt.DWORD), ('reserved', ct.c_void_p)]


class HidCaps(ct.Structure):
    _fields_ = [('usage', wt.USHORT), ('page', wt.USHORT), ('input_bytes', wt.USHORT),
                ('output_bytes', wt.USHORT), ('feature_bytes', wt.USHORT),
                ('reserved', wt.USHORT * 17), ('counts', wt.USHORT * 10)]


class RemoteDevice:
    def __init__(self, handle, hid, kernel, legacy=False):
        self.handle, self.hid, self.kernel = handle, hid, kernel
        self.legacy = legacy
        self.feature_bytes = 8 if legacy else FEATURE_BYTES
        self.legacy_loaded = False
        self.active_layer = 0

    @classmethod
    def find(cls):
        if os.name != 'nt':
            raise OSError('The desktop controller supports Windows only')
        hid = ct.WinDLL('hid.dll', use_last_error=True)
        setup = ct.WinDLL('setupapi.dll', use_last_error=True)
        kernel = ct.WinDLL('kernel32.dll', use_last_error=True)
        function(hid, 'HidD_GetHidGuid', None, ct.POINTER(GUID))
        function(hid, 'HidD_GetProductString', wt.BOOL, wt.HANDLE, ct.c_void_p, wt.ULONG)
        function(hid, 'HidD_GetPreparsedData', wt.BOOL, wt.HANDLE, ct.POINTER(ct.c_void_p))
        function(hid, 'HidD_FreePreparsedData', wt.BOOL, ct.c_void_p)
        function(hid, 'HidP_GetCaps', ct.c_int32, ct.c_void_p, ct.POINTER(HidCaps))
        function(hid, 'HidD_GetFeature', wt.BOOL, wt.HANDLE, ct.c_void_p, wt.ULONG)
        function(hid, 'HidD_SetFeature', wt.BOOL, wt.HANDLE, ct.c_void_p, wt.ULONG)
        function(hid, 'HidD_SetOutputReport', wt.BOOL, wt.HANDLE, ct.c_void_p, wt.ULONG)
        function(kernel, 'CreateFileW', wt.HANDLE, wt.LPCWSTR, wt.DWORD, wt.DWORD,
                 ct.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE)
        function(kernel, 'CloseHandle', wt.BOOL, wt.HANDLE)
        function(setup, 'SetupDiGetClassDevsW', wt.HANDLE, ct.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD)
        function(setup, 'SetupDiEnumDeviceInterfaces', wt.BOOL, wt.HANDLE, ct.c_void_p,
                 ct.POINTER(GUID), wt.DWORD, ct.POINTER(InterfaceData))
        function(setup, 'SetupDiGetDeviceInterfaceDetailW', wt.BOOL, wt.HANDLE,
                 ct.POINTER(InterfaceData), ct.c_void_p, wt.DWORD, ct.POINTER(wt.DWORD), ct.c_void_p)
        function(setup, 'SetupDiDestroyDeviceInfoList', wt.BOOL, wt.HANDLE)
        guid = GUID()
        hid.HidD_GetHidGuid(ct.byref(guid))
        invalid = ct.c_void_p(-1).value
        inventory = setup.SetupDiGetClassDevsW(ct.byref(guid), None, None, 0x12)
        if inventory == invalid:
            raise ct.WinError(ct.get_last_error())
        try:
            index = 0
            while True:
                item = InterfaceData()
                item.size = ct.sizeof(item)
                if not setup.SetupDiEnumDeviceInterfaces(inventory, None, ct.byref(guid), index, ct.byref(item)):
                    if ct.get_last_error() == 259:
                        return None
                    raise ct.WinError(ct.get_last_error())
                index += 1
                required = wt.DWORD()
                setup.SetupDiGetDeviceInterfaceDetailW(inventory, ct.byref(item), None, 0, ct.byref(required), None)
                if not required.value:
                    continue
                detail = ct.create_string_buffer(required.value)
                ct.cast(detail, ct.POINTER(wt.DWORD))[0] = 8 if ct.sizeof(ct.c_void_p) == 8 else 6
                if not setup.SetupDiGetDeviceInterfaceDetailW(inventory, ct.byref(item), detail,
                                                              required, None, None):
                    continue
                path = ct.wstring_at(ct.addressof(detail) + 4)
                if not any(identity in path.lower() for identity in ('vid_16c0&pid_27db', 'vid_16c0&pid_27d9')):
                    continue
                handle = kernel.CreateFileW(path, 0xc0000000, 3, None, 3, 0, None)
                if handle == invalid:
                    continue
                keep = False
                try:
                    product = ct.create_unicode_buffer(128)
                    if not hid.HidD_GetProductString(handle, product, ct.sizeof(product)) or product.value not in ('Tiny88 Media', 'Tiny88 Media 8'):
                        continue
                    legacy = product.value == 'Tiny88 Media'
                    preparsed, caps = ct.c_void_p(), HidCaps()
                    if not hid.HidD_GetPreparsedData(handle, ct.byref(preparsed)):
                        continue
                    try:
                        status = hid.HidP_GetCaps(preparsed, ct.byref(caps))
                        if status != 0x110000 or (caps.page, caps.usage, caps.feature_bytes, caps.output_bytes) != (0xff00, 1, 8 if legacy else FEATURE_BYTES, 2):
                            continue
                    finally:
                        hid.HidD_FreePreparsedData(preparsed)
                    keep = True
                    return cls(handle, hid, kernel, legacy)
                finally:
                    if not keep:
                        kernel.CloseHandle(handle)
        finally:
            setup.SetupDiDestroyDeviceInfoList(inventory)

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def get_mapping(self):
        buffer = ct.create_string_buffer(bytes((3,)) + bytes(self.feature_bytes - 1), self.feature_bytes)
        if not self.hid.HidD_GetFeature(self.handle, buffer, self.feature_bytes):
            raise ct.WinError(ct.get_last_error())
        self.legacy_loaded = bool(buffer.raw[1] & 0x40)
        self.active_layer = 0 if self.legacy else buffer.raw[2]
        return (parse_legacy if self.legacy else parse_mapping)(buffer.raw)

    def set_mapping(self, mapping, persist=True):
        if self.legacy:
            raise ValueError('Upload eight-button firmware before saving the expanded mapping')
        payload = mapping_report(mapping, persist)
        buffer = ct.create_string_buffer(payload, len(payload))
        if not self.hid.HidD_SetFeature(self.handle, buffer, len(payload)):
            raise ct.WinError(ct.get_last_error())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            actual, busy = self.get_mapping()
            if not busy:
                if actual != mapping:
                    raise OSError('Mapping readback did not match the selected actions')
                return
            time.sleep(0.02)
        raise TimeoutError('EEPROM save did not complete')

    def _send_output(self, payload):
        buffer = ct.create_string_buffer(payload, len(payload))
        if not self.hid.HidD_SetOutputReport(self.handle, buffer, len(payload)):
            raise ct.WinError(ct.get_last_error())

    def set_mute(self, muted):
        payload = mute_report(muted)
        self._send_output(payload)

    def test_button(self, button):
        if self.legacy:
            raise ValueError('Button testing requires eight-button firmware')
        payload = test_report(button)
        self._send_output(payload)

    def select_layer(self, layer):
        if self.legacy or not 0 <= layer < 3:
            raise ValueError('Layer selection requires eight-button firmware and layer 1..3')
        payload = bytes((6, layer))
        self._send_output(payload)
