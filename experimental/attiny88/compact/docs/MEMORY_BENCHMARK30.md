# Installed 2.8 versus compact 3.0 memory benchmark

The benchmark measures the same ATtiny88 board, 16 MHz clock, Windows USB
driver and PyUSB/libusb0 backend. It compares native protocol operations using
host wall-clock time. It does not measure physical USB bit timing or establish
full protocol compliance. The accepted incoming DATA CRC exception and known
ACK/retry limitations still apply.

`build_benchmark30.py` builds a separate application at `0x1000`, revision
`0x0391`. The production sources and revision allowlist are unchanged. Its PHY
bytes match production, RUN and inactivity exit are disabled, and its final
common SPM executor permits only these initially unused Flash page ranges:

| Start | End, exclusive | Bytes |
| --- | --- | --- |
| `0x0040` | `0x0080` | 64 |
| `0x00C0` | `0x0FC0` | 3840 |
| `0x14C0` | `0x1AC0` | 1536 |
| Total | 85 pages | 5440 |

The remaining pages hold RESET, the entry wrapper, the trial postscript, the
benchmark code, or the installed loader/postscript. The final erase/commit
guard is tested at emitted opcodes for all 1024 possible 16-bit page addresses,
with both operations (2048 cases). EEPROM retains its 64-byte hardware bounds.

The host tool is `hardware/benchmark30.py`. It reuses the preserved benchmark's
meter and verified legacy cursor-priming adapter, adding a dedicated compact
adapter. `tests27/benchmark_host.py` checks host mutation bounds, read-only
rejection and EEPROM busy/reselection/completion handling without USB access.

## Procedure

1. Build the guarded application with `python3 build_benchmark30.py` using the
   AVR toolchain. Run `python tests27/benchmark_host.py` on the host.
2. Run `hardware/benchmark30.py snapshot` while trial `0x0390` or the guarded
   benchmark `0x0391` is active. This phase only reads. Supply `--private-dir`,
   `--expected-eeprom`, `--python-libs` and
   `--dll`. It checks two identical full Flash reads, the original EEPROM,
   erased scratch and the independently verified installed 1274-byte loader.
3. After explicit operator approval and a fresh USB RESET, run the tool's
   `compare` phase with the same paths, plus `--execute-writes`,
   `--fresh-reset-confirmed` and `--micronucleus` pointing to the stock uploader.
   `--flash-delay-ms` defaults to 7 ms. Use `--flash-delay-ms 15` to reproduce
   the initial baseline below.
4. The legacy phase measures reads, EEPROM writes/restoration and one write to
   every initially erased free page. It never sends global ERASE or RUN itself.
   The stock uploader then installs the guarded application in the application
   region, using its normal application erase and RESET/postscript handling.
5. The compact phase verifies its installed code, RESET and original loader,
   measures the same logical workloads, restores EEPROM, erases the test
   pages and checks every application byte outside them. It also verifies the
   installed loader again. The guarded application remains installed.

No fuse, lock or permanent bootloader programming is performed. Private device
dumps, original EEPROM, uploader logs and raw reports stay outside Git.

## Interpretation

- Common Flash reads cover 6908 bytes, three times per protocol. Controlled
  Flash reads verify all 5440 written test bytes. Old EEPROM reads use 64
  one-byte transactions; compact uses SELECT plus eight READ8 transactions.
- Flash program throughput covers native page selection, WRITE4 requests and
  required completion waits. Erase and subsequent readback are separate rows.
  The initial compact baseline used 15 ms after erase and commit; the current
  default is 7 ms, configurable with `--flash-delay-ms`. The old wait comes from INFO.
- EEPROM write throughput includes completion detection: legacy readiness
  polls versus compact SELECT/READ8 polling with a second confirming read.
  Each protocol performs three 64-byte writes, then restores the original.
- Legacy Flash has one sample: rewriting requires a fresh erase, and its
  native erase covers the entire application. Compact has three separately
  erased trials. The transition uploader's total time is not an equivalent
  per-page erase benchmark and must not be compared as one.
- Rates count logical bytes. WRITE4 carries its four bytes in SETUP fields;
  USB data-stage payload counters alone would undercount transmitted data.
- Reports retain measured host waits and transaction counts separately.
  Driver scheduling, USB NAKs/retries and firmware busy time remain included
  in wall-clock throughput. The benchmark does not find the minimum safe
  completion delay or isolate the silicon programming time.

## Board results, 2026-10-27

PASS: every controlled write matched readback, original EEPROM was restored,
all free test pages were erased, other application bytes were unchanged, and
the original loader remained byte-identical. The board now runs the guarded
application `0x0391`; the production bootloader has not been installed.

Rates below are medians in decimal bytes/s, including required completion.
The old Flash write has one sample; other displayed operations have three.
Raw timing summaries are in [the public result](../results/benchmark30-2026-10-27.json).

| Operation | Bytes | Old 2.8, B/s | Compact 3.0, B/s | Compact / old |
| --- | --- | --- | --- | --- |
| Controlled Flash read, identical payload | 5440 | 2668.3 | 2660.5 | 1.00x |
| Flash program, excluding erase | 5440 | 1599.6 | 1332.7 | 0.83x |
| EEPROM read | 64 | 333.5 | 2467.7 | 7.40x |
| EEPROM write, completed | 64 | 99.5 | 125.0 | 1.26x |

Compact erased all 85 test pages in a median 1.362 s. Its program-only median
was 4.082 s, versus the old loader's 3.401 s. The corresponding measured host
waits were 1.295 s and 0.611 s: their 0.684 s difference accounts for the
observed 0.681 s duration difference. Subtracting these waits leaves 2.786 s
and 2.789 s respectively. This indicates comparable transfer cost with the
tested host; the newer protocol's longer 15 ms completion policy limits its
current end-to-end Flash program speed. It does not prove a shorter wait safe.

The tested application and its checked geometry are preserved as
`firmware27/Pass30_benchmark_app.hex` and `firmware27/benchmark30.json`.

## Flash completion delay sweep

The [ATtiny48/88 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf),
section 19.1.4, table 19-1, lists 3.7..4.5 ms for an SPM page erase or page
write. Section 19.2.1 states that these operations halt the CPU. This is the
hardware operation time, starting at SPM, rather than a USB completion delay.
The calibrated internal oscillator times the Flash operation even though the
core uses the board's external clock.

Our command may remain deferred for approximately one 5 ms polling interval
before SPM. A quiet-bus estimate is therefore about 9.5 ms plus foreground
overhead. This is conditional: USB traffic can postpone dispatch, and a
software polling countdown is not a wall-clock completion deadline.

For comparison, official Micronucleus
[ATtiny88 configuration](https://github.com/micronucleus/micronucleus/blob/master/firmware/configuration/t88_default/bootloaderconfig.h)
advertises 5 ms. Its [host library](https://github.com/micronucleus/micronucleus/blob/master/commandline/library/micronucleus_lib.c)
adds 2 ms normally, yielding 7 ms; fast mode uses 5 ms. Our scheduling differs.

`hardware/sweep_flash_delay30.py` tested the already installed protected
application with a new deterministic pseudorandom payload each trial. All
85 free pages were erased, checked, programmed and checked at every level.
The following waits passed on this board:

| Wait after erase/commit | Program 5440 bytes | Program rate |
| --- | --- | --- |
| 15 ms, initial baseline median | 4.082 s | 1332.7 B/s |
| 12 ms | 3.829 s | 1420.7 B/s |
| 10 ms, three trials median | 3.656 s | 1487.9 B/s |
| 8 ms | 3.486 s | 1560.6 B/s |
| 7 ms | 3.401 s | 1599.6 B/s |
| 6 ms | 3.316 s | 1640.5 B/s |
| 5 ms | 3.231 s | 1683.7 B/s |

The user selected **7 ms as the configurable default**. The normal v3.0 host
and benchmark accept `--flash-delay-ms`; fractional positive values are allowed.
The archived v5.5 host keeps its previous default. The fixed wait applies after
each selected-page erase and automatic page commit. No firmware bytes changed
when selecting a different wait.

The sweep restored all test pages, compared every protected byte across the
full 8192-byte Flash including both postscripts, and confirmed unchanged EEPROM.
[Timing-only sweep evidence](../results/flash-delay30-2026-10-27.json) is public;
private preflight dumps remain outside Git. Passing these trials does not prove
7 ms or 5 ms sufficient on every board, bus, supply or temperature. The results
also do not measure electrical USB response timing or minimum completion time.
