# Experimental Micronucleus+ for ATtiny88

This directory contains the assembly development line imported from the October 25, 2026 handoff. Upstream C firmware and the original command-line tool remain in their existing directories. The imported code targets ATtiny88 / MH-Tiny88 at 16 MHz and has not been validated on physical USB hardware.

| Variant | Code bytes | Boot address | Application bytes | Flash read |
| --- | ---: | --- | ---: | --- |
| Fast Pass7, selected development line | 1320 | `0x1AC0` | 6844 | 1–8 bytes/request |
| Strict USB Pass7, initial hardware trial candidate | 1328 | `0x1AC0` | 6844 | 1–8 bytes/request |
| Historical compact Pass4 | 1344 | `0x1AC0` | 6844 | 1 byte/request |
| Rejected range-CRC Pass6 experiment | 1554 | `0x19C0` | 6588 | 1–8 bytes/request |

Fast and strict Pass7 support standard Micronucleus Flash writes, application Flash reads, and read/write access to all 64 EEPROM bytes. USB packet CRC remains enabled. The selected line excludes the memory-range CRC experiment; verify readback on the host instead.

## Build and check

Requirements: Python **3.10+**, Clang with the AVR backend, `llvm-objcopy`, `llvm-objdump`, and GNU `avr-ld`. In Ubuntu/WSL these tools are supplied by `clang`, `llvm`, and `binutils-avr`. No external Python packages are needed for offline builds or tests.

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

## Files and protocol

- `source/micronucleus_t88_plus.S`: selected Fast Pass7 source.
- `firmware/`: archived fast body, fresh-device ISP HEX, and complete Flash image.
- `variants/strict_usb_1328/`: conservative source and images; its original 516-byte USB handler and 44-byte CRC routine are unchanged.
- `variants/compact_pass4/` and `variants/range_crc_pass6/`: historical alternatives, excluded from the selected build.
- `host/micronucleus_plus.py`: Flash/EEPROM host utility. Physical use requires PyUSB and a compatible libusb backend; Flash writes delegate to the stock Micronucleus CLI.
- `reference/`, `tests/`, and `tools/`: comparison binaries, AVR model, timing checks, and provenance verification.

See [PROTOCOL.md](PROTOCOL.md) for memory layout and requests. `python3 host/micronucleus_plus.py --help` works without USB libraries or an attached board. The memory extensions require Micronucleus+ feature flags and are unavailable on an unchanged stock 2.2 bootloader.

## Installation status

These images are experimental ISP installation artifacts. A fresh-device ISP image includes RESET and is not an application image to upload through an existing USB bootloader. No physical board was flashed during import. Software trace comparisons do not establish electrical USB compatibility, power-loss recovery, or reliability at 16 MHz on a particular device.

An ATtiny88 self-updater has **not** been implemented. Its preserved [design plan](../../docs/attiny88-history/SELF_UPDATER_PLAN.md) is a future task, not a supported installation method. Initial hardware testing needs a working ISP recovery path and backups of the original device state.

## History and license

Each historical stage and alternative is retained in a separate import commit. See the [history index](../../docs/attiny88-history/README.md), [development timeline](../../docs/attiny88-history/DEVELOPMENT_HISTORY.md), and [validation record](../../docs/attiny88-history/VALIDATION.md).

The original handoff ZIP is preserved byte for byte under `docs/attiny88-history/`. Its archived original-language documents are historical records; current project documentation is maintained in English. Derived firmware retains the original Micronucleus GPL-2.0-or-later licensing; see `reference/LICENSE_GPL-2.0.txt` and the repository license.
