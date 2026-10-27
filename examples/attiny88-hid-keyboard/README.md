# MH-Tiny88 HID keyboard demonstration

An ordinary application for the project's MH-Tiny88 board: ATtiny88, external
16 MHz clock, USB D- on PD1, USB D+ on PD2, active-high onboard LED on PD0.
It enumerates as a USB boot keyboard named **Tiny88 Keyboard** (`16c0:27db`).

After USB configuration, the application waits five seconds and presses the
physical H, E, L, L, O keys once. Each key is held for 40 ms, followed by a
release and an 80 ms gap. It sends no Enter or modifier keys. The final report
releases all keys, and the LED turns on. Reports wait for endpoint availability;
USB processing continues throughout the delay and demonstration.

Open a text editor and focus a blank document **before** connecting or starting
the application. Select an English keyboard layout and turn Caps Lock off to
see `hello`. HID sends key positions; the host's current layout and lock state
determine the actual characters. Power-cycle/reset the MCU to run it again.
A USB bus reset after typing has started aborts the demonstration and releases
the report state without replaying it; this also marks the demonstration finished.

## Build

Install Python 3.9+, AVR-GCC, AVR libc, and AVR binutils. From this directory:

```sh
python3 build.py
```

On Windows, `python build.py` also searches Arduino's AVR-GCC installation.
If necessary, pass `--toolchain` with the directory containing `avr-gcc` and
`avr-objcopy`. The script never opens a USB device. Outputs are ignored under
`build/`: `keyboard.hex`, `keyboard.elf`, `keyboard.bin`, and `keyboard.map`.
No network access or additional Python packages are needed for the build.

Change `KEYBOARD_START_DELAY_MS` in `keyboard.h` to adjust the starting delay.
Change `demo_keys` in `keyboard.c` to send different USB HID usage codes.
The example's fixed eight-byte boot report has modifier, reserved, and six
keycode bytes; only the first keycode slot is used by this demonstration.

## Loading with the installed compact 3.0 loader

The HEX is an **original application linked at `0x0000`**. It is not a complete
device image or a bootloader update. Use the existing profile-aware compact
3.0 programmer with its original HEX input. The programmer patches only RESET
and its four-byte postscript, preserving the application's INT0 vector at
`0x0002`. See the [application layout contract](../../experimental/attiny88/compact/docs/APPLICATION_LAYOUT.md).

For an offline placement check from the repository root:

```sh
python3 experimental/attiny88/compact/host/compact_programmer27.py examples/attiny88-hid-keyboard/build/keyboard.hex
```

This command is a dry run. This example does not add an automatic uploader.
The hardware programmer's existing execution/recovery requirements still apply.
The stock Micronucleus CLI does not speak the installed compact protocol 3.0;
do not use it for this board in its current configuration.

Programming replaces the previous application. The generated HEX stays below
`0x1AFC` (a conservative limit also fitting the previous loader) and contains
no fuse, lock-bit, EEPROM, or bootloader data. Application code does not execute
SPM. Actual preservation during programming depends on the existing uploader.

During startup, the application briefly disconnects for 250 ms to change from
the loader's USB identity to the keyboard identity. Windows should use its
built-in HID keyboard driver for `16c0:27db`; keep the existing libusb driver
associated with the bootloader's separate identity.

## Verification and hardware status

Run offline checks with a native C compiler available as `cc` (or `--cc PATH`):

```sh
python3 verify.py
```

These checks build the actual AVR application, inspect its device/configuration
and HID report bytes, verify RESET/INT0 targets and all three compact 3.0
placements, check unchanged vendor hashes, and execute the portable C report
logic in four scenarios: full sequence, endpoint backpressure, HID idle timing,
and USB reset during typing. Boot and report protocols use the same eight-byte
format; GET/SET_IDLE, GET/SET_PROTOCOL, GET_REPORT, and the one-byte keyboard LED
SET_REPORT are implemented.

Validated offline on 2026-10-27 using AVR-GCC 7.3.0: **2488 Flash bytes,
85 static SRAM bytes**. All checks passed. The application was subsequently
uploaded and verified on the connected board: Windows enumerated the HID
keyboard and the user confirmed text input. See [the hardware test record](HARDWARE_TEST.md)
for the exact scope and limitations. The inherited V-USB 16 MHz backend
does not validate incoming DATA CRC16; this demonstration does not implement
USB suspend power management or remote wakeup.

For a hardware smoke test, record these observations separately:

1. The board changes from the compact loader to `Tiny88 Keyboard`.
2. The focused editor receives `hello` once, including both `l` characters.
3. The LED turns on; waiting another ten seconds produces no further typing.
4. Power-cycling starts the same demonstration again after the loader exits.
5. Reconnecting while the compact programmer waits still permits loading another application.

V-USB is vendored independently of the reduced bootloader driver. Its pinned
source and license are documented in [usbdrv/UPSTREAM.md](usbdrv/UPSTREAM.md).
The upstream [HIDKeys example](https://www.obdev.at/products/vusb/hidkeys.html)
documents this use of V-USB as a keyboard.
