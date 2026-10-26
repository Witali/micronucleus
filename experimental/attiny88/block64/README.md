# Isolated ATtiny88 Block64 experiment

This is a separate experimental protocol line based on the October 26, 2026
handoff. It transfers up to 64 application bytes per USB control transfer;
each physical low-speed DATA packet still carries at most eight payload bytes.
It is not compatible with the stock Micronucleus upload protocol. The existing
verified/optimized Micronucleus+ implementations remain separate.

The experiment is integrated into the default `master` branch under this
directory, alongside the earlier ATtiny88 implementation. Its complete
50-commit development history through `8ce91a5` is preserved by a merge;
`feature/attiny88-block64` remains available for continued development.

| Component | Location | Scope |
| --- | --- | --- |
| Block64 loader development | `source/`, `host/`, `tests/` | 1852-byte loader with documented USB defects |
| Streaming CRC receiver | [prototypes/streaming_crc16](prototypes/streaming_crc16/README.md) | Separate 4096-byte diagnostic body; software traces and application-only USB trial |
| Preserved working CRC variant | [table512 checkpoint](prototypes/streaming_crc16/checkpoints/table512/README.md) | 512 table bytes and 11 CRC clocks per byte |
| Reduced CRC table experiments | [table tradeoffs](prototypes/streaming_crc16/CRC_TABLE_TRADEOFFS.md) | 32/16-byte tables measured separately; not integrated into USB |
| Restricted memory benchmark | [prototypes/memory_benchmark](prototypes/memory_benchmark/README.md) | Physical legacy/new comparison with application/EEPROM restoration |

The branch preserves the complete handoff archive and each available source
stage as chronological Git commits. See the [history and provenance index](../../../docs/attiny88-block64-history/README.md).
The additional Pass10 tree and unverified Pass16 are preserved under `history/`.
Their builders, metadata and tests are historical artifacts, not the active
build interface or a claim of hardware validation.

## Current development result

| Property | Value |
| --- | --- |
| Protocol | Block64 v3.3; fixed eight-byte GET_STATUS |
| Code | 1852 bytes, compared with archived Pass15's 1580 |
| Loader boundary | `0x18C0`; 29 pages / 1856 reserved bytes |
| Application capacity | 6332 bytes; four further bytes reserved for postscript |
| Timed code / CRC | 242-byte sampler and 152-byte TX schedule audited; original 44-byte CRC retained |
| Validation | Software only; nonempty DATA CRC before ACK remains unresolved |

Development changes reproduce the original Pass15 image with current LLVM,
fix watchdog-reset startup and SETUP CRC, retain IN packets until a timely
host ACK, and bind Flash/RUN to their own acknowledged status ZLP. A valid
new SETUP cancels unacknowledged work; already running EEPROM writes finish
without injecting an old status into the new transfer.

Empty DATA1 status packets are CRC-checked before ACK. Token CRC5 is cached
per USB address: a 32-byte/80-cycle helper runs only on an acknowledged
address change, while the common token check costs two additional cycles.
The receiver sampler and TX bit schedule retain their instruction semantics;
transaction bookkeeping intentionally changes outside those timed sections.

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

The remaining strict expected failure is nonempty DATA acknowledged before
its foreground CRC validation. SETUP command protection does not fix that
handshake. Full continuous foreground service latency and electrical USB
operation also remain unproved. The board retains the earlier physically
tested 1274-byte Micronucleus+ loader and its application.

The [streaming CRC design](STREAMING_CRC_DESIGN.md) records a concrete candidate
that distributes table lookup and CRC updates across received bits at 16 MHz.
Its separate [V2 prototype](prototypes/streaming_crc16/README.md) is assembled,
passes the documented digital timing matrices and completed an application-only
physical read trial. It remains separate from the 1852-byte loader. The
[ACK experiments](prototypes/streaming_crc16/ACK_EXPERIMENTS.md) and remaining
foreground/ownership defects must be considered before integration.

The [continuation plan](PLAN.md) prioritizes these transaction fixes before
further size work or physical installation. The inherited first-page power-loss
window also remains: software RESET patching cannot protect a page while it
is being erased.
