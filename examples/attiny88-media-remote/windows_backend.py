"""Compatibility imports for existing controller integrations.

HID transport and Core Audio now have separate owners. Keep these imports for
scripts using the previous Windows backend module.
"""
from windows_types import GUID, function
from windows_hid import InterfaceData, HidCaps, RemoteDevice
from windows_audio import audio_state
