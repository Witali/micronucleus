# Pass27 software-verified firmware candidate

Target: ATtiny88 with the existing external 16 MHz clock and board wiring.
The no-LED body is permanently installed through the application self-updater;
see [hardware evidence](../docs/HARDWARE_INSTALL30.md). LED profiles have not been
installed. The fresh ISP images were not used. This checkpoint does not fit 1 KiB.

| File prefix | LED | BOOT_AT | Body bytes | Application bytes |
| --- | --- | --- | ---: | ---: |
| `Pass27_off` | None | `0x1B80` | 1148 | 7036 |
| `Pass27_high` | Active high | `0x1B40` | 1166 | 6972 |
| `Pass27_low` | Active low | `0x1B40` | 1164 | 6972 |

`*_body.bin` contains only the bootloader at its listed placement.
`*_ISP_FRESH_8192.bin` is a complete fresh-chip Flash image with RESET redirect;
the application and postscript are erased. `*_ISP_FRESH_EXPERIMENTAL.hex`
contains the RESET redirect and bootloader region. Neither changes fuses or
EEPROM. These are ISP preparation artifacts, not application upload images.
Preserve the board's existing verified fuse settings and ISP recovery access.

Use `host/compact_programmer27.py` for the matching v3.0 application protocol;
the Pass26 client/profile is different. Its execution and ISP-recovery gates
remain required. The builder itself never accesses programming hardware.

The full software suite passed at code checkpoint `ce74532`: standard/NVM/host
regressions, 186 synchronized scenarios, 125943 polling intervals and 12654 TX
waveform cases. Digital timing checks exclude analog behavior and Flash-program
CPU halts. Incoming DATA CRC16 omission is an accepted exception; token admission,
ACK-driven retry and reset/error behavior still have known protocol gaps.
See `docs/USB_PROTOCOL.md` and `docs/USB_TIMING.md` in the source tree.

Rebuild from the compact directory at the frozen e405ea7 checkpoint with
`python3 build_firmware27.py`, using
Clang/LLVM 18.1.3 and AVR binutils 2.26.20160125. The builder checks physical fit,
profile/descriptor identity, undefined operands, emitted PHY contracts, RESET
destination, and an independently parsed HEX round trip. `SHA256SUMS.txt`
covers every other file in this directory.

These images additionally include the two-byte EEPROM-tail reuse. Its affected
EEPROM/USB paths pass in every LED profile; see docs/PASS27_EEPROM_TAIL.log.
Exact current source hashes are recorded in manifest.json.

`Pass30_rehearsal_app.hex` is the tested, write-disabled application at 0x1000
(USB device revision 0x0390, protocol 3.0). It preserves the installed 2.8 loader
at 0x1B00 and requires its 6908-byte application layout; it is not a permanent
bootloader installer. The entry wrapper initializes SP and disables interrupts.

`hardware30.json` records the no-LED permanent installation and basic checks.
It does not certify the protocol or the untested LED profiles. The top-level
manifest's `hardware_validated: false` retains that broader admission limit;
`hardware_tested_profiles` records the specific tested image.
