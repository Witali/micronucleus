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

The normative reference is the USB-IF
[USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification),
sections 8.3.5 (CRC), 8.6.2 (sequence advancement) and 8.6.4 (lost ACK/retry).
The precise source PDF hash and timing requirements are recorded in
[USB_TIMING.md](USB_TIMING.md).
