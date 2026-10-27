# Eight-button remote with three local layers

Targets MH-Tiny88: ATtiny88, external 16 MHz, USB D-/D+ on PD1/PD2, onboard
Mute LED on PD0. Buttons support media actions, ordinary keys and combinations
with left Ctrl/Shift/Alt/Win. Browser, Email and Calculator are HID Consumer
commands; the operating system decides how to handle them.

## Local layers

Configure one to three layers and reserve any button as the layer switch.
Every debounced press cycles through those layers entirely on the MCU, without
the desktop helper. The switch has the same role in every layer; selecting
None makes all eight buttons available for bindings.

Changing layers releases all previous keys and suppresses buttons already held
until released. Keyboard bindings stay held while the button is down; the host
handles key repeat. Six distinct keys plus modifiers fit a keyboard report.
More keys produce HID ErrorRollOver until the held count decreases. Duplicates
share key state. Queue overflow retains a release and the latest state.

The MCU starts in layer 1 after reset. Switching layers does not write EEPROM
or change the computer's input language. Letters still follow that language.

Defaults: one layer, button 8 as the switch, Mute/up/down on buttons 1..3,
all other bindings disabled. Edit additional layers in the controller.

## Wiring

| Button | MCU pin |
| --- | --- |
| 1 | PC0 |
| 2 | PC1 |
| 3 | PC2 |
| 4 | PC3 |
| 5 | PC4 |
| 6 | PC5 |
| 7 | PB0 |
| 8 | PB1 |

Each normally-open button connects GPIO through 1 kOhm, then the switch, to
GND. Internal pull-ups are enabled; debounce is 20 ms. The resistor limits a
mistaken high-output short to about 5 mA at 5 V. Match MCU port names to the
board schematic rather than assuming header labels.

| Layer indicator | MCU output |
| --- | --- |
| Layer 1 | PD3 |
| Layer 2 | PD4 |
| Layer 3 | PD5 |

Wire each output through its own 1 kOhm resistor to LED anode, with LED cathode
to GND. Exactly one output is high. Unused LEDs can be left unconnected.
The three outputs work without the PC helper. PD0 remains the onboard Mute
indicator. Constant single-bit PORTD updates preserve the USB bits.

## Windows controller

Run Python for Windows with Tkinter; no pip packages or custom HID driver:

~~~sh
python controller.py
~~~

Set Layer count and Switch button, choose Edit layer, and assign each row.
The reserved switch row is marked Layer switch. Save all layers to EEPROM
stores the complete configuration. The actual active layer is displayed
separately from the layer currently being edited.

Test exercises a saved button binding without physical wiring: it activates
the selected local layer and injects a 250 ms press through the debounce path.
Save edits before testing. Media presses last at least 40 ms; only volume
repeats, after 500 ms and then every 120 ms.

The app safely reads the old three-button firmware and disables saving/testing
until upgraded. The MCU also imports a valid old EEPROM mapping into layer 1
without automatically writing EEPROM.

Keep the helper running for the onboard LED to follow actual Windows mute
state. Without feedback for three seconds, that LED turns off (state unknown).
Local layers and their three indicator outputs work without this helper.

~~~sh
python controller.py --probe
python controller.py --layers 3 --cycle-button 8
python controller.py --set "Mute" "Volume up" "Volume down" "Ctrl+C" "Browser" "Email" "Calculator" "Disabled" --layer 1
python controller.py --set "Mute" "Volume up" "Volume down" "Ctrl+V" "F13" "F14" "F15" "Disabled" --layer 2
python controller.py --test 4 --layer 2
python controller.py --watch --seconds 15
~~~

The set/layers commands intentionally write EEPROM. Probe is read-only.
Cycle-button 0 disables the reserved switch. No network or automatic startup
service is used. The Windows batch launcher also runs the UI.

## Build and HID protocol

With Python 3.9+, AVR-GCC, AVR libc and binutils:

~~~sh
python3 build.py
python3 verify.py
~~~

Outputs: build/remote.hex for physical buttons and host-requested tests;
build/remote-test.hex additionally performs Mute/up/down at 5/7/9 seconds.
The automatic test uses the saved active bindings and changes audio state.

The new device is Tiny88 Media 8, VID/PID 16c0:27db, revision 0x0300, with
Consumer, Keyboard and vendor HID collections. The earlier hello application
remains independent. The shared IDs identify this local prototype.

| ID | Type | Total bytes | Meaning |
| --- | --- | ---: | --- |
| 1 | Input | 3 | Consumer usage, little-endian; zero releases |
| 4 | Input | 8 | ID, modifiers, six keycodes |
| 2 | Output | 2 | Mute: 0 unknown, 2 unmuted, 3 muted |
| 3 | Feature | 53 | All layers and current local layer |
| 5 | Output | 2 | Temporary test button bitmask |
| 6 | Output | 2 | Select active local layer, zero-based |

The report-protocol keyboard omits a reserved byte to fit the eight-byte
low-speed endpoint; it is not a boot keyboard. Feature header: ID, status,
active layer (read-only), layer count, switch button (0..7 or 255). Next are
48 bytes: three layers of eight 16-bit little-endian bindings. Encoding:
0 disabled; 0x1MKK keyboard with four modifier bits M; 0x2UUU Consumer usage.
Format is 3. SET status 0x83 saves, 0x03 applies volatile settings. GET flags:
0x10 saving, 0x20 readback failure, 0x40 imported legacy settings. All seven
packets of a configuration transfer are collected before applying it.

## EEPROM and upload

ATtiny88 has 64 EEPROM bytes. The record occupies 0x00..0x37 (56 bytes);
0x38..0x3F is untouched. It contains magic/version, count/switch settings,
48 binding bytes, CRC-16/CCITT and a final commit marker. Byte writes are
asynchronous, happen only on Save, and are read back before reporting success.

There is space for one complete record, so an interrupted save can lose the
previous settings. Invalid records load safe defaults. Keep the full backup.
Saving the new format deliberately replaces the settings area; legacy import
alone does not write it. Layer changes themselves cause no EEPROM wear.

Upload the original HEX with the profile-aware compact 3.0 programmer.
Images stay at 0x0000, preserve INT0 at 0x0002 when RESET/postscript are patched,
and fit below 0x1AFC. No bootloader/fuse/lock/EEPROM image is included.
The stock Micronucleus CLI does not support the installed compact 3.0 protocol.

The old [hardware record](HARDWARE_TEST.md) applies to the three-button version.
Expanded-version results are in [VALIDATION.md](VALIDATION.md).
The new firmware was also uploaded and its keyboard/layer behavior checked on
the board; details are in [HARDWARE_LAYERS.md](HARDWARE_LAYERS.md).
V-USB is reused unchanged from the sibling example's
[pinned driver](../common/usbdrv/UPSTREAM.md), including its
existing DATA CRC and USB suspend-power limitations.
