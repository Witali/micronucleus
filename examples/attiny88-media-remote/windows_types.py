"""ctypes primitives shared by the Windows HID and Core Audio adapters."""
import ctypes as ct
import uuid


class GUID(ct.Structure):
    _fields_ = [('data', ct.c_ubyte * 16)]

    @classmethod
    def parse(cls, text):
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


def function(library, name, result, *arguments):
    method = getattr(library, name)
    method.restype, method.argtypes = result, arguments
    return method
