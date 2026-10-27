# MH-Tiny88 media remote

Separate application firmware for the project's ATtiny88 board at external
16 MHz. The original `attiny88-hid-keyboard` example and its `hello` HEX remain
independent. This application sends USB Consumer Control usages, which do not
depend on keyboard layout.

## Buttons and wiring

| MCU pin | Default action | Consumer usage |
| --- | --- | --- |
| PC0 | Mute | `0x00E2` |
| PC1 | Volume up | `0x00E9` |
| PC2 | Volume down | `0x00EA` |

Connect each input through a **1 kOhm series resistor**, then a normally-open
button, to GND: `GPIO -- 1 kOhm -- switch -- GND`. The resistor limits current
if a programming error drives the pin high; at 5 V the bound is about 5 mA.
It does not interfere with the enabled internal pull-ups. These are MCU port
names; match them to the board's schematic rather than assuming header labels.
USB uses PD1/PD2; the onboard active-high LED uses PD0.

Inputs are sampled every millisecond with 20 ms debounce. A press sends an
action followed by a zero release report after at least 40 ms. Mute and media
transport actions do not repeat while held. Volume repeats after 500 ms, every
120 ms. A bounded eight-event queue absorbs endpoint delays; releases take
priority and cannot be displaced by queued presses.

## Two independent HEX files

From this directory, with Python 3.9+, AVR-GCC, AVR libc and AVR binutils:

```sh
python3 build.py
```

Pass `--toolchain DIR` when the AVR bin directory is not found automatically.
No USB devices are accessed during building.

- `build/remote.hex`: physical GPIO buttons only.
- `build/remote-test.hex`: the same GPIO handling plus one automatic test.

The test injects an 80 ms button press into the same debounce path at 5 seconds
(Mute), 7 seconds (Volume up), and 9 seconds (Volume down), after configuration.
Every action is released; the sequence stops after one pass per MCU startup.
A USB bus reset after the test has started cancels it rather than replaying
Mute. GPIO input remains active throughout. The test uses the **current button
mapping**; if EEPROM holds customized bindings it exercises those instead.

The test changes the computer's mute/volume state. It does not restore the
previous audio settings. With no physical buttons connected, the pull-ups keep
the GPIO inputs inactive.

## Windows configuration UI and mute LED

Run Python for Windows with Tkinter (included in the standard Python installer):

```sh
python controller.py
```

No pip dependencies, administrator privileges, or custom HID driver are needed.
Choose an action for each button and click **Save to EEPROM**. Available actions
are Mute, Volume up/down, Play/pause, Next/previous track, Stop and Disabled.
The program reads the saved mapping on connection and verifies each completed
save. Keep it running to synchronize the LED with the actual mute state of the
default Windows multimedia playback endpoint. It follows changes made by other
keyboards or Windows audio controls, and rechecks the default endpoint so output
device changes are also followed.

The LED turns on only for a recent, confirmed muted state. Without the helper,
or after feedback is lost for three seconds, it turns off because the state is
unknown. Sending a Consumer Mute command alone does not tell the board whether
the computer was already muted. The firmware never guesses by toggling the LED.

Console tools, using the same implementation:

```sh
python controller.py --probe
python controller.py --set "Mute" "Volume up" "Volume down"
python controller.py --watch --seconds 15
```

`--probe` is read-only. `--set` deliberately saves the bindings in EEPROM.
`--watch` waits for enumeration, synchronizes the LED, and logs audio-state
changes for the simulated-button smoke test. It never changes audio directly;
all audio changes during that test come from firmware HID input or other sources
on the computer. The helper has no startup-service installation or network access.

The firmware is a standard HID device (`16c0:27d9`, product **Tiny88 Media**).
Windows uses its built-in HID driver. Its two top-level collections separate
Consumer Control input from the vendor configuration/LED channel. The helper
checks VID/PID, product name, vendor usage page and report sizes before writing.
These shared IDs are for this local prototype, not a unique production identity;
allocate an appropriate identity/serial before distributing hardware. The
Windows helper is Windows-specific; standard media input also works through
Linux HID, subject to desktop media-key handling.

## EEPROM layout

Only EEPROM `0x00..0x1F` is reserved for mappings; `0x20..0x3F` is untouched.
Two 16-byte slots contain magic, format version, generation, three little-endian
usages, CRC-16/CCITT and a final commit marker. A save invalidates the inactive
slot, writes its payload one byte at a time, then commits its marker last.
The old slot stays intact until the new slot is valid. Interrupted saves select
the previous valid slot; CRC-invalid or unsupported records are ignored.

USB polling continues between EEPROM byte writes. After the last byte finishes,
the firmware reads back every record byte before reporting completion. Settings
are written only after a host save request, not on startup or button presses.
Defaults come from `config.h` if no valid EEPROM record exists. Hardware testing
or saving mappings can replace earlier application data in the reserved range;
keep the complete device backup before the first save.

## HID reports

| ID | Type | Complete report bytes | Purpose |
| --- | --- | ---: | --- |
| 1 | Input | 3 | ID, 16-bit Consumer usage; zero means release |
| 2 | Output | 2 | ID, flags: 0 unknown, 2 known unmuted, 3 known muted |
| 3 | Feature | 8 | ID, format/status, three 16-bit usage bindings |

Feature format is 1. SET with byte 1=`0x81` requests EEPROM persistence;
`0x01` applies a volatile mapping. GET byte 1 includes `0x10` while saving and
`0x20` on EEPROM readback failure. Unsupported actions are rejected.

## Uploading and verification

Use the installed profile-aware compact 3.0 programmer with an original HEX.
Applications are linked at `0x0000`; the host patches only RESET and the
loader's four-byte postscript while preserving the INT0 vector at `0x0002`.
Both builds are limited below `0x1AFC` and contain no bootloader, fuse, lock or
EEPROM image. Runtime EEPROM saves are separate from uploading the HEX.
The stock Micronucleus CLI does not support this board's compact 3.0 protocol.
The loader can start an installed application automatically six seconds after
its last USB access; prepare observation before completing an upload.

```sh
python3 verify.py
```

Offline checks cover real HID descriptors and report sizes, application/vector
preservation for all compact 3.0 profiles, unchanged V-USB source hashes, GPIO
debounce, repeat, endpoint backpressure, mapping validation, LED feedback expiry,
the exact three-action simulation, EEPROM interruption at every byte boundary,
CRC fallback/generation wrap, and host report encoding/validation.

V-USB is reused from the sibling example's pinned `usbdrv` without modifying
those files. Its license and source are documented in
[the vendor record](../attiny88-hid-keyboard/usbdrv/UPSTREAM.md).
The 16 MHz backend's incoming DATA CRC and USB suspend-power limitations remain.

The automatic test was uploaded and verified on the connected board: Windows
observed all three audio changes, HID feedback succeeded, and a persistent
mapping save completed with readback. See [the hardware test record](HARDWARE_TEST.md).
The tested build uses 4034 Flash bytes and 127 static SRAM bytes; the GPIO-only
build uses 3910 Flash bytes and 126 static SRAM bytes (AVR-GCC 7.3.0).
Visible LED state, cold-power persistence, physical button wiring and GUI
interaction remain to be checked; the controller was exercised in console mode.
