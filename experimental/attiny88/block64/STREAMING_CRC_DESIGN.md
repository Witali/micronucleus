# Candidate 16 MHz streaming RX CRC schedule

This is a design investigation, not an enabled receiver or a completed timing
proof. The board's external oscillator is confirmed as 16 MHz. Incoming DATA
CRC can be accumulated while the bits arrive; checking the entire payload
only after EOP is unnecessarily expensive. The difficult part is placing that
work among the existing samples, unstuffing and byte stores without moving a
sample outside its allowed window.

The starting references are the maintained 16 MHz sampler and upstream
`firmware/usbdrv/usbdrvasm18-crc.inc`. The latter already spreads a table-driven
CRC update across received bits, but its twelve-cycle slots are not directly
usable at 16 MHz. This proposal reschedules those operations instead of
changing the oscillator.

The [official upstream comparison](VUSB_UPSTREAM_REVIEW.md) confirms that
the current official V-USB dispatcher still provides RX CRC checking only
at 18 MHz. Updating the bundled library alone does not supply this feature
at 16 MHz, and the local function calling convention must be preserved.

## Why the existing foreground routine cannot move before ACK

The current 44-byte routine was executed on 4608 archived-opcode vectors:

| Payload bytes | Observed routine cycles |
| ---: | ---: |
| 0 | 19 |
| 1 | 80–88 |
| 2 | 141–154 |
| 4 | 270–286 |
| 8 | 528–551 |

These include RET and exclude call/setup, comparison and handshake work. A
structural bound is `19 + 61*N <= cycles <= 19 + 69*N`; observed extrema are
not claimed to cover every possible payload. Full-payload foreground checking
cannot fit the response interval. The existing bounded empty-DATA check does
not establish CRC validation for nonempty DATA packets.

The [USB-IF USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification),
section 7.1.18.1, measures response spacing from SE0-to-J at EOP to the next
J-to-K at SOP. The detachable-cable limit corresponds to 69.33 nominal CPU
cycles at 16 MHz; the captive-cable limit corresponds to less than 80. A trace
starting at the first SE0 sample must be converted to that specified reference.
Do not spend the whole interval on CRC: packet classification and TX setup
also consume it.

## Byte pipeline and register allocation

Use the reflected USB polynomial `0xA001`, two 256-byte Flash lookup tables,
and a CRC update for the preceding byte while receiving the next byte.

| Candidate role | Register |
| --- | --- |
| Alternating current/previous pin samples | R16, R17 |
| Inverted current-byte assembly | R18 |
| Remaining receive-buffer capacity | R19 |
| Corrected preceding-byte latch | R20 |
| Signed fractional-cycle correction | R21 |
| CRC high byte | R24 |
| Pending table high byte | R25 |
| Unstuff correction mask | R27 |
| Receive-buffer pointer | Y |
| CRC low byte / table index and table page | ZL, ZH |

This consumes additional scratch registers compared with the maintained
receiver. Their caller liveness and any required save/restore operations must
be proved before integration. R26 remains available after reception, but that
alone is not evidence that an existing call convention has been preserved.

The pipeline separates table lookup from its final XOR:

1. In bit 4, finish the preceding lookup: XOR its low result with the old
   CRC high byte, install the pending high result, then XOR the preceding
   data latch into the new low-byte index.
2. In bit 5, load the high table result into its temporary register.
3. In bit 6, load the low table result into ZL.
4. In bit 7, correct the assembled byte, retain it in the data latch and
   reset the unstuff mask. Bit 0 of the next byte stores that latch.

The PID must not enter the DATA CRC. A special first-byte entry can store the
PID using the existing prefix, then make the first virtual data latch zero.
Upstream's `0xFE54` virtual-zero initialization is a useful starting point:
this delayed pipeline needs a proved seed for all three CRC registers, not
just a copied two-byte constant. Initialization, PID-only handshakes and token
packets remain explicit prototype work.

## Concrete normal-path instruction allocation

The proposed physical order is bits 4–7 then bits 0–3, with one wrap jump
after bit 3. Inline inverted unstuff branches for bits 3, 5 and 7 avoid placing
an extra jump in an already full slot. Handler placement must also satisfy
AVR conditional-branch displacement limits.

| Bit | Candidate work between this sample and the next | Cycles |
| ---: | --- | ---: |
| 0 | IN; NRZI EOR/BST/BLD; unstuff MOV/ANDI/branch; count/overflow check; ST | 11 |
| 1 | IN; SE0 check; NRZI EOR/BST/BLD; unstuff MOV/ANDI/branch; one padding cycle | 10 |
| 2 | IN; NRZI EOR/BST/BLD; unstuff MOV/ANDI/branch; fractional correction | 10 or 11 |
| 3 | IN; NRZI EOR/BST/BLD; inline unstuff test; wrap jump | 10 |
| 4 | IN; select high-table page; NRZI/unstuff; EOR low/high, MOV new high, EOR byte/index | 11 |
| 5 | IN; NRZI/inline unstuff; LPM pending table high | 11 |
| 6 | IN; select low-table page; NRZI/unstuff; LPM table low | 11 |
| 7 | IN; NRZI/inline unstuff; correct byte, latch it, reset mask | 11 |

This totals 85 or 86 cycles per unstuffed byte. The signed correction can
retain the existing `SUBI phase,1; BRPL; SUBI phase,-3; NOP` pattern in bit 2:
three clocks on the ordinary path, four on correction. These are instruction
allocations, not assembled, waveform-tested timestamps. In particular, one
must validate sample phase within the byte, not only the total byte length.

## Stuffed bits and EOP

The candidate retains the maintained receiver's inserted-bit durations:
eleven cycles for bit positions 0–6 and ten for position 7. Update the phase
accumulator by `+1` for an eleven-cycle insertion or `-2` for ten, as in the
existing sixteen-megahertz correction scheme. Each handler must correct the
assembly mask, verify the stuffed zero, preserve the next pin-sample role and
return to its scheduled continuation. An inline branch changes the handler's
entry and return timestamps; copying an eighteen-megahertz handler is invalid.

The earliest EOP/unstuff overlap needs special attention. A valid final CRC
can leave a run that enters an unstuff path while SE0 has already begun.
Neither dropping a stuffed-bit error check nor declaring SE0 at an arbitrary
intermediate byte position is an acceptable timing shortcut.

At a completed DATA packet, finish the pending low/high update and feed the
last latched CRC byte through the two tables. A candidate cleanup takes about
sixteen instruction cycles, followed by restoring the context pointer. Test
the USB residual `0xB001` before selecting ACK. This is a budget estimate;
revised EOP detection, ACK-window invalidation, classification and branches
must all be included in the measured turnaround.

Non-DATA packets must take their own path. A one-byte host ACK has no DATA
CRC, and token packets use CRC5. The DATA checker must not accidentally add a
byte to those packets or delay an IN response by a DATA-only cleanup.

## Space and validation costs

The two Flash tables cost 512 bytes, plus up to 255 bytes of initial alignment
padding. Do not put them in SRAM: the ATtiny88 has only 512 SRAM bytes in total
and already needs context, packet buffers and stack. The receiver code also
grows. Any new reservation must update BOOT_AT, application capacity, RESET,
postscript and host metadata together; the old size target is not a reason
to remove CRC or range protection.

The next bounded implementation step is a private, frozen standalone sampler
prototype, not replacement of the maintained receiver. Required checks are:

- Assemble the schedule and enumerate normal and stuffed continuations;
  prove register liveness, branch reach and every GPIO sample timestamp.
- Validate the table byte-step against an independent CRC implementation for
  all 65536 CRC states and 256 input bytes.
- Exercise zero through eight payload bytes, both DATA PIDs, every individual
  payload/trailer bit corruption, cross-byte six-one runs and all arrival phases.
- Include dribble, early SE0, overflow, invalid PID, token CRC5 and PID-only ACK.
- Check complete host retries, ACK loss, receive publication and mutation
  ownership. Preserve the maintained TX waveform and control-transfer contract.
- Measure foreground CRC/reply preparation service latency and continuous
  reception from device DATA through host ACK to the next token. Packet-level
  turnaround alone does not prove this polling firmware can service the bus.
- Perform physical USB validation only after the independent software proofs.

No part of this candidate schedule is enabled by adding this document.
