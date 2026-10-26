# ATtiny88 Block64 development branch

This is a separate experimental protocol line based on the October 26, 2026
handoff. It transfers up to 64 application bytes per USB control transfer;
each physical low-speed DATA packet still carries at most eight payload bytes.
It is not compatible with the stock Micronucleus upload protocol. The existing
verified/optimized Micronucleus+ implementations remain separate.

The branch preserves the complete handoff archive and each available source
stage as chronological Git commits. See the [history and provenance index](../../../docs/attiny88-block64-history/README.md).
The additional Pass10 tree and unverified Pass16 are preserved under `history/`.
Their builders, metadata and tests are historical artifacts, not the active
build interface or a claim of hardware validation.

## Current development result

| Property | Value |
| --- | --- |
| Protocol | Block64 v3.3; fixed eight-byte GET_STATUS |
| Code | 1588 bytes, compared with archived Pass15's 1580 |
| Loader boundary | `0x19C0`; 25 pages / 1600 reserved bytes |
| Application capacity | 6588 bytes; four further bytes reserved for postscript |
| USB PHY / CRC routine | Original 508 / 44 bytes, byte-identical |
| Validation | Software only; four confirmed USB transaction defects remain |

Development changes reproduce the original Pass15 image with current LLVM,
fix watchdog-reset startup, accept only the safe two-byte CRC-pointer saving,
and add a shared SETUP/OUT CRC gate. SETUP protection adds ten bytes after
the pointer saving. Corrupt SETUP fields cannot dispatch memory commands.
Foreground CRC processing adds latency; unchanged PHY opcodes alone do not
prove that following host tokens are always serviced in time.

The full archived Pass16 PHY change is rejected: its clear-flag polling loop
falls from six to five cycles, and its ten-poll timeout from 59 to 49 cycles.
Tests cover all 61 edge-arrival phases and preserve the original behavior.

## Build and checks

Requirements: Python 3.10+, pytest, Clang with AVR support, LLVM objcopy/objdump,
and GNU AVR binutils (`avr-ld`). Use a Linux/WSL environment and activate its
Python environment before running:

```sh
bash verify.sh
python3 host/micronucleus_block64.py --help
```

The builder explicitly links LLVM relocations before binary extraction.
Firmware outputs are `firmware/bootloader.bin`, `isp-full.bin`, `isp-fresh.hex`,
`manifest.json` and `symbols.txt`. Generated files are ignored. The manifest
records development status, source/body hashes and known USB defects rather
than labeling the modified image as an original Pass15 release.
No build or ordinary software test programs a board.

The tests include command/host behavior, Flash/EEPROM bounds, actual opcode
execution, archived differential comparisons, 403 SETUP CRC cases, reset
flags, strict NVM rules and USB transaction regressions. Strict expected
failures are limited to a dedicated protocol exception; other failures cannot
silently count as known USB issues. See [the validation record](VALIDATION.md).

## Memory and USB constraints

The [official-document memory audit](MEMORY_CONTRACT.md) distinguishes the
ATtiny88's CPU-stalling Flash operations from asynchronous EEPROM programming,
documents fuse and timing assumptions, and explains the optional strict model.
It also distinguishes the standard part's 12 MHz rating from the separately
specified automotive grade; a 16 MHz cycle model does not verify the board's
device grade or supply voltage.

Four transport defects remain executable expected failures:

1. The PHY can select ACK before foreground DATA CRC validation.
2. An IN payload/PID can advance before the host acknowledges it.
3. A Flash worker can start without the mutation status packet's host ACK.
4. An unrelated GET_STATUS response can satisfy the pending status marker.

SETUP CRC protection prevents command dispatch from damaged fields; it does
not fix the premature handshake. These conditions make the branch a development
target. The board retains the earlier physically tested 1274-byte Micronucleus+
loader and its application; no Block64 image was installed during this work.

The [continuation plan](PLAN.md) prioritizes these transaction fixes before
further size work or physical installation. The inherited first-page power-loss
window also remains: software RESET patching cannot protect a page while it
is being erased.
