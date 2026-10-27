# Protocol 3.0 application-only hardware test, 2026-10-27

Historical trial: the board was later updated permanently as recorded in
[HARDWARE_INSTALL30.md](HARDWARE_INSTALL30.md). The original trial scope below
is preserved.

Result: PASS on the connected ATtiny88 board at 16 MHz, using its existing
libusb-win32 driver. The installed Micronucleus+ 2.8 loader remains at 0x1B00,
with 6908 application bytes. No ISP programmer was connected.

The user explicitly confirmed application programming and USB power cycling.
Application Flash and all 64 EEPROM bytes were read twice before writing.
The original application HEX matched that backup and was retained privately.
Device dumps and restore images are excluded from the repository.

`build_rehearsal30.py --installed-capacity 6908` builds a 1142-byte read-only
trial at 0x1000, ending at 0x1476. Its USB device revision is 0x0390; its wire
protocol is 3.0. A 14-byte entry at 0x0080 initializes SP, clears R1 and disables
interrupts. The application HEX has no records near the installed loader or
its postscript. The existing loader uploaded and started it successfully.

Before upload, emitted-opcode tests rejected writes for every private request
byte; only SELECT and READ8 remain available. The PHY bytes match production.
The production images retain the normal write protocol and use revisions
0x0300/0x0301/0x0302 for off/high/low LED builds.

Hardware checks passed:

- 60 repeated device/configuration descriptor requests, GET_STATUS and GET_CONFIGURATION.
- Two identical reads of all 8192 Flash bytes and two of all 64 EEPROM bytes.
- Exact application body/entry readback, unchanged EEPROM and installed RESET.
- Installed boot bytes equal the archived 1274-byte loader image.
- After a physical USB power cycle, loader 2.8 responded, then the trial started
  automatically; its body and EEPROM still matched.

`firmware27/Pass30_rehearsal_app.hex` is the tested application artifact.
`hardware/read_rehearsal30.py` repeats the read-only checks with explicit
`--private-dir`, `--python-libs` and `--dll` arguments. The private directory must
contain the original `before/eeprom.bin` and `before/manifest.json` backup.

This validates the read-only application rehearsal. It does not validate
production Flash/EEPROM writes, permanent bootloader replacement, bad-CRC/lost-ACK
recovery, reset-flag forwarding through the old loader, or physical bit timing.
Known protocol limitations remain in USB_PROTOCOL.md. No fuse/lock writes occurred.
