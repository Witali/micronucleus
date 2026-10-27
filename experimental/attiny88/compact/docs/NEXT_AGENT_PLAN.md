# Next engineering steps

The no-LED Pass26 source at `BOOT_AT=0x1C00` occupies 1202 bytes, requiring a
further 178-byte reduction to fit 16 pages. At `0x1B40`, it uses 1206 of 1216
available bytes. Do not claim a 1-KiB result without builds and tests.

1. Reproduce all profile sizes, hashes and offline tests. Keep the supplied
   Pass26 ASM as an unchanged control; create a separate Pass27 source/diff.
   Document AVR flag liveness, X/Y/Z lifetimes and exact RX/TX cycle paths.
   Investigate SETUP/IN/OUT retry behavior and early ACK before CRC16 using
   real control-transfer semantics.
2. Measure non-PHY regions by symbols: startup, session handling, standard
   descriptors, selection, Flash SPM, EEPROM, common reply tails and application
   handover. Look for duplicate LDI/STD, reloads and shared noncritical tails.
   Check BRxx range (+/-64 words), RJMP/RCALL placement and both boot addresses.
   The host may handle geometry, alignment and RESET preparation, while the AVR
   must retain erase/write boundary protection.
3. Consider PHY changes only with cycle proofs for NRZI, bit stuffing, EOP,
   ACK/NAK and every sampling path, including late SYNC. Compare emitted words
   and timing separately. Account for phase-specific X/Y/Z reuse and persistent
   `r4:r5` and `r6:r7`.
4. Treat physical testing as a separate step with explicit authorization, ISP
   recovery and Flash/EEPROM backups. Exercise bad CRCs, short/repeated packets,
   lost ACKs, hubs and SPM pauses with USB capture/oscilloscope measurements.

Acceptance requires reproducible profiles and hashes, an appropriate new
bcdDevice, no unresolved AVR relocations, correct app/postscript boundaries,
preserved standard requests and passing opcode/NVM/host tests. Document remaining
USB risks. Compilation alone does not establish compatibility or power-loss safety.

## Deferred: explicit write-completion polling

Deferred at the user's request on 2026-10-27. Keep the current configurable
7 ms Flash wait (`--flash-delay-ms`) while this improvement is pending. See the
[same-board benchmark and delay sweep](MEMORY_BENCHMARK30.md).

Design a separate vendor IN `GET_WRITE_STATUS` request; do not repurpose the
standard USB `GET_STATUS` fields. Required behavior and acceptance checks:

- Report READY only after both queued work and the actual operation finish.
  Account for pending Flash erase/commit, the EEPROM byte queue and EEPE.
  Distinguish USB transaction acknowledgment from command acceptance/completion;
  evaluate a sequence/completion token if a plain BUSY/READY bit can be stale.
- Status reads must leave the memory cursor, temporary page buffer and pending
  command untouched. Current SELECT can replace a queued command, and READ8
  advances the cursor, so neither is a safe Flash completion poll.
- The CPU halts during Flash SPM and cannot transmit even NAK while halted.
  Define how polling interacts with this interval and validate actual USB
  response/retry timing. A missing or malformed response is a transport error,
  never READY and never a substitute for a legal BUSY/NAK response.
- Bound host polling and recovery. After uncertain writes, verify memory and
  re-establish the cursor rather than blindly replaying data commands.
- Preserve standard-request behavior and the cooperative timing bound outside
  SPM. Test queued/busy/complete transitions, early polling, short/error replies,
  ACK loss, bus reset and write readback at emitted opcodes and on the board.
- Measure added Flash bytes and host transaction cost before adopting it. Keep
  this work separate from the 1-KiB size target and document the tradeoff.

No completion-status command has been implemented by the benchmark work.
