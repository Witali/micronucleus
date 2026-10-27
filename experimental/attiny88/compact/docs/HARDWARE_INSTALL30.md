# Permanent compact 3.0 installation, 2026-10-27

PASS on the connected ATtiny88 board with the existing external 16 MHz clock
and Windows libusb0 driver. The no-LED compact loader now resides permanently
at `0x1B80`, reports USB revision `0x0300`, and implements protocol 3.0.
Its code is 1148 bytes in an 1152-byte reservation, leaving 7036 application
bytes. RESET is `0xCDBF`; the new postscript page `0x1B40..0x1B7F` is erased.
The loader remains active while no application postscript is present.

The user explicitly approved replacing the old 2.8 loader and accepted the
RESET-page power-loss risk without ISP. A fresh complete Flash backup was read
twice, EEPROM matched the original private backup, and the installed old
1274-byte body matched its independently checked image before programming.
Private memory dumps, recovery HEX and uploader logs remain outside Git.

## Updater and pre-install checks

The existing [ATtiny88 self-updater](../../updater/README.md#compact-protocol-30)
was reused without changing `updater.c`. Its application starts at `0x0080`
and ends at `0x0756`. It verifies SELFPRGEN and embedded-image CRC-16/CCITT,
installs a temporary RESET into itself, verifies every replaced page, clears
the new postscript and commits RESET into the new loader last.

The selected payload contains 1148 code bytes, padded to 1152 bytes; its CRC is
`0x74B5`. The ready application and its hashes are preserved under
`updater/releases/upgrade-t88-compact30-off.hex` and `compact30-off.json`.

Both simavr and the MicroMusic CPU model passed with the exact old-loader
bytes and native application RESET/postscript patching in the initial Flash.
Checks cover the exact destination image, all other protected bytes, disabled
SELFPRGEN, corrupt embedded CRC, failed page readback and five operation-boundary
restarts in MicroMusic. The older default updater remains byte-identical.

## Hardware checks

- The stock uploader detected the original 2.8 identity and 6908-byte capacity,
  uploaded the checked application and started the self-updater successfully.
- The board re-enumerated as permanent `0x0300` after the updater's watchdog
  reset, without physical intervention.
- Two identical reads of all 8192 Flash bytes matched every new loader byte and
  all padding; RESET and the erased postscript page were checked separately.
- The updater application remained intact and all 64 original EEPROM bytes
  were unchanged. Repeated standard descriptors, GET_STATUS and GET_CONFIGURATION
  succeeded.
- The user removed all power for 2-3 seconds. USB disappearance was observed;
  after reconnection the permanent loader started again, and full Flash and
  EEPROM still matched their verified copies.
- The installed loader erased and wrote one initially free 64-byte page at
  `0x0800`, using the selected 7 ms host delay. Readback matched the controlled
  payload. The page was erased again; a complete Flash comparison confirmed
  restoration and EEPROM remained unchanged.

Timing-only/boolean evidence is in [hardware30.json](../firmware27/hardware30.json).
The [earlier full-memory benchmark](MEMORY_BENCHMARK30.md) used a guarded
application image and remains a separate test scope.

## Remaining scope

This is a successful installation and basic hardware smoke test of the
no-LED profile. LED profiles have not been installed. Incoming DATA CRC16 is
still omitted by the accepted decision; token admission and ACK-driven retry
remain open. These checks do not establish USB electrical compliance,
worst-case completion timing, or power-failure recovery.

The updater application remains in application Flash. No ordinary user
application has been installed after it. Moving the loader upward also leaves
old bytes at `0x1B00..0x1B3F` and the previous postscript at `0x1AFC`; they are
ordinary stale application data and provide no old-loader fallback. A complete
normal application upload erases them. No fuse, lock or EEPROM writes were
performed during the permanent update or smoke test.
