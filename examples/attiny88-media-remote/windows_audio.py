"""Read-only Windows default multimedia endpoint access."""
import ctypes as ct
from ctypes import wintypes as wt
import os
from windows_types import GUID, function


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
