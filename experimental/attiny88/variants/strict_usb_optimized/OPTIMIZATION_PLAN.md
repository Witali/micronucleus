# ATtiny88 optimization plan

## Completed target: no-LED loader within 20 pages

- [x] Preserve USB packet CRC, Flash programming/readback, EEPROM, watchdog
  startup and RESET protection.
- [x] Audit dispatch, empty replies, unsigned Flash bounds and startup pointer
  reuse as separate focused changes.
- [x] Merge response copying with the original inverted CRC recurrence;
  validate packed counters/carry and independent checksums.
- [x] Fit 1274 code bytes at `0x1B00`, reserve 1280 bytes and expose 6908
  application bytes, gaining one 64-byte page.
- [x] Support the new layout in updater, restart tests, host and opt-in
  hardware verification tools.
- [x] Pass CPU/NVM models, exhaustive Flash-read bounds and USB timing checks.
- [x] Install on the connected board over USB, validate watchdog/cold startup
  and physical Flash/EEPROM write/read/erase.
- [x] Back up and restore the actual 4652-byte application and all EEPROM.
  Before/after dumps differ only in the expected loader RESET byte; the
  additional 64 application bytes are erased.
- [x] Measure USB application readback: 6908 bytes in approximately 2.592 s.

## Completed follow-up: all tested LED profiles within 20 pages

- [x] Publish remaining reply length once, using the short-packet borrow;
  preserve the remainder through CRC (six bytes saved).
- [x] Check the Flash page offset in disposable ZL and use the shared empty
  reply tail (two bytes saved).
- [x] Reuse context pointer YH for the SPM buffer-load command, protected by
  a compile-time assertion and model checks (two bytes saved).
- [x] Use SBIC to select EEPROM ready/busy status, following Microchip EEPE
  semantics; check all EECR values and completion after sampling (two bytes saved).
- [x] Fit default PD0 active-high/low images at `0x1B00`, saving another four
  bytes in their Flash bounds. Current code sizes: off 1262, high 1280, low 1278.
- [x] Validate seven LED/port/mask profiles with actual opcode, CRC and USB
  audit/packet tests; repeat exhaustive bounds, timing and native erase checks
  for all three board modes.
- [x] Validate all three 1280-byte updater payloads in MicroMusic and simavr,
  including failure and interrupted-operation cases.

All seven tested profiles reserve 1280 bytes and expose 6908 application
bytes. These latest images have software/model validation only; the connected
board retains the earlier, physically verified 1274-byte no-LED image.
Installing the latest image and repeating physical memory/preservation tests
remain a separate hardware step.

## Optional further reduction

No further safe reductions are confirmed. Keep full memory functionality and
the USB machine-code/timing audits for any further experiments. A 19-page
reservation would allow only 1216 bytes, requiring another substantial reduction.

An audible application check was offered and deferred by the user. Byte-exact
application preservation and the start command are verified; audible behavior
is not claimed as observed.
