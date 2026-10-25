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

## Optional follow-up

LED-enabled images still reserve 21 pages. At `0x1B00`, the single-bit-mask
profiles would need a further eight bytes saved active high or six active low;
default-mask profiles would need twelve or ten bytes respectively. No further
safe reductions are confirmed. Keep full memory functionality and the USB
machine-code/timing audits for any further experiments.

An audible application check was offered and deferred by the user. Byte-exact
application preservation and the start command are verified; audible behavior
is not claimed as observed.
