# Micronucleus+ ATtiny88 compact Pass26

This is the October 27, 2026 compact strict-USB research line, imported separately
from [Block64](../block64/README.md) and the earlier optimized firmware.
Pass26 uses protocol **v5.5** on an ATtiny88 at 16 MHz. It has **no physical USB
validation**. Its original source and release bytes are retained as the baseline.

The no-LED [protocol 3.0](PROTOCOL_v3_0.md) loader is now
[permanently installed and hardware smoke-tested](docs/HARDWARE_INSTALL30.md).
The earlier [application-only rehearsal](docs/HARDWARE_REHEARSAL30.md) is retained.

The [application layout contract](docs/APPLICATION_LAYOUT.md) keeps ordinary
applications at `0x0000`, patches only RESET, preserves interrupt vectors and
stores the application handoff in the four-byte postscript before the loader.

Development continues in the [Pass28 size-reduction candidate](docs/PASS28.md),
based on the [deployed modular Pass27 checkpoint](docs/PASS27.md) and organized
like the adjacent Block64 source. Use `sh verify27.sh` for active-source work;
`sh verify.sh` continues to reproduce the archived Pass26 release.

The [same-board 2.8/3.0 benchmark](docs/MEMORY_BENCHMARK30.md) covers all 5440
free test bytes and the complete EEPROM. The v3.0 client defaults to a 7 ms
Flash completion wait; override it with `--flash-delay-ms 12`, for example.

| LED profile | Code bytes | USB PHY bytes | BOOT_AT | Application bytes | bcdDevice |
| --- | ---: | ---: | --- | ---: | --- |
| Off | 1206 | 492 | `0x1B40` | 6972 | `0x0550` |
| Active high | 1220 | 492 | `0x1B00` | 6908 | `0x0551` |
| Active low | 1218 | 492 | `0x1B00` | 6908 | `0x0552` |

Application capacity excludes the four-byte postscript. The no-LED build reserves
19 pages; LED builds reserve 20 pages. The host selects geometry from the standard
USB device descriptor instead of probing private memory layouts.

## Build and verify

Requirements: Python 3, a Clang AVR backend, `llvm-objdump`, `llvm-objcopy`, GNU
`avr-ld` and a POSIX shell. On Ubuntu/WSL, `clang`, `llvm` and `binutils-avr`
provide these tools. The builder explicitly links AVR relocations before binary
extraction and opcode tests, including with LLVM 18.

From this directory:

```sh
sh verify.sh
python3 host/compact_programmer.py --help
python3 verify_integrity.py
(cd firmware && sha256sum -c SHA256SUMS.txt)
```

These checks build firmware and execute opcode/model tests without accessing a
USB device. `firmware/` contains the supplied release manifest, bodies, complete
8192-byte images and Intel HEX. Files marked `ISP_FRESH_EXPERIMENTAL` contain
RESET and bootloader code for an initial external-ISP installation; they can
erase the application and are not ordinary application uploads.

## Changes in Pass26

Pass25 occupied 1216/1230/1228 bytes. Pass26 saves ten bytes in each profile:

1. Keep a shared byte cursor in `r4:r5`; READ8 advances it by eight and WRITE4 by
   four. READ8 no longer recomputes a block address, saving four bytes. Sequential
   reads/writes do not need another SELECT.
2. Move the PHY RX length counter from `r19` to `r23`. Replace PUSH with a
   two-cycle `RJMP +0` and remove POP, saving two bytes. Bit sampling keeps its
   schedule; handler return is two cycles earlier.
3. Replace RX `EOR/SUBI/SBCI` with `LDI/ADIW`, saving two bytes with equivalent
   pointer arithmetic and a three-cycle schedule.
4. Replace TX `SUBI/SBCI` with `SBIW`, saving two bytes with equivalent pointer
   arithmetic, live Z flag and a two-cycle schedule.

The PHY shrinks from 498 to 492 bytes. Flash SPM boundary protection, standard
USB dispatch, reply CRC generation and asynchronous EEPROM remain present.
See [protocol v5.5](PROTOCOL_v5_5.md), [register contracts](docs/REGISTERS_AND_CONTRACTS.md)
and the unmodified `PASS25_TO_PASS26.diff` for details.

## Validation limits and next work

The offline suite covers standard requests, emitted reply bytes/CRC, NVM
instructions, cursor movement, boundary protection and host recovery state.
It does not establish electrical USB compatibility or transaction retry safety.
The [import validation](docs/VALIDATION.md) records the successful LLVM 18 run
and exact agreement with all supplied firmware files.
Pass26 inherits Pass25's four-cycle earlier SYNC search and possible early ACK
before nonempty DATA CRC16 validation. Lost ACKs leave write/cursor state
uncertain; the host must verify and reselect rather than blindly replay writes.
Power loss while erasing the RESET page may require ISP recovery.

At `BOOT_AT=0x1C00`, the no-LED source occupies 1202 bytes: **178 bytes over the
1024-byte target**. Keep Pass26 unchanged when developing a separate Pass27
candidate. See [next steps](docs/NEXT_AGENT_PLAN.md) and [validation and risks](docs/VERIFICATION_AND_RISKS.md).

## Contents and provenance

- `variants/strict_usb_optimized/`: supplied Pass22, Pass24, Pass25 and Pass26 ASM.
- `host/compact_programmer.py`: v5.5 client, geometry, RESET/postscript preparation,
  Flash/EEPROM programming and readback. Physical programming requires the
  explicit execution and ISP-recovery flags documented by `--help`.
- `tests25/`, `tests26/`, `tests/`: retained regression models and AVR decoder.
- `build_release26.py`, `audit_phy25.py`, `audit_phy26.py`: builds and PHY audits.
- `history/`: original English verification log; the original-language reports
  are preserved in the complete handoff archive.
- [History](docs/HISTORY.md) and [original archive/bundle provenance](../../../docs/attiny88-history/pass26/README.md).

The original bundle has one snapshot commit, preserved in this branch's ancestry.
Earlier development stages are source/diff checkpoints, not invented Git commits.
The derived work retains Micronucleus/V-USB copyright notices and
GPL-2.0-or-later licensing; see `LICENSE_GPL-2.0.txt`.
