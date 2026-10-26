# Guarded memory benchmark host

`benchmark.py` compares the installed Micronucleus+ 2.8 loader with the
separate guarded streaming-V2 application. Importing the module, `--help`,
and the fake-device tests do not access hardware.

All raw backups and reports must use a fresh private directory outside the
Git checkout. The tool creates exclusive snapshots before mutation and
requires the expected 64-byte EEPROM backup. Legacy CLI mode also requires
the freshly verified original Flash image. Reports contain measurements and
hashes, without raw memory data or USB serial numbers.

Run from `experimental/attiny88/block64`. Root orchestration supplies the
private paths, Windows USB backend, and explicit RESET instructions:

```text
python prototypes/memory_benchmark/host/benchmark.py --help
python -m pytest prototypes/memory_benchmark/host/tests -q
python prototypes/memory_benchmark/host/compare.py PRIVATE_OLD/report.json PRIVATE_NEW/report.json
```

The legacy phase reads all 6908 common Flash bytes in eight-byte control
transfers and reads EEPROM using one-byte `0xA0` requests, with no redundant
ready query before each known-idle read. It benchmarks three EEPROM
write/read/erase-to-FF cycles by default, restores the original EEPROM, then
writes eight initially erased scratch pages exactly once. It does not send
global ERASE or RUN. The necessary subsequent official-CLI upload performs
the application erase and restoration/transition outside this host tool.

Legacy raw Flash page transfer uses request1 followed by sixteen request3
SETUP packets, as implemented in `commandline/library/micronucleus_lib.c`.
The deployed 1274-byte image (`be203513...`) ignores request1 at reset
cursor zero. An independent actual-opcode proof established the safe
preparation: request1 selects scratch if possible, one request3 stages two
temporary-buffer words without a page commit, then request1 selects scratch
and clears the temporary buffer. This preparation has its own timing row.
Every legacy run requires `--legacy-fresh-reset-confirmed` and the direct
API requires `legacy_fresh_reset_confirmed=True`; both default to refusal.
The operator must establish RESET before connection, with no prior Flash
commands or pending command. The flag does not observe MCU registers.

EEPROM is restored before preparing Flash, then checked again in `finally`.
An acknowledged partial buffer can be discarded after a conservative delay
with aligned request1/CTPB. An ambiguous USB data transfer is never retried
or blind-primed: the report requires operator RESET, while the previously
restored EEPROM can still be checked by reading. The tool never programs
page zero or assumes repeated programming of an unerased page is valid.

The new application must advertise `bcdDevice=0x0303`, status marker `0x33`,
features `0x83`, and geometry `0x1FFC/64/64`. Its build manifest must describe
the guarded scratch interval `[0x1800,0x1A00)` and disabled RUN request.
Host mutation checks independently enforce those eight aligned pages and
all 64 EEPROM bytes. EEPROM erase means programming `0xFF` in the normal
erase-and-write mode; it is not a separate erase-only hardware operation.

The new phase uses native 64-byte transfers. Optional equal-chunk controls
use eight-byte Flash reads and one-byte EEPROM reads. The same deterministic
512-byte scratch payload is used by both phases and verified outside write
timing. Full common Flash reads contain different application images, so
their data hashes are retained. Three runs are the default; one to five are
allowed. Legacy Flash has eight per-page samples from one safe write round.

Each timing row separates data/control calls, completion/status calls,
fixed host programming waits, readiness polling sleeps, and other host
overhead. USB call time includes driver scheduling, NAK retries, and device
busy stalls; it is not pure wire time. Fixed waits are host policy, not
measured silicon programming duration. The legacy page wait is the
advertised delay plus the official CLI's 2 ms margin; the new default is
18 ms per Flash operation. Verification is outside the corresponding write
or erase timer. Aggregate scratch-write rows contain their per-page rows;
do not sum both levels.

The old loader only offers a whole-application erase. Its necessary CLI
transition's host-paced erase interval may be reported separately, with its
larger scope and advertised wait. It is unsuitable for a direct speed ratio
against the new eight-page scratch erase.
