# Verified ATtiny88 updater adaptation

This application adapts the in-place flow from upstream [`firmware/upgrade.c`](../../../firmware/upgrade.c). Upstream also supplies `firmware/upgrades/upgrade-t88_default.hex`; that image installs the stock loader, whereas this builder embeds the pinned **Strict USB 1328-byte** Micronucleus+ image at **0x1AC0**.

The updater and its image execute from application Flash starting at `0x0080` and end at `0x0816` in the recorded AVR-GCC build, below the old loader at `0x1A00`, the new postscript page, and the destination image. The total ELF text is 1942 bytes. The embedded image is padded to 1344 bytes (21 pages).

## Sequence

1. Disable interrupts/watchdog, wait for EEPROM, and disconnect USB on PD1. Only the PD0 LED and USB pins are touched.
2. Require the ATtiny88 extended SELFPRGEN fuse to be programmed. Check CRC-16/CCITT of the embedded image before any Flash write.
3. Replace RESET with an entry into the intact updater at `0x0080` and verify the first page.
4. Clear the temporary page buffer, erase, fill and write each 64-byte target page. Keep Z page-aligned for PGWRT and compare every written word through LPM.
5. Erase/verify the new postscript page so the new loader waits for a first application.
6. Commit RESET to the new loader only after all image pages pass verification. Perform a watchdog reset after success.

No fuse or EEPROM writes are implemented. A readback error keeps the temporary updater entry instead of committing the new loader. Resetting between completed operations can restart the intact updater; a power failure during either first-page erase/write can still destroy RESET. There is no guaranteed recovery without ISP for that window. Emulator results do not prove analog power-failure or electrical USB behavior.

## Build and model checks

```sh
python3 build.py
node test_micromusic.mjs
python3 test_simavr.py /path/to/simavr-source
```

Build dependencies: AVR-GCC, avr-libc, AVR binutils and Python 3. Simulation also requires Node, GCC, libelf and a built current simavr library. `test_micromusic.mjs` imports `C:/Work/MicroMusic` read-only by default; set `MICROMUSIC_ROOT` elsewhere as needed.

MicroMusic's ATtiny88 CPU currently rejects SPM. The test harness explicitly adds a local 64-byte Flash-controller shim and missing CBI/SBIC/SBIS execution. All remaining updater instructions use the original CPU. The sibling project is unchanged. The simavr test independently uses its CPU and native SPM engine, constraining the ATmega88 substrate to tiny88 RAM, EEPROM and 64-byte NORWW pages; it supplies the missing CTPB command. Neither is presented as a complete native ATtiny88 peripheral model.

Checks pass for the exact resulting image, intact updater memory, late RESET commit, disabled SELFPRGEN, corrupt payload and failed target readback. The MicroMusic test additionally restarts at five operation boundaries. Flash-operation duration is an explicit model parameter, not an electrical timing guarantee. Device behavior was checked against [Microchip ATtiny48/88 datasheet, chapter 19](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf).

## Reversible USB rehearsal and local backup

```sh
python3 build_rehearsal.py
```

This produces `build/rehearsal.hex`, an ordinary application that runs the strict USB engine at `0x1000`, ending at `0x1536` and leaving the old loader at `0x1A00` untouched. Only the diagnostic Flash-read bound is expanded to 8192 bytes. Its low-level USB engine is unchanged. Do not send Flash/EEPROM write commands to the rehearsal.

After uploading the rehearsal as an application, `usb_backup.py` uses only vendor IN requests for information, Flash reads and EEPROM reads. It requires two identical reads of each memory, checks the old RESET, and saves a local dump, hashes, and an ISP recovery HEX for the stock 2.2 loader. Pass `--dll`, `--python-libs` if needed, and a new local `--backup` directory. Device backups stay outside the public repository.

The final application updater is `build/updater.hex`, intended for the working stock uploader. It is distinct from the fresh-device ISP image. Build and checks do not themselves flash a board. Hardware results, when available, belong in a separate record.
