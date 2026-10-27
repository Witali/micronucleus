"""Windows HID and read-only Core Audio access using Python's standard library."""
import ctypes as ct
from ctypes import wintypes as wt
import os
import time
import uuid
from protocol import mapping_report, parse_mapping, mute_report


class GUID(ct.Structure):
    _fields_ = [('data', ct.c_ubyte * 16)]

    @classmethod
    def parse(cls, text):
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


class InterfaceData(ct.Structure):
    _fields_ = [('size', wt.DWORD), ('guid', GUID), ('flags', wt.DWORD), ('reserved', ct.c_void_p)]


class HidCaps(ct.Structure):
    _fields_ = [('usage', wt.USHORT), ('page', wt.USHORT), ('input_bytes', wt.USHORT),
                ('output_bytes', wt.USHORT), ('feature_bytes', wt.USHORT),
                ('reserved', wt.USHORT * 17), ('counts', wt.USHORT * 10)]


def function(library, name, result, *arguments):
    method = getattr(library, name)
    method.restype, method.argtypes = result, arguments
    return method


class RemoteDevice:
    def __init__(self, handle, hid, kernel):
        self.handle, self.hid, self.kernel = handle, hid, kernel

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
                if 'vid_16c0&pid_27d9' not in path.lower():
                    continue
                handle = kernel.CreateFileW(path, 0xc0000000, 3, None, 3, 0, None)
                if handle == invalid:
                    continue
                keep = False
                try:
                    product = ct.create_unicode_buffer(128)
                    if not hid.HidD_GetProductString(handle, product, ct.sizeof(product)) or product.value != 'Tiny88 Media':
                        continue
                    preparsed, caps = ct.c_void_p(), HidCaps()
                    if not hid.HidD_GetPreparsedData(handle, ct.byref(preparsed)):
                        continue
                    try:
                        status = hid.HidP_GetCaps(preparsed, ct.byref(caps))
                        if status != 0x110000 or (caps.page, caps.usage, caps.feature_bytes, caps.output_bytes) != (0xff00, 1, 8, 2):
                            continue
                    finally:
                        hid.HidD_FreePreparsedData(preparsed)
                    keep = True
                    return cls(handle, hid, kernel)
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
        buffer = ct.create_string_buffer(bytes((3, 0, 0, 0, 0, 0, 0, 0)), 8)
        if not self.hid.HidD_GetFeature(self.handle, buffer, 8):
            raise ct.WinError(ct.get_last_error())
        return parse_mapping(buffer.raw)

    def set_mapping(self, mapping, persist=True):
        payload = mapping_report(mapping, persist)
        buffer = ct.create_string_buffer(payload, len(payload))
        if not self.hid.HidD_SetFeature(self.handle, buffer, len(payload)):
            raise ct.WinError(ct.get_last_error())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            actual, busy = self.get_mapping()
            if not busy:
                if actual != tuple(mapping):
                    raise OSError('Mapping readback did not match the selected actions')
                return
            time.sleep(0.02)
        raise TimeoutError('EEPROM save did not complete')

    def set_mute(self, muted):
        payload = mute_report(muted)
        buffer = ct.create_string_buffer(payload, len(payload))
        if not self.hid.HidD_SetOutputReport(self.handle, buffer, len(payload)):
            raise ct.WinError(ct.get_last_error())


def audio_state():
    """Read current default multimedia endpoint mute and volume; never change either."""
    if os.name != 'nt':
        raise OSError('Core Audio is available on Windows only')
    ole = ct.WinDLL('ole32.dll')
    function(ole, 'CoInitializeEx', ct.c_int32, ct.c_void_p, wt.DWORD)
    function(ole, 'CoUninitialize', None)
    function(ole, 'CoCreateInstance', ct.c_int32, ct.POINTER(GUID), ct.c_void_p,
             wt.DWORD, ct.POINTER(GUID), ct.POINTER(ct.c_void_p))

    def checked(result):
        if result < 0:
            raise OSError('Core Audio call failed (HRESULT 0x%08x)' % (result & 0xffffffff))

    def invoke(pointer, index, types, *arguments):
        table = ct.cast(pointer, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
        call = ct.WINFUNCTYPE(ct.c_int32, ct.c_void_p, *types)(table[index])
        checked(call(pointer, *arguments))

    initialized = ole.CoInitializeEx(None, 2)
    if initialized != ct.c_int32(0x80010106).value:
        checked(initialized)
    enumerator, device, endpoint = ct.c_void_p(), ct.c_void_p(), ct.c_void_p()
    try:
        clsid = GUID.parse('bcde0395-e52f-467c-8e3d-c4579291692e')
        iid = GUID.parse('a95664d2-9614-4f35-a746-de8db63617e6')
        checked(ole.CoCreateInstance(ct.byref(clsid), None, 23, ct.byref(iid), ct.byref(enumerator)))
        invoke(enumerator, 4, (ct.c_int, ct.c_int, ct.POINTER(ct.c_void_p)), 0, 1, ct.byref(device))
        iid = GUID.parse('5cdf2c82-841e-4546-9722-0cf74078229a')
        invoke(device, 3, (ct.POINTER(GUID), wt.DWORD, ct.c_void_p, ct.POINTER(ct.c_void_p)),
               ct.byref(iid), 23, None, ct.byref(endpoint))
        muted, volume = wt.BOOL(), ct.c_float()
        invoke(endpoint, 15, (ct.POINTER(wt.BOOL),), ct.byref(muted))
        invoke(endpoint, 9, (ct.POINTER(ct.c_float),), ct.byref(volume))
        return bool(muted.value), volume.value
    finally:
        for pointer in (endpoint, device, enumerator):
            if pointer.value:
                table = ct.cast(pointer, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
                ct.WINFUNCTYPE(wt.ULONG, ct.c_void_p)(table[2])(pointer)
        if initialized >= 0:
            ole.CoUninitialize()
