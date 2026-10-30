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

## Historical 1 KiB placement audit at 0x1C00

The production source at commit 68a4d21 measures 1380 bytes when built without
LED at the intended 1 KiB start address, 0x1C00. It exceeds the 1024-byte region
by 356 bytes. The four-byte difference from the 0x1A40 checkpoint comes from
the shorter page-aligned Flash guard; it is not a new algorithmic reduction.
This measurement advertises the unknown identity 0xFFFF and is not admitted
by the client. Receiver qualification is still open at both placements.

## Adjacent USB polls retained after timing measurements

Each proposed removal saves two bytes, but merges instruction gaps beyond
the currently admitted 38-clock receiver-entry envelope:

| Poll removed | Legal request | IN SOP after SETUP ACK recovery J | Measured RX entry |
| --- | --- | ---: | ---: |
| Before message-length publication | SET_CONFIGURATION | 76 1/3 clocks | 43 2/3 clocks |
| At reply-limiter entry | Interface GET_STATUS | 91 1/3 clocks | 39 2/3 clocks |
| At EP0 packet preparation entry | SET_CONFIGURATION | 106 1/3 clocks | 43 2/3 clocks |

All corners use a 1.5 Mbit/s host. Those individual tokens decoded; this does
not prove admission for all phases outside the tested entry envelope. The
final TX-length publication guard was retained throughout. No poll removal
was integrated.

## Packet-done counter seed retained

Replacing the packet-done IN/SBRC pair with direct SBIC would save two bytes
and one clock, but the IN also replaces R28 with the PCIF value before the
next wait-for-J loop. The proposed proof that the old R28 could never be
0xFF was disproved: a long malformed K ending in J on the 255th increment,
followed by a wait-for-K timeout, reaches packet-done with R28=0xFF. This is
reachable with a new SOP pending too. The direct-SBIC variant was not admitted;
this counterexample disproves its proposed invariant rather than establishing
its full behavior by itself.

## Current 1280-byte target at 0x1B00

The current target is 1 KiB plus 256 bytes, or 1280 bytes, without LED.
This region starts at 0x1B00. The strict source at 68a4d21 measures 1380 bytes
there, exceeding the target by 100 bytes; the measurement hash is
`4982b48f1f8f6efa479d29204cda697b448ca3fcc5fa3c0a05f696307fc4ec50`.
It remains an unknown-profile measurement with open receiver findings.
Required framing/timing corrections are not yet included in that count, so
the 100-byte difference is not a prediction of the remaining final work.

## Reuse the accepted OUT token as reply completion

R18 still contains the validated OUT PID E1 when control-read status completes. Its bit7 already denotes a finished message, so storing R18 directly removes a redundant LDI and saves two bytes and one OUT-response clock. All128 negative completion values suppress publication; the lifetime regression covers100 delayed builder passes, IN retries, duplicate OUT, a new SETUP/read and reset. Independent324-case GPIO comparison shifts accepted OUT replies exactly one clock earlier; it does not close existing short-EOP receiver timing failures. Standard status and57 completed-read sequences pass on the composed image.

Measured image: 1382 bytes.

## Count disconnect slices without clearing inactive buffers

Replace the startup buffer-clear store and comparison with a YL countdown. The reset initializer owns all live USB state; received and transmit bytes become readable only after complete publication. The no-LED body shrinks by 2 bytes, while the USB receive/transmit instructions and their timing are unchanged. A new cold-start regression poisons all registers and USB SRAM across 256 seeds, checks 1536 initial packet cases and verifies the first descriptor payload and outgoing CRC. All 1536 existing unselected erase/commit guard cases across the LED modes and all 32 reset/handoff cases pass. This remains an audit checkpoint with the existing receiver qualification findings.

Measured image: 1380 bytes.

## Let GET_CONFIGURATION fall through its dispatch test

Move the existing GET_CONFIGURATION body beside its request comparison and invert the conditional branch. This removes one jump without removing any request validation or USB poll. Together with the preceding startup change, the no-LED source is 4 bytes smaller than the 1382-byte checkpoint: 1378 bytes at 0x1A40, or 1374 bytes at the 1280-byte target placement 0x1B00 (still 94 bytes over). Independent checks pass 2213 standard requests, 4032 complete foreground IN exchanges with the unchanged 38-clock maximum entry, and 268 AVR instruction/skip-cycle fixtures. Receiver qualification remains open.

Measured image: 1378 bytes.

## Use the final CRC5 feedback carry

The final five-bit CRC state has bit 4 equal to the last feedback carry. SWAP followed by ROR therefore produces the same endpoint-zero wire byte as three LSL instructions, saving 2 bytes and one clock without a table. Final SREG.C can differ; it is dead before the next carry-dependent branch. All 213248 token field/address/length cases and all 128 atomic pending-address/cache/status-ACK commits pass on the emitted image. Receiver qualification remains open.

Measured image: 1376 bytes.

## Share small standard replies under their specified lengths

GET_INTERFACE reuses GET_STATUS zero bytes. GET_CONFIGURATION retains its configuration-value pointer and shares two-byte availability/publication. USB 2.0 sections 9.4.2 and 9.4.4 specify wLength=1 and explicitly leave other lengths unspecified; the existing limiter still returns exactly one byte for every specified request. All recipient, interface/configuration and descriptor guards and all USB polls remain. The change saves 4 bytes. With the separate CRC5 reduction, the composed image is exactly 1536 bytes at 0x1A00 with unknown identity FFFF, reaching the next 64-byte boundary. Standard, CRC/cache, retry/state, 4032 foreground and 225 minimum-gap checks pass. Receiver qualification and the 1280-byte objective remain open.

Measured image: 1372 bytes.

## Reuse the validated OUT token for protocol-error completion

A protocol error already has a validated OUT token (E1), whose high bit satisfies the existing message-completion contract. Store that token instead of loading a separate FF marker. This saves 2 bytes and one clock on the error response, preserves STALL and queued-command cancellation, and changes no transmitted payload. Both PHY variants use their own live token register. Nineteen status cases now include pending WRITE4, while all 128 negative-marker lifetime cases, delayed builders, reset/replacement, pending-SETUP and 3040 PID-effect checks pass. The composed image is 1534 bytes, with receiver findings still mandatory.

Measured image: 1370 bytes.
