# Experimental Micronucleus+ for ATtiny88

This directory contains the assembly development line imported from the October 25, 2026 handoff. Upstream C firmware and the original command-line tool remain in their existing directories. The original imported images are historical experiments. A subsequent real-board trial uncovered vendor-dispatch, SRAM-reply and watchdog-startup defects; the [corrected strict USB version](variants/strict_usb_verified/README.md) and [USB updater](updater/README.md) address them without changing the low-level USB handler.

| Variant | Code bytes | Boot address | Application bytes | Flash read |
| --- | ---: | --- | ---: | --- |
| Earlier packet/reset-corrected strict USB, pinned hardware target | 1344 | `0x1AC0` | 6844 | 1–8 bytes/request |
| Optimized 20-page loader, LED off, hardware validated | 1274 | `0x1B00` | 6908 | 1–8 bytes/request |
| Historical Fast Pass7, uncorrected | 1320 | `0x1AC0` | 6844 | Declared 1–8 bytes/request |
| Historical strict Pass7, uncorrected | 1328 | `0x1AC0` | 6844 | Declared 1–8 bytes/request |
| Historical compact Pass4 | 1344 | `0x1AC0` | 6844 | 1 byte/request |
| Rejected range-CRC Pass6 experiment | 1554 | `0x19C0` | 6588 | 1–8 bytes/request |

The corrected strict build supports standard Micronucleus Flash writes, application Flash reads, and read/write access to all 64 EEPROM bytes. The historical images declared these extensions but need the packet-level corrections described above. USB packet CRC remains enabled. The current target excludes the memory-range CRC experiment; verify readback on the host instead.

The separate [strict USB optimization candidate](variants/strict_usb_optimized/README.md)
retains the corrected behavior and USB timing, with four audited substitutions
shrinking the engine from 516 to 508 bytes. Single-pass reply copying/CRC now
uses 1274 code bytes without LED, freeing a page and exposing 6908 application
bytes at `0x1B00`. Default-mask PD0 LED modes use 1296/1294 bytes and reserve
21 pages at `0x1AC0`. The no-LED image passed a later
[USB upgrade and hardware memory/preservation check](variants/strict_usb_optimized/HARDWARE_TEST.md).
Default verified/release artifacts remain pinned to the earlier 1344-byte build.

## Build and check

For the current hardware target, use `python3 updater/build_verified.py` and `python3 updater/build.py`, followed by the checks documented in the updater directory. The commands below reproduce the original historical Pass7, not the corrected target. Its original handler-only tests did not cover complete USB request routing or watchdog-reset startup.

Requirements: Python **3.10+**, Clang with the AVR backend, `llvm-objcopy`, `llvm-objdump`, GNU `avr-ld`, AVR-GCC and AVR-libc headers. In Ubuntu/WSL these tools are supplied by `clang`, `llvm`, `binutils-avr`, `gcc-avr` and `avr-libc`. No external Python packages are needed for offline builds or tests.

From this directory:

```sh
python3 build.py
python3 build_strict.py
python3 -m unittest discover -s tests -q
python3 tests/test_vusb_timing.py
python3 tests/emulator_diff_test.py
python3 tools/scan_repeats.py
python3 tools/verify_history.py
```

`sh verify.sh` runs the original fast-build checks. The strict builder and history verifier are separate checks. LLVM 18 leaves branch relocations in AVR object files, so the imported build scripts now invoke `avr-ld` before extracting binary bytes. This reproduces the archived firmware without modifying assembly instructions.

Fast Pass7 body SHA-256: `6f573edc063f1e7751d551ac2ee3384ecfc92d807fa2db5e279e1d063327413d`.

Strict USB body SHA-256: `fab49bebffe9a03c0db4504313e2af6c67678dde2b2211bf6dfe6d98fd9c4d5a`.

## Assembly labels

The maintained [Fast Pass7 source](source/micronucleus_t88_plus.S) uses semantic
labels instead of the address-like names inherited from disassembly. Each
renamed block has a short English comment describing its role. Names distinguish
USB synchronization and NRZI receive paths (`usb_rx_*`), transmit/stuffing/EOP
paths (`usb_tx_*`), control replies (`usb_reply_*`), standard requests
(`usb_standard_*`), the bootloader poll/command loop (`bootloader_*`), and Flash
page-buffer operations (`flash_*`).

The [label map](source/label-map.csv) records all 94 former address labels and
three misleading named labels with their new names and purposes. For example,
`L1abe` is `usb_rx_wait_for_j`, `L1d6a` is
`flash_erase_application_page`, and `L1e3a` is `usb_tx_copy_flash_payload`.
The former `usb_program_page` becomes `flash_buffer_append_word`: it stages
one word with SPM; the separate `flash_commit_buffered_page` actually writes
the page. `legacy_led_off_anchor` and `legacy_led_on_anchor` intentionally
contain no instructions because those LED operations were removed in Pass7.

This naming change preserves every instruction and all 97 mapped symbol
addresses. The 1320-byte body and its SHA-256 above are unchanged. Tests and
the repeat scanner use the new names. `tests/source_labels.py` exposes semantic
aliases only in test-side dictionaries when reading old reference objects;
it does not add historical aliases to the maintained assembly. The archived
sources and original handoff remain intact. The corrected strict hardware
target in `variants/strict_usb_verified/` is a separate source and is unchanged
by this readability update.

## Named constants and device definitions

The Fast Pass7 source includes `<avr/io.h>` through the C preprocessor. The
build selects the unmodified official Microchip `iotn88.h` from the pinned
[ATtiny_DFP 3.4.278 files](vendor/microchip/ATtiny_DFP-3.4.278/README.md).
Register and bit names such as `DDRD`, `PCIFR`, `WDTCSR`, `EEPE` and `EEMPE`
come from these device definitions. Standard AVR-libc I/O/CPU macros make
the header usable from `.S`; `_SFR_IO_ADDR()` is used for bit I/O and IN/OUT,
and `_SFR_MEM_ADDR()` is used for LDS/STS. No C functions or types are emitted.

Project constants appear at the start of the assembler file, grouped by
memory layout, SRAM-field offsets, USB IDs/requests/descriptors, SPM commands,
bootloader commands, EEPROM status, timing and CRC/NRZI encodings. Page size,
EEPROM size, SRAM start and signature bytes derive from the official header.
Descriptor bytes have field comments instead of opaque eight-byte chunks.
Simple arithmetic values such as zero, one and byte bit positions remain
literal where their meaning is immediate.

These names describe the existing fixed 16 MHz implementation. Timing seeds,
SRAM offsets and device/protocol values are not independent configuration
options: changing them requires a fresh audit. Build-time SHA-256 validation
pins the resulting 1320-byte body to the historical image; symbol addresses
and the instruction stream remain unchanged by this refactor.

```sh
python3 tools/import_microchip_device.py --check
```

## Files and protocol

- `source/micronucleus_t88_plus.S`: historical Fast Pass7 source.
- `firmware/`: archived fast body, fresh-device ISP HEX, and complete Flash image.
- `variants/strict_usb_1328/`: historical strict source and images; its original 516-byte USB handler and 44-byte CRC routine are unchanged, but packet/reset fixes are needed.
- `variants/strict_usb_verified/`: corrected 1344-byte target used in the successful USB upgrade and hardware memory tests.
- `variants/strict_usb_optimized/`: 20-page corrected loader with semantic labels/constants and unchanged strict USB timing; no-LED hardware validation and LED model checks.
- `variants/compact_pass4/` and `variants/range_crc_pass6/`: historical alternatives, excluded from the selected build.
- `host/micronucleus_plus.py`: Flash/EEPROM host utility. Physical use requires PyUSB and a compatible libusb backend; Flash writes delegate to the stock Micronucleus CLI.
- `reference/`, `tests/`, and `tools/`: comparison binaries, AVR model, timing checks, and provenance verification.

See [PROTOCOL.md](PROTOCOL.md) for memory layout and requests. `python3 host/micronucleus_plus.py --help` works without USB libraries or an attached board. The memory extensions require Micronucleus+ feature flags and are unavailable on an unchanged stock 2.2 bootloader.

## Installation status

These images are experimental ISP installation artifacts. A fresh-device ISP image includes RESET and is not an application image to upload through an existing USB bootloader. No physical board was flashed during import. Software trace comparisons do not establish electrical USB compatibility, power-loss recovery, or reliability at 16 MHz on a particular device.

The [ATtiny88 application updater](updater/README.md) now embeds the corrected strict image. It validates the payload and written pages before final RESET handover. Its [original design plan](../../docs/attiny88-history/SELF_UPDATER_PLAN.md) remains preserved for provenance. First-page power-loss recovery still requires ISP in the worst case; the local device backup is not published with the source.

## History and license

Each historical stage and alternative is retained in a separate import commit. See the [history index](../../docs/attiny88-history/README.md), [development timeline](../../docs/attiny88-history/DEVELOPMENT_HISTORY.md), and [validation record](../../docs/attiny88-history/VALIDATION.md).

The original handoff ZIP is preserved byte for byte under `docs/attiny88-history/`. Its archived original-language documents are historical records; current project documentation is maintained in English. Derived firmware retains the original Micronucleus GPL-2.0-or-later licensing; see `reference/LICENSE_GPL-2.0.txt` and the repository license.
