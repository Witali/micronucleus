# Guarded physical memory benchmark

This is an ordinary application for comparing the installed 1274-byte
Micronucleus+ 2.8 with streaming V2 and the Block64 memory workers. It keeps
the installed loader and its application postscript intact. The
[completed comparison](COMPARISON.md) includes exact restoration evidence.

## Build and software checks

Run from `experimental/attiny88/block64`, with the same LLVM AVR / GNU AVR
linker environment as the other experimental firmware:

```sh
python3 prototypes/memory_benchmark/tools/build.py
python3 -m pytest -q prototypes/memory_benchmark/tests prototypes/memory_benchmark/host/tests
python3 prototypes/memory_benchmark/tools/audit_legacy_cursor.py
```

The complete suite has 48 tests. Importing host modules and running their
fake-device tests never accesses USB. Physical use is opt-in and requires
private backups, expected images and explicit operator RESET sequencing;
see the [host contract](host/README.md) and [experiment plan](PLAN.md).

## Firmware contract

The builder reuses frozen streaming-V2 source
`fcc0ad6f463dd0e133808065e8db3d1aa2e4a1762158666dadfc2231205dbd2c`.
The default streaming diagnostic builder remains read-only.

- Origin is 0x0800; tables occupy 0x1600 and 0x1700; HEX data ends at
  0x1800, before the installed loader at 0x1B00.
- Flash WRITE and ERASE permit exactly eight aligned 64-byte pages at
  0x1800..0x19FF. The request validator and final SPM address builder
  independently enforce the range.
- EEPROM WRITE permits addresses 0..63. The original EEPROM is restored
  before legacy Flash preparation and after the new benchmark.
- READ can address all 8192 Flash bytes. Metadata is 0x1FFC/64/64 with
  benchmark features 0x83 and USB version 0x0303.
- RUN and inactivity application exit are disabled. An invalid internal
  NVM address stops before a programming trigger; RESET returns to the
  installed loader.

The final body is 4096 bytes: 3348 bytes of executable/static content,
512 CRC-table bytes and 236 bytes of alignment. It includes benchmark-only
protection and is not the final size/layout of an integrated loader.
Body SHA-256:
`1a4234414d966a91bf8bca82b7c93c16aa5c3d673cdebd498132b2a467eb21f3`.

The 28 firmware tests execute compiled guards and strict NVM workers,
including every aligned 16-bit Flash page address, scratch byte offsets,
EEPROM ranges and invalid internal trigger addresses. USB smoke passes
136 frames; a semantic instruction audit preserves the frozen PHY.
An additional eight tests rebuild the exact historical 1274-byte source
and prove legacy cursor preparation over 1729 idle cursor states.
Twelve host tests check framing, timing accounting and restoration.

The [Microchip ATtiny48/88 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf)
defines SPM and EEPROM sequencing. Flash erase/write stalls the CPU; the
host's 18 ms pause covers the firmware's approximately 5 ms quiet interval
and one Flash operation. The quiet interval is a custom host contract,
not an automatic USB guarantee. EEPROM completion follows EEPE/status,
including the final byte. Raw memory dumps and snapshots remain outside Git.
