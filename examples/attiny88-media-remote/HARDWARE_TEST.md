# Media remote hardware test, 2026-10-27

The user requested testing the three Consumer Control commands before wiring
physical buttons. The separate automatic-test application was uploaded to the
connected MH-Tiny88 through its recognized compact 3.0 no-LED loader (`0x0300`,
`BOOT_AT=0x1B80`).

## Programming and interruption recovery

The tested `remote-test.hex` used 4034 Flash bytes and 127 static SRAM bytes;
its SHA-256 was
`31dc0e1d9f9b88a1272407e65fec97f32c075099a3268e9ea460918031f81a2c`.
Two complete Flash and EEPROM reads matched before writing. Complete private
backups remain outside Git.

The user reported pressing Reset twice during the upload, which ended with a
USB transfer error. A read-only audit then independently established that the
loader and RESET redirect were unchanged, EEPROM was unchanged, 109 of 110
application pages matched the exact prepared image, and the final postscript
page was erased. No blind full-image retry was performed.

A fresh audit confirmed those conditions before writing only that final page.
All application bytes were then read back and matched; the complete loader and
EEPROM still matched the original backup. The application was started by RUN.

## Consumer input and host feedback

Windows enumerated the Consumer Control and vendor HID collections. The Python
controller successfully selected the vendor collection, read the three default
mappings, and sent mute feedback through Output report 2. No special HID driver
was installed.

Read-only Windows Core Audio monitoring recorded these changes, relative to
the controller's connection:

| Approximate time | Command | Observed Windows audio change |
| ---: | --- | --- |
| 4.94 s | Mute | Unmuted to muted, volume unchanged |
| 6.95 s | Volume up | Muted to unmuted, volume increased by about two percentage points |
| 8.97 s | Volume down | Volume decreased by about two percentage points |

The controller never changed Windows audio directly. These state changes align
with the one-pass firmware simulation at five, seven and nine seconds after USB
configuration. The user also confirmed that the commands worked. The input
sequence had already been checked offline for the three usages and their
following release reports.

Mute feedback writes completed without error. The user did not notice the
physical LED during the short muted interval, so visible LED operation is
**not confirmed** by this test. The monitoring helper was stopped after the
16-second observation; the LED subsequently represents an unknown state (off)
until a helper sends fresh feedback.

## EEPROM configuration

The Windows controller sent a persistent mapping feature report for Mute,
Volume up and Volume down. The firmware completed its asynchronous EEPROM save,
read back its record bytes, and returned the same mapping with no busy/error
flags. A separate controller process read back those mappings again.

This deliberately reserves EEPROM `0x00..0x1F` for this application's settings;
the original complete EEPROM backup remains private. Cold-power persistence
was not separately tested. Offline tests cover interrupted writes at every
record byte boundary, CRC fallback, generation wrap and preserving the upper
32 EEPROM bytes.

## Remaining physical checks

Physical GPIO buttons, visible LED state, cold-power mapping persistence and
interaction with the Tkinter GUI remain unverified. The controller's HID and
Core Audio paths were exercised through its console modes.

The board was left running `remote-test.hex`, which repeats its automatic test
after each MCU reset. For normal button-only operation, upload `remote.hex`.
