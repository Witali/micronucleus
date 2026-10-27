# USB protocol checks and accepted receive-CRC exception

## Accepted design assumption, 2026-10-27

The user explicitly accepted acknowledging an incoming DATA packet without
validating its CRC16 first when that validation cannot meet the bootloader's
size and ACK timing budget. This applies to received DATA, including the
eight-byte SETUP payload. The current compact receiver does not validate that
CRC16 before dispatching the SETUP request or applying its side effects.

This is an intentional exception to USB 2.0 section 8.3.5, not a claim of full
USB protocol compliance or proof that a CRC check is impossible to implement.
The outgoing DATA CRC16 remains mandatory and is checked against an independent
reference in the opcode tests.

The assumption is that corrupted packets are sufficiently rare for this
experimental bootloader. If corruption does occur, an altered SETUP can be
accepted as a different command, address or payload. The MCU's final Flash
bootloader-region guard and EEPROM WRITE4 bounds guard remain in place; the
host also validates selectors and verifies writes by reading them back. Readback
can detect data mismatches but does not make early acknowledgment equivalent to
rejecting a bad packet, or guarantee that an unintended command was harmless.

This exception does not waive USB bit timing, transmitted CRC16, token
address/endpoint checks, token CRC5, DATA PID sequencing, ACK-driven retries or
standard control-request behavior. Those checks remain separate audit items.
In particular, a passing size or happy-path transfer test must not be presented
as proof of retry or malformed-packet correctness.

## Open protocol findings

The timing-repair checkpoint still lacks token CRC5, exact token-length and
endpoint-zero checks. Emitted-waveform counterexamples show a response to a
corrupted or absent-endpoint token; an invalid SETUP token followed by DATA can
reach WRITE4. These are open defects, not covered by the receive-CRC16 waiver.
ACK-driven retransmission, duplicate handling and control-pipe error/reset
behavior also require independent admission. Happy-path PID/CRC comparisons
and waveform equivalence do not close those items.

Flash page erase/write halts this MCU. The private host protocol therefore
requires a quiet interval after erase and automatic page commit; its programming
client uses 15 ms. Foreground service bounds exclude that hardware halt.

The normative reference is the USB-IF
[USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification),
sections 8.3.5 (CRC), 8.6.2 (sequence advancement) and 8.6.4 (lost ACK/retry).
The precise source PDF hash and timing requirements are recorded in
[USB_TIMING.md](USB_TIMING.md).
