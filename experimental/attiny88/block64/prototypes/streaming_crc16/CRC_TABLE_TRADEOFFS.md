# CRC table size and receive-cycle experiment

The requested 32-byte table calculates the correct USB CRC16. Its measured
AVR update takes 35 clocks per byte with the table page already selected,
versus 11 for the existing 512-byte streaming pipeline. It cannot replace
that pipeline within the current sampling schedule. The verified 512-byte
variant is preserved separately in [checkpoints/table512](checkpoints/table512/README.md).

## Assembled candidates

| Implementation | Table data | Inline clocks per byte | With page setup | Routine bytes including setup and RET |
| --- | ---: | ---: | ---: | ---: |
| Existing split-page streaming pipeline | 512 bytes | 11 | included in pipeline | Distributed through the sampler |
| Two nibble updates | 32 bytes | 35 | 36 | 58 |
| Separate folded-parity lookup | 16 bytes | 19 | 20 | 38 |
| AVR-LibC table-free formula | 0 bytes | 23 | 23 | 48 |

The standalone measurements exclude function calls: RCALL and RET add
seven clocks. The table candidates assume favorable placement at page
offset zero. The 32-byte low/high halves occupy offsets 00..0F and 10..1F;
four LPM reads and two 16-bit shifts are needed for each byte. The separate
folded candidate performs one lookup and more arithmetic. It is not the
32-byte nibble algorithm.

Table data and alignment padding are different quantities. Removing 480
table bytes does not establish a 480-byte saving in a linked receiver:
instruction size, duplicated stuffing paths and placement also change.
No complete USB image with a reduced table has been built or programmed.

The table-free reference and the folded candidate derive from the official
[AVR-LibC implementation](https://github.com/avrdudes/avr-libc/blob/main/include/util/crc16.h),
reviewed blob `9d3bc825e2767202b425508067892037696e7a92`.
Its redistribution notice is retained in the assembly source.

## Why the current receiver does not have enough slots

An unstuffed byte takes 85 or 86 CPU clocks at 16 MHz. Useful work outside
CRC takes 71 clocks, including decoding, SE0/stuffing checks, storing the
preceding byte, length accounting, fractional correction and loop control.
The existing CRC uses 11 clocks. Three unconditional padding clocks can
also be reused, giving **14 regular CRC slots per byte**.

| Bit interval | Period | Existing CRC clocks | Reusable padding |
| --- | ---: | ---: | ---: |
| 0 | 10 | 0 | 0 |
| 1 | 10 | 0 | 0 |
| 2 | 11/12 | 0 | 0; one extra only on the long path |
| 3 | 11 | 2 | 0 |
| 4 | 11 | 2 | 1 |
| 5 | 11 | 4 | 0 |
| 6 | 11 | 3 | 0 |
| 7 | 10 | 0 | 2 |

The loop-control RJMP at bit 3 is useful work, not a delay instruction.
Eliminating it would require a structural layout or unrolling change and
fresh verification. Stuff bits cannot fund mandatory CRC work because a
valid all-zero payload has none. Average time over a stuffed test pattern
is therefore insufficient.

Even with the table page preloaded, the measured candidates exceed the
unchanged receiver's budget by 21 clocks (32-byte table), five clocks
(16-byte table), or nine clocks (table-free). These are workload bounds;
register transfers, flags, individual sample slots and EOP completion can
impose further constraints. They do not prove that a redesigned receiver
cannot use a smaller table. The 16-byte folded candidate is the closer
option for a future rescheduling experiment.

## Arithmetic and opcode evidence

The nibble recurrence is checked for all **16,777,216** CRC-state/input-byte
pairs against an independent serial reference. Six pytest tests also cover
seed FFFF, reflected polynomial A001, raw residual B001, payloads and
single-bit payload/trailer corruption. The normative CRC definition is in
[USB 2.0 section 8.3.5.2](https://www.usb.org/document-library/usb-20-specification);
the reflected representation reverses the specification's bit notation.

Each assembled candidate passes 73,728 opcode state/input vectors:
all 65,536 states with byte 00, all 256 bytes at sixteen boundary states,
and 4096 reproducible random pairs. Each also passes 36 complete payload
and wire-trailer vectors. This opcode coverage is separate from the full
arithmetic enumeration. A small executor decodes the linked instructions,
checks input/register preservation, and rejects unsupported opcodes.

The saved [measurement record](evidence/2026-10-26-crc-nibble.json) includes
source/code/table hashes and exact cycle and size counts. The read-only
cycle-budget audit traces the existing sampler's actual opcodes. Neither
test establishes electrical compliance or changes hardware.

## Reproduce

Run from `experimental/attiny88/block64` with the project's LLVM AVR tools:

```sh
python3 -m pytest -q prototypes/streaming_crc16/tests/test_crc_nibble.py
python3 prototypes/streaming_crc16/tools/measure_crc_nibble.py
python3 prototypes/streaming_crc16/tools/build.py
python3 prototypes/streaming_crc16/tools/audit_crc_cycle_budget.py
```
