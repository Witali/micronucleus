# ATtiny88 USB upgrade and memory tests — October 25, 2026

Result: **PASS** on the connected ATtiny88 board. The stock Micronucleus 2.2 loader was replaced over USB; no ISP programmer was used. The final board runs the known 200-byte LED application through the corrected Micronucleus+ 2.8 loader.

## Installed target

| Property | Observed value |
| --- | --- |
| MCU signature | `0x1E9311` (ATtiny88) |
| USB VID/PID and version | `16D0:0753`, bcdDevice `0x0208` |
| Physical Flash page | 64 bytes |
| Loader address and size | `0x1AC0`, 1344 bytes |
| Application capacity | 6844 bytes, previously 6650 bytes on the stock 2.2 device |
| Feature byte | `0xE0` (Flash read, EEPROM, saved MCUSR) |
| Final body SHA-256 | `ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc` |
| Tested updater application | 1942 bytes of text, linked at `0x0080`, ending at `0x0816` |
| Updater HEX SHA-256 | `7c35513bd50ff7830747aaa2a9edc61c6b92ffc6710599dee67d21aea192b21e` |

## Preparation and defects caught before completion

1. Found the generic upstream `firmware/upgrade.c` and existing `firmware/upgrades/upgrade-t88_default.hex`. Corrected the earlier handoff claim that upstream only supplied an ATtiny85 implementation. Adapted its application-based page replacement flow for the imported strict image.
2. Built and executed the updater using the MicroMusic CPU and an explicit ATtiny88 NVM shim, and independently with current simavr's CPU/native SPM engine plus documented target shims. Cases cover byte-exact installation, intact updater code, late RESET handover, disabled SELFPRGEN, corrupt payload, failed readback, and five restart boundaries.
3. Ran the imported strict USB source as an application at `0x1000`, leaving the old loader at `0x1A00` untouched. The first trial enumerated but returned empty extension replies. Complete-packet review found two defects missed by the old handler-only tests: extension routing from the actual vendor path, and SRAM replies passed to LPM. Added complete SETUP-to-TX regression coverage and corrected both.
4. Through the corrected rehearsal, read all 8192 Flash bytes and 64 EEPROM bytes twice and compared both reads. Saved local backups and an ISP recovery HEX before permanent replacement. Raw device contents remain outside this public repository.
5. The first permanent installation exposed a further startup defect: WDRF remained set during watchdog disable. USB returned after a full power cycle, proving that the new loader had been installed. Moving the existing MCUSR save/clear before watchdog disable fixed this without increasing body size. GET_CONFIGURATION was also routed through the SRAM reply helper.
6. Rebuilt and reran both updater models and 18 complete-packet cases, adding POR/EXTR/BOR/WDR/mixed flag checks. Installed the final image through the working 2.8 loader. USB returned automatically after the updater's watchdog reset, without a button or power cycle.

## Final real-device checks

- Information query reports 2.8, signature `0x1E9311`, 64-byte pages and 6844 application bytes.
- Standard GET_CONFIGURATION returns configuration 1 from the SRAM reply path.
- Reads at the protected Flash boundary are rejected.
- All 64 EEPROM bytes initially matched the pre-upgrade backup.
- Uploaded the 200-byte LED application through the new loader; readback matched every source byte except the expected bootloader-patched RESET, which was checked separately as `0xCD5F`.
- The application was started. The user pressed the RESET button and confirmed the three-short/one-long LED pattern returned; a waiting information query also observed the new loader.
- After the memory cycles below, the user explicitly removed USB power for 2–3 seconds and reconnected it. The information query again identified the final loader, and the user confirmed the LED pattern returned after the loader window.

## Physical write/read/erase cycles

The existing mock/CPU tests already covered host operations and handler boundaries. The new opt-in `test_hardware_memory.py` adds the missing physical end-to-end cycles, reusing the existing host library.

| Check | Result |
| --- | --- |
| EEPROM: write/read all 64 bytes with a deterministic pattern | PASS |
| EEPROM: erase to `0xFF` and read all 64 bytes | PASS |
| EEPROM: restore and verify original contents | PASS |
| Flash: write/read all 6844 application bytes, accounting for patched RESET | PASS |
| Flash: erase and verify all 6844 application bytes are `0xFF` | PASS |
| Flash: restore LED application and verify readback | PASS |
| EEPROM: recheck original contents after all Flash operations | PASS |
| Start restored LED application | PASS |

EEPROM erase is performed through its existing erase/write command by programming `0xFF`; the protocol has no separate EEPROM erase opcode. The test temporarily changes memory and restores it, requires an explicit hardware flag and backups, and never runs during ordinary unit-test discovery. See [the retained result](evidence/memory-cycle.json) and public command logs under `evidence/`.

## Reproducibility and limits

- LLVM/Clang 18.1.3, GNU AVR binutils 2.26, AVR-GCC 7.3.0 and AVR libc 2.0.0 in Ubuntu WSL.
- MicroMusic CPU source SHA-256 observed during checks: `718f63991289a6021c9eb226b8f4e26480215f8d2a3cee847b08ebe969b9defa`. The sibling repository was imported read-only and not modified.
- simavr source commit: `5b08da60497f7564f50941f74a549fe2851db030`. Its ATmega88 substrate was restricted to tiny88 RAM/EEPROM and 64-byte NORWW Flash; the missing CTPB command was supplied by the harness. It is not represented as a complete native ATtiny88 peripheral model.
- Device backups are local under `C:/Work/MicroNucleus/validation/board-backup-2026-10-25`; they include stock-loader recovery data and EEPROM. They were not pushed to GitHub.
- No fuse settings were changed. ISP was available as a recovery contingency but was not used. Power-loss corruption during first-page erase/write is not eliminated, and these observations apply to this board and clock setup rather than every possible ATtiny88 installation.
