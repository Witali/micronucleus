# 20-page ATtiny88 hardware validation — October 25, 2026

Result: **PASS** for USB installation, memory operations, watchdog/cold startup
and preservation of the original application and EEPROM. The 1274-byte no-LED
build replaced the previous 1344-byte loader over USB; ISP was not used.

| Property | Observed value |
| --- | --- |
| Target | ATtiny88, `16D0:0753`, bcdDevice `0x0208`, feature byte `0xE0` |
| Physical page | 64 bytes |
| Loader start / code / reservation | `0x1B00` / 1274 / 1280 bytes |
| Application capacity | 6908 bytes, previously 6844 |
| Built payload SHA-256 | `be2035139b301739837b5a214773e0a0421404450b078d40e2bf0c02aafa77c4` |
| Tested updater end / embedded bytes | `0x07D0` / 1280 |
| RESET after installation | `0xCD7F`, formerly `0xCD5F` |

The updater checks the image and programmed pages by readback before final
RESET handover. The USB Flash-read extension intentionally excludes loader
and postscript bytes; its dump alone is not a direct loader-body hash check.

## Application preservation

Three pre-update dumps were identical, and all EEPROM matched the existing
backup. The installed application differed from the older LED example.
A local MicroMusic Lumiere Stereo image matched every readable application
byte except the loader-patched RESET, including erased padding. Its original
RESET `0xC093` identifies entry `0x0128`; that exact 4652-byte image was saved
beside the device backup and selected for restoration.

After tests, Flash readback matched the original application HEX. A full
before/after dump comparison found exactly one difference within the original
6844-byte region: byte zero changed from `0x5F` to `0x7F`, redirecting RESET
to the new loader. All other original bytes and all 64 EEPROM bytes matched.
The additional 64 application bytes are `0xFF`. Three post-cold-start dumps
were identical. The application start command succeeded. The user deferred
an audible check, so audible output is not claimed as observed.

## Physical checks

- New USB information and 6908-byte capacity appeared after the updater's
  watchdog reset, with unchanged EEPROM.
- Flash boundary protection and SRAM GET_CONFIGURATION response passed.
- All 6908 application bytes passed pattern write/read and erase/read.
- All 64 EEPROM bytes passed write/read, erase-to-FF/read, and exact restore.
- The original application was restored and verified, and EEPROM remained
  unchanged after all Flash operations.
- The user then removed USB power for 2–3 seconds and reconnected. USB,
  configuration, protected bounds, EEPROM and application readback passed.

The retained [memory-cycle result](../../updater/evidence/memory-cycle-1274.json)
and [preservation comparison](../../updater/evidence/preservation-1274.json)
contain no raw user memory. Backups and the source-matched restore image
remain local under `C:/Work/MicroNucleus/validation/board-before-1274` and
`board-after-1274`; they are not published.

## USB read throughput

Synchronous libusb0/PyUSB on this Windows host, eight bytes per vendor request:

| Application bytes | Requests | Three measured times, seconds |
| ---: | ---: | --- |
| 6844, before update | 856 | 2.567880, 2.567832, 2.567809 |
| 6908, after update | 864 | 2.591876, 2.591818, 2.591837 |

This is approximately 2665 bytes/s, or 3 ms per request. At that measured
rate, 8192 bytes would take approximately 3.07 s; this is an extrapolation,
because the normal extension protects loader/postscript memory. The request
timings include host/driver overhead and are not a raw USB bit-rate measure.

No fuses were changed. The updater's existing first-RESET-page power-loss
limitation remains. LED-enabled variants have model validation only.
