# Verified ATtiny88 updater adaptation

This application adapts the in-place flow from upstream [`firmware/upgrade.c`](../../../firmware/upgrade.c). Upstream also supplies `firmware/upgrades/upgrade-t88_default.hex`; that image installs the stock loader, whereas this builder defaults to the pinned **packet-corrected strict USB 1344-byte** Micronucleus+ image at **0x1AC0**. A firmware manifest selects a configured image, including the optional LED variants below. The historical 1328-byte image failed the first reversible trial's extension requests and is not the update target.

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
python3 build_verified.py
python3 build.py
node test_usb_packets.mjs
node test_micromusic.mjs
python3 test_simavr.py /path/to/simavr-source
```

Build dependencies: AVR-GCC, avr-libc, AVR binutils and Python 3. Simulation also requires Node, GCC, libelf and a built current simavr library. `test_micromusic.mjs` imports `C:/Work/MicroMusic` read-only by default; set `MICROMUSIC_ROOT` elsewhere as needed.

Optional bootloader LED macros, build commands, output formats and capacity
changes are documented in the [verified variant configuration](../variants/strict_usb_verified/README.md#optional-bootloader-led).
`build_verified.py` also requires Clang and LLVM binutils as described by the
parent experiment. Its default continues to reproduce the pinned no-LED image.

MicroMusic's ATtiny88 CPU currently rejects SPM. The test harness explicitly adds a local 64-byte Flash-controller shim and missing CBI/SBIC/SBIS execution. All remaining updater instructions use the original CPU. The sibling project is unchanged. The simavr test independently uses its CPU and native SPM engine, constraining the ATmega88 substrate to tiny88 RAM, EEPROM and 64-byte NORWW pages; it supplies the missing CTPB command. Neither is presented as a complete native ATtiny88 peripheral model.

Checks pass for the exact resulting image, intact updater memory, late RESET commit, disabled SELFPRGEN, corrupt payload and failed target readback. The MicroMusic test additionally restarts at five operation boundaries. Flash-operation duration is an explicit model parameter, not an electrical timing guarantee. Device behavior was checked against [Microchip ATtiny48/88 datasheet, chapter 19](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf).

## Reversible USB rehearsal and local backup

```sh
python3 build_rehearsal.py
```

This produces `build/rehearsal.hex`, an ordinary application that runs the corrected strict USB engine at `0x1000`, ending at `0x1546` and leaving the old loader at `0x1A00` untouched. Only the diagnostic Flash-read bound is expanded to 8192 bytes. Its low-level USB engine is unchanged. Do not send Flash/EEPROM write commands to the rehearsal.

After uploading the rehearsal as an application, `usb_backup.py` uses only vendor IN requests for information, Flash reads and EEPROM reads. It requires two identical reads of each memory, checks the old RESET, and saves a local dump, hashes, and an ISP recovery HEX for the stock 2.2 loader. Pass `--dll`, `--python-libs` if needed, and a new local `--backup` directory. Device backups stay outside the public repository.

The final application updater is `build/updater.hex`, intended for the working stock uploader. `upload_stock.py` first requires the original 2.2 descriptor and 6650-byte capacity, so an application cannot accidentally be uploaded through the running diagnostic variant. It is distinct from the fresh-device ISP image. Build and checks do not themselves flash a board. Hardware results, when available, belong in a separate record.

The tested ready-to-upload application image is retained in `releases/upgrade-t88-verified.hex`; its checksum and target are recorded in `releases/SHA256SUMS.txt`. Use it only with the verified ATtiny88 target and working Micronucleus, not as an arbitrary application for another AVR.

## USB updater for a configured LED image

Build a selected loader, then pass its manifest to the application updater:

```sh
python3 build_verified.py --led on
python3 build.py --firmware-manifest build/led-on/firmware.json \
    --output-dir build/updater-led-on
node test_micromusic.mjs build/updater-led-on
python3 test_simavr.py /path/to/simavr-source --build-dir build/updater-led-on

python3 build_verified.py --led active-low
python3 build.py --firmware-manifest build/led-active-low/firmware.json \
    --output-dir build/updater-led-low
node test_micromusic.mjs build/updater-led-low
python3 test_simavr.py /path/to/simavr-source --build-dir build/updater-led-low
```

The same interface accepts a custom macro build. Without `--output-dir`, a
configured updater goes to the firmware manifest's directory under `updater/`;
it does not overwrite `build/updater.hex`. The builder validates the target,
body hash, page size, signature, capacity and page alignment before embedding
the selected image. It derives the destination, postscript and RESET from its
actual boot boundary. `bootloader-image.bin` in the updater directory contains
the exact padded payload used by both emulator checks.

The default `python3 build.py` remains byte-identical to the previously tested
release. The `ACTIVE_HIGH` and `ACTIVE_LOW` updaters end at `0x0856`, embed 1408
bytes at `0x1A80`, and report 6780 application bytes after installation. Both
pass byte-exact update and fuse/CRC/readback failure checks in MicroMusic and
simavr. MicroMusic also checks five restarts between completed operations.
These are software results; no LED-enabled loader has been installed on the
board as part of this change. The output `updater.hex` is the USB application
image; `isp-fresh.hex` from the loader builder serves a different purpose.

The later [strict USB optimization candidate](../variants/strict_usb_optimized/README.md)
has a separate `build_optimized.py` entry point. It retains packet/reset fixes
and permits exactly four audited cycle-neutral USB-engine substitutions.
It uses 1274 bytes without LED at `0x1B00`, reserves 20 pages and exposes
6908 application bytes. Default-mask PD0 LED modes use 1296/1294 bytes at
`0x1AC0`, with 6844 application bytes. Its manifests work with the same updater command
above. The candidate's documentation records exact sizes, focused changes,
cycle comparisons and independent erase/updater model checks. It has been
installed and memory-tested on the physical board in its no-LED configuration;
see the [20-page hardware record](../variants/strict_usb_optimized/HARDWARE_TEST.md).
LED modes retain model validation; default builds and release files stay pinned.

## Hardware memory test and user actions

`test_hardware_memory.py --help` describes an explicit opt-in physical test. It reuses the existing host library: write/read all 64 EEPROM bytes, erase to `0xFF`, restore the backup, write/read/erase the entire application reservation, then restore and start the selected original application. `--firmware-manifest` selects its actual capacity and RESET (6908 bytes for the 20-page image); omission retains the earlier 6844-byte layout. `--restore-hex` selects the original application; `--led-hex` remains an alias. EEPROM has no separate USB erase opcode. The test requires `--exercise-hardware`, backups and an external report destination, and never runs in ordinary discovery.

`check_installed.py` accepts the same firmware manifest. `--benchmark-reads N`
times read-only eight-byte Flash requests; `--readback-dir` saves identical
repeated Flash reads, EEPROM and a manifest in a new local directory and
requires at least two reads. These dumps exclude protected loader/postscript
bytes. Preserve an exact source image with its original RESET before an
updater or memory test replaces an unknown application. The measured 6908-byte
read takes approximately 2.592 seconds on the tested Windows/libusb0 host.

Instructions to a person must distinguish **press the RESET button** from **remove all board power**. Use the button for a normal loader window after the final fixes. Request a full power cycle explicitly for a cold-start check or for clearing an old latched reset condition. If requesting a power cycle, specify removal of USB/other power for 2–3 seconds. During actual bootloader programming, neither reset nor remove power. Otherwise leave the board connected until a specific action is requested.

The first permanent trial revealed that the imported loader attempted watchdog disable while WDRF was still set. Full removal of power allowed the installed loader to start. Moving the existing MCUSR save/clear before watchdog disable fixed this without increasing size; the final image returned by USB after the updater's watchdog reset, without physical intervention. Tests now cover POR/EXTR/BOR/WDR/mixed flags and complete SETUP-to-TX payloads, including GET_CONFIGURATION.
