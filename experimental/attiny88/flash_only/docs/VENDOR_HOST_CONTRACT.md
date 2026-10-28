# Vendor request trust boundary

The computer client owns validation of custom command numbers, command
parameters, memory geometry, bmRequestType direction/recipient and wLength.
It emits device vendor OUT0x40 writes with no data stage and vendor IN0xC0
READ8 requests. The firmware does not duplicate these vendor-field checks.

The firmware still separates standard, class/reserved and vendor request
types. Standard requests keep their USB-defined handling; unsupported
class/reserved requests STALL. Vendor dispatch retains cheap recognition of
READ8 and the supported write commands; unknown opcodes currently STALL.

Every vendor write explicitly selects write-status state before polling USB.
Consequently an OUT cannot stand in for the ACK of its IN status packet,
including for an out-of-contract vendor request received on the wire.
Queued erase/commit/RUN work still requires that ACK, and reset/new SETUP
cancel stale work. The selected-page and boot-region protection remain.

This host-only vendor-field contract does not relax USB token address,
endpoint, framing, CRC5, handshake or timing requirements. The separately
documented incoming DATA CRC16 waiver is unchanged.
