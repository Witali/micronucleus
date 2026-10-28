# Measured size reductions

All measurements use no LED at BOOT_AT0x1A40. Receiver qualification remains open.

## Reuse EP0 SETUP validation in foreground

Reuse the existing received-length and token validator instead of repeating its length check. This saves six bytes; the valid-SETUP path retains its timing. Non-SETUP service adds seven cycles, covered by the real-IN polling test.

Measured image: 1402 bytes.

## Pack CRC payload termination into the byte counter

Predecrement the packed payload-byte counter and use borrow for termination. Eight increments of 32 preserve its low byte-count remainder. This saves two bytes and one cycle per copied byte; empty DATA remains unchanged. Independent emitted-packet CRC tests cover 2304 payloads.

Measured image: 1400 bytes.

## Share cold-start and USB-reset control initialization

Cold startup and USB bus reset share the fail-closed control initializer. Startup retains the full context clear and disconnect loop; bus reset adds seven call/return cycles outside packet sampling. Both callers prove R24:R25 zero. Poisoned-state tests exercise 1536 unselected-page guards.

Measured image: 1388 bytes.

## Chain token length, address and CRC checks

CPC carries a cleared equality flag through all three fields, saving four bytes and two valid-token cycles. The strict receiver therefore recalibrates its wait count from 28 to 29; 324 SOP-boundary cases pass, alongside 214272 token cases and 99 minimum-gap ACK-to-SETUP cases. This count is specific to the strict EOF path; a replacement dribble classifier needs its own measured calibration.

Measured image: 1426 bytes.

## Reuse carry for read completion

SBC saves the existing length-comparison carry in the consumed read-only R12 field, replacing a separate flag construction. Empty WRITE4 status bypasses this path and preserves its four payload bytes until ACK. The two-byte reduction passes 57 read-completion sequences, 33 independent packets, 2213 standard requests and the sequential write/read/retry cases.

Measured image: 1424 bytes.

## Use one accepted-SETUP owner

Only validated eight-byte DATA0 SETUP reception installs R3 value 11. Its unique bit 3 replaces historical RX-length/token state, retires the old reply to NAK immediately and lets IN reuse its timed TX-length snapshot. Removing duplicate checks and the now-dead NAK tail saves 26 bytes. Build-time guards reject command-state collisions. Real-wire tests cover 77 ownership/caller cases,864 bounded IN responses,1536 startup guards,324 token deadlines,96 WRITE4,26 READ and99 minimum-gap exchanges. The existing dribble receiver finding stays open.

Measured image: 1398 bytes.

## Reuse the TX line mask as the EOP counter

R21 remains 6 throughout transmission and already supplies the six-count EOP loop. Removing its redundant reload saves 2 bytes. In 975 transmitted DATA/handshake/DDR cases, SE0 changes from 22 to 21 clocks (1.3125us at 16 MHz), within USB2 Table 7-10 limits of 1.25..1.50us and closer to the nominal two-bit interval. The driven J interval remains 11 clocks; ACK eligibility, read completion and minimum-gap WRITE4 exchanges pass.

Measured image: 1396 bytes.

## Use the captured request length directly

The read limiter compares R24 directly with the preserved R6 length byte and uses R6 for the bounded result. Removing the temporary R25 copy saves two bytes and one foreground cycle. The physical receiver/transmitter prefix is unchanged; 2213 standard requests, 57 completed reads, the sequential write/read/retry cases and 4032 foreground injections pass.

Measured image: 1394 bytes.

## Share the service return with SETUP validation

The quiet USB service path falls through to the existing SETUP validator return, saving two bytes. Quiet polling adds two cycles and a pending packet enters RX one cycle earlier; all 802 descriptor/PHY/ACK bytes remain identical. The composed image passes 83 ownership and caller-state cases, 864 IN responses, 96 sequential WRITE4 and 26 READ exchanges, 99 minimum-gap ACK-to-SETUP cases and 4032 real-IN foreground injections (maximum entry 38 cycles).

Measured image: 1392 bytes.

## Share one-byte reply setup and publication

GET_INTERFACE and GET_CONFIGURATION share the one-byte availability instruction and the existing pointer, length and publication tail. The common code is kept in vusb_replies.inc and included beside the interface path to allow fallthrough while retaining AVR short-branch range. The composed image keeps all 802 descriptor/PHY/ACK bytes identical; 108 OUT waveforms match event-for-event. GET_INTERFACE prepares its reply two clocks earlier, while GET_CONFIGURATION and GET_STATUS retain their timing. Standard requests, 57 complete reads, sequential write/read/retry cases and 4032 real-IN foreground injections pass.

Measured image: 1390 bytes.

## Shared helpers rejected after measurement

Similar-looking instructions are not automatically a useful subroutine. These
isolated measurements retain the inlined implementation in the active source:

| Proposed extraction | Code-size change | Timing or contract result |
| --- | ---: | --- |
| Two WRITE4 hardware-buffer word loads | 0 bytes | Adds 14 clocks and two stack bytes between ACK and the next SETUP. |
| Common TX-length load | +4 bytes | Call and return exceed the cost of the duplicated load. |
| OUT/STALL message-state stores | 0 bytes | Adds seven clocks; a control-read status ACK takes 71 clocks, beyond the nominal 6.5-bit bound. |
| SELECT/deferred-SPM opcode setup | +4 bytes | Register adaptation and calls outweigh the duplicate instructions. |

Reset, SETUP and ACK also have different state ownership: reset clears the
address and invalidates page selection, SETUP snapshots pending state, and an
eligible ACK commits it. Combining these distinct contracts would remove
required cancellation or retry behavior.

## Share the standard GET_STATUS request check

Device, interface and endpoint dispatch converge on one request-zero guard after their existing recipient, index and configuration checks. Unsupported request numbers still STALL. This removes six bytes without adding a poll; all 802 descriptor/PHY/ACK bytes stay identical. The exact composed image passes 2213 standard requests, 17 status cases, 57 completed control reads and 4032 real-IN foreground injections, retaining the same maximum 38-clock entry bound. The isolated before/after audit also passes 83 SETUP ownership cases, 864 IN responses and 16 zero-length direction sequences.

Measured image: 1384 bytes.
