# Block64 software validation, October 26, 2026

The original Pass15 source rebuilt to exactly the archived 1580-byte body:
`39f627fb0e67ff7cf69ae146ed0092abfdde2d1452cd109bc6815da517637d55`.
LLVM's pending AVR relocations require explicit GNU AVR linking. A missing
branch target is a tested build failure, not an image to extract or flash.

After the focused development changes, `bash verify.sh` completed with
**565 passed and four strict expected failures**. Build, linked-relocation
audit, sparse HEX reconstruction, range arithmetic and cycle profiling pass.
Expected failures are confirmed USB protocol defects, not skipped tests.

| Result | Value |
| --- | --- |
| Code / reservation | 1588 / 1600 bytes |
| BOOT_AT / application capacity | `0x19C0` / 6588 bytes |
| Body SHA-256 | `5a942d870a2b29bbdb17522c1e2b27a0faa10d5622e83e9e84f678087271106a` |
| Full ISP binary SHA-256 | `bc908f306b45c83fe76c824ce93c46190cefedc2ad23831fc49b49156ad56bdc` |
| USB PHY | 508 bytes, unchanged; SHA-256 `f9a6c9bb587fc6123a384c68f8ae897c228e1bf11fd93cc64dcb168df5b0d63a` |
| CRC routine | 44 bytes, unchanged; SHA-256 `e2ca1be4e1c0ee222eff4eee87df39afe91b36e68feb8b756625efcf2fd142ec` |

The full run covers the imported command/host regressions plus:

- 2304 RX CRC/pointer differential vectors against immutable archived Pass15,
  comparing registers, RAM, flags, stack, EEPROM and I/O state. Pointer reuse
  saves one cycle; the later shared helper adds seven, for a net six-cycle
  increase in that foreground OUT path.
- All 61 flag-arrival phases and no-edge wait behavior; the archived Pass16
  PHY optimization is demonstrably different and remains rejected.
- 403 SETUP checks: 13 valid standard/vendor routes and 390 corruptions across
  every payload/trailer byte and three operation-state contexts.
- 16 reset-flag combinations checking capture, WDRF clear, watchdog write
  timing and application handover.
- 16 strict NVM cases, including real workers and negative hardware-rule
  probes. The strict mode requires explicit fuse assumptions and models
  selected timing/interlock constraints; historical functional mode remains.
- Actual post-decode handshake classification, repeated OUT data and IN TX
  paths. Four contract tests still fail for the intended reason: premature
  ACK, lost IN ACK replay, missing status ACK before SPM, and unrelated status
  completion. Only `USBContractViolation` satisfies their expected-failure marks.

Instruction-only profiles remain EEPROM READ64=628 cycles, EEPROM WRITE64
worker=1856, Flash programming logic=468 and idle dispatch=8. EEPROM busy time,
Flash stalls and electrical USB latency are not included in those numbers;
see [the memory contract](MEMORY_CONTRACT.md) for the separate strict mode.

No physical USB, fuse read, memory programming, cold start, audible application
check or power-loss test was performed for Block64. The installed board and
its application/EEPROM were left untouched.
