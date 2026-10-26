# Block64 software validation, October 26, 2026

## Maintained loader ACK/CRC5 checkpoint

The final unchanged body was checked by 1315 functional cases and eight
independent waveform/timing tests: **1323 passed checks and one strict expected
failure**. The functional total combines its full run with the focused rerun
of the updated address-zero CRC5 initialization expectation. No instruction
changed after that run. The expected failure is nonempty DATA ACK before
foreground CRC validation; streaming RX CRC remains unimplemented in that
1852-byte loader. The separately assembled V2 application, its physical trial,
ACK optimizations and CRC-table experiments have their own
[prototype evidence](prototypes/streaming_crc16/README.md).

## Default-branch integration check

The merge of `feature/attiny88-block64` through `8ce91a5` preserves all 50
development commits under the separate `experimental/attiny88/block64/`
directory. Original default-branch parent: `49ba54b`; merge commit: `d4e0d0f`.
The shared ATtiny88 assembly change outside this folder only corrects a
datasheet-section comment; its instructions are unchanged.

Fresh checks from the integration worktree completed on 2026-10-26:

- `bash verify.sh`: 1323 passed, one strict expected failure, followed by
  passing linked-release/timed-instruction and worker-cycle audits.
- Default V2, optional EOP V2 and guarded benchmark applications rebuild to
  their previously verified hashes. The default V2 smoke suite passes.
- CRC arithmetic, application boundaries, ACK continuation, protected NVM,
  exact historical cursor and host benchmark tests: 75 passed and three
  strict expected failures for inherited continuation/ownership defects.
- The actual-opcode audit confirms 11 CRC clocks and 14 available regular
  slots per receive byte. Saved table512 bytes and sampler match exactly.
- The preceding optimized Micronucleus+ loader rebuilds to 1262 bytes at
  `0x1B00`; its USB substitutions and reply CRC audit pass.

The four expected failures above retain their existing strict trackers;
this merge does not resolve or hide them. No board was programmed during
integration. Private hardware backups and raw device logs remain outside Git.

| Result | Value |
| --- | --- |
| Code / reservation | 1852 / 1856 bytes, 29 pages |
| BOOT_AT / application capacity | `0x18C0` / 6332 bytes |
| Body SHA-256 | `a3f600235ab49d66ef357a859b2d1cbd9bb98a873a9fcb0283748ce75dadb433` |
| Full ISP binary SHA-256 | `4effe20a1ebe4035174fea64c343a8129cbf675b51759a1e89cc43fc0ea6415e` |
| Timed sections | 242-byte RX sampler, 152-byte TX schedule, original 44-byte CRC |
| Classified PHY region | 558 bytes; explicitly changed ACK/token bookkeeping |

The narrow build audit compares actual opcodes and logical branch targets.
It allows only a two-cycle jump in the former TX address-store slot; address
activation now occurs on ACK. Independent mutation tests reject changed
sampler/CRC/TX instructions and an incorrect replacement address slot.

Confirmed transaction properties include identical IN replay until ACK,
rejection of malformed/duplicate/late ACKs, nonzero-endpoint rejection,
SET_ADDRESS activation only after its status ACK, and own-transfer ownership
for Flash/RUN. New SETUP cancels unacknowledged work. EEPROM completion cannot
inject its old ZLP into a newer transfer. A valid empty DATA1 OUT can complete
a control read when its last IN ACK was lost.

The cached token CRC5 helper is 32 bytes and exactly 80 cycles across all
128 addresses and four initial flag patterns. It changes only SRAM `0x012E`
and scratch R18/R22/R23. It runs only on an acknowledged address change,
inside the SET_ADDRESS recovery interval; ordinary tokens pay two extra
comparison cycles. Independent tests cover all 32 CRC values for each
address and each token PID, endpoints and real SET_ADDRESS ACK/abort paths.

Independent full-waveform checks cover:

- 1408 valid DATA0/1 frames with stuffing patterns and arrival phases.
- 480 IN response cases and 600 random TX waveform comparisons.
- 720 full-wire CRC5-corrupt IN/OUT/SETUP tokens and 96 valid controls.
- 188 ACK-SOP arrival times, no-edge timeout and six complete ACK waveforms.

The [USB-IF specification](https://www.usb.org/document-library/usb-20-specification),
sections 7.1.18.1 and 7.1.19.1, defines the timing reference and deadlines.
At nominal 16 MHz, measured end-EOP-to-SOP ranges are:

| Path | CPU cycles |
| --- | ---: |
| IN to DATA | 61.33–62.33 |
| CRC-valid empty DATA1 OUT to ACK | 59.33–60.33 |
| Eight-byte DATA1 to ACK | 46.67–47.67 |

All fit the stricter detachable-cable limit of 69.33 cycles; worst nominal
margin is seven cycles. ACK SOP at cycle 179 remains eligible; cycle 180
onward is disarmed, within the 16–18-bit SOP timeout window. Completing ACK
reception after that SOP deadline does not invalidate a timely start.

A continuous ACK-to-next-IN probe catches 22–47-cycle gaps. Foreground/caller
re-entry beyond that probe, electrical operation and real-host reliability
remain unproved. Packet-level turnaround is not a complete USB certification.

Instruction-only memory profiles are EEPROM READ64=628, EEPROM WRITE64
worker=1856, Flash write logic=470, idle dispatch=8. The Flash increase of two
cycles clears completed transfer ownership. Peripheral busy time/stalls are
excluded here and separately exercised by strict NVM tests. No physical board
was programmed. See [the streaming CRC candidate](STREAMING_CRC_DESIGN.md)
for the next receiver step and its unproved timing obligations.

---

# Initial import validation (historical iteration)

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
