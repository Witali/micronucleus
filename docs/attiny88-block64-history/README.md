# ATtiny88 Block64 import history

The October 26, 2026 handoff is preserved byte for byte in `archives/`.
Archive SHA-256: `d6e3c7c0d43af1ef64dd557b23f558173d650aeca629b20ed27c9966d10aef66`.
It contains ten original stage ZIPs, extracted source snapshots, Pass15,
unverified Pass16 work, and the earlier pre-Block64 handoff.
Original-language documents inside the archive are immutable provenance;
maintained project documentation is in English.

The `feature/attiny88-block64` branch starts from master `49ba54b`. Each
available development stage is imported as a separate chronological commit
under `experimental/attiny88/block64/`. These are reconstructed snapshot
commits, not recovered original Git commits. No original Git repository,
author metadata, or chat transcript was supplied. The additional Pass10
worktree is retained separately because it is not necessarily a successor
to the released Pass10 snapshot.

Generated build outputs and duplicate documents are available in the
original archive; source, host tools, tests and required reference inputs
are extracted into the development tree. The existing Micronucleus+
optimized/verified variants and the installed board are not changed.

## Imported stages

| Stage | Reported code bytes | Protocol / change |
| --- | ---: | --- |
| Block64 v3.0 | 1660 | Read/write up to 64 bytes per control transfer |
| SplitEraseWrite v3.1 | 1728 | Host-controlled separate Flash erase/write |
| RESET-only Pass8 | 1720 | Patch RESET only; native application ISR vectors |
| Pass9 | 1664 | Compact dispatch and range checks |
| Pass10 | 1662 | Unified GET_STATUS |
| Additional Pass10 worktree | See archived artifacts | Parallel working snapshot, preserved independently |
| Pass11 | 1662 | Fixed eight-byte GET_STATUS; modular PHY/EP0/standard code |
| Pass12 | 1606 | DATA OUT and dispatch compaction |
| Pass13 | 1610 in the original stage; a later nested reference has 1600 | Faster EEPROM/Flash paths; distinct artifacts remain preserved |
| Pass14 | 1596 | Shared SPM and 25-page layout at 0x19C0 |
| Pass15 | 1580 | Shared mutation setup and DATA OUT tail dispatch |
| Pass16 WIP | 1576, unverified | CRC pointer reuse and a timing-changing PHY experiment |

Pass15 is the handoff's latest completed software-tested snapshot, using
25 Flash pages and exposing 6588 application bytes. The archived Pass16
builder still labels outputs as Pass15; its size alone is not validation.
No Block64 version in the handoff has physical USB validation. The compact
1274-byte Micronucleus+ loader already installed on the board uses another
protocol and is not evidence of Block64 hardware compatibility.

The handoff prioritizes USB correctness (CRC before ACK, lost ACK/retries,
DATA PID deduplication and status-stage/SPM ordering), followed by a size
target of 1536 bytes without removing memory functionality. See the current
Block64 [development plan](../../experimental/attiny88/block64/PLAN.md).

The original Pass13 stage's body and manifest both report 1610 bytes. A later
`Pass13_baseline` reference is a different 1600-byte artifact. They are not
silently treated as one build. The current development image is 1588 bytes;
its [validation record](../../experimental/attiny88/block64/VALIDATION.md)
separates new checks from handoff reports.

## Reconstructed commit map

| Snapshot | Commit |
| --- | --- |
| Complete archive and index | `ce1c43b` |
| v3.0 | `5726ce6` |
| SplitEraseWrite | `4a74dc5` |
| RESET-only Pass8 | `7949a69` |
| Pass9 | `7d562ec` |
| Pass10 | `90b1895` |
| Additional Pass10 tree | `3967da0` |
| Pass11 | `49714f6` |
| Pass12 | `0d0c97f` |
| Pass13 | `c3b8ffc` |
| Pass14 | `493c8d5` |
| Pass15 | `37e762a` |
| Unverified Pass16 tree | `08ff346` |

Before import, all 1776 archive entries including nested ZIP contents were
locally inspected for credential signatures and private contact patterns;
no matches were found. The outgoing Git objects and commit metadata must
also be checked before publication. This records the scope of inspection,
not a guarantee that a pattern scanner detects every possible secret.
