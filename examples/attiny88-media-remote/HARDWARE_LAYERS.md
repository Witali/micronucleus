# Eight-button local-layer hardware checks, 2026-10-27

The GPIO-only expanded application was uploaded to the connected MH-Tiny88
through the recognized compact 3.0 no-LED loader at 0x1B80. Two complete Flash
and EEPROM reads matched before writing. Private backups remain outside Git.

The tested original remote.hex has SHA-256
7aff437db9c8100b15816b4de7487c23fc9b81d1e2f197909ae16acae71da298.
It uses 5506 Flash bytes and 308 static SRAM bytes with AVR-GCC 7.3.0.
The complete installed application matched readback, including its patched
RESET and postscript. The entire loader and EEPROM were unchanged at upload.

Windows enumerated the expanded Consumer, Keyboard and vendor HID device.
The controller read the complete 53-byte feature report. The existing imported
bindings were saved in the new EEPROM format and read back without busy/error
flags.

For a bounded test, three temporary layers assigned button 4 to F13, F14 and
F15 respectively. The test injected only the corresponding button through the
same debounce path used by GPIO. Windows GetAsyncKeyState, queried only for
those three known test keys, independently observed each press and release.
No other keyboard input or editor text was read.

Test presses of the configured layer switch, button 8, cycled the actual MCU
layer from 1 to 2, 2 to 3 and 3 to 1. The host did not issue layer selection
between those switch presses. It only read back the MCU's active layer and
checked which saved binding the next button press produced.

Afterward, the original bindings were restored and independently read back;
the device was left in layer 1. The saved configuration has one enabled layer,
button 8 reserved as the layer switch, Mute/up/down on buttons 1..3 and other
bindings disabled. Additional layers can be enabled and configured in the UI.
The temporary F13/F14/F15 bindings are not left active or saved.

The expanded Tkinter window was opened and visually inspected on Windows.
Its compatibility mode correctly read the older firmware before upgrading and
disabled new-format writes. The live native HID/Core Audio paths were also
exercised through console modes.

External button wiring and the three physical layer LEDs were not connected
or observed in this check. Offline disassembly checks confirm atomic SBI/CBI
updates for PD3, PD4 and PD5, preserving USB bits. Cold-power EEPROM persistence
was not separately tested; interrupted-save and CRC fallback paths passed
native tests. Mute LED visibility remains a separate physical observation.
