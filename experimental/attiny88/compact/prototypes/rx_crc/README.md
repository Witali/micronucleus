# Table-free receive CRC16 feasibility, 2026-10-27

**Result:** online CRC is mathematically possible, but neither compact integration
tested here fits the existing 16 MHz receive schedule. Both are rejected. This
is a bounded result for the current receiver and these designs, not a proof that
every replacement receiver is impossible. No active firmware was changed.

## Pinned input and measured integrations

`baseline.S` is an immutable preprocessed copy of the coherent cooperative
candidate, built with Clang/LLVM 18.1.3 and GNU AVR ld 2.26.20160125 for ATtiny88,
no LED, `BOOT_AT=0x1C00`. It is **1144 bytes**, not the integrated timing
checkpoint `ce74532` at **1146 bytes**: the extra foreground EEPROM poll is
outside this PHY. The pinned input and rejected variants are isolated research
artifacts; the active firmware build does not include this directory.

The baseline derives from `source/micronucleus_t88_compact.S` and its include
modules under GPL-2.0-or-later. Contributor provenance remains in the project's
[history](../../docs/HISTORY.md) and [GPL license](../../LICENSE_GPL-2.0.txt).
The adapted fast-byte kernel retains its separate GPL v2/v3 attribution in
`crc_arithmetic.py`. Full external V-USB sources and tables are not copied here.

| Design | Linked bytes | Delta | CRC cost per decoded bit | Clean synchronized controls |
| --- | ---: | ---: | --- | --- |
| Frozen baseline | 1144 | 0 | none | 16/16 correct |
| Inline streaming LFSR | 1230 | +86 | +5..6 cycles | 0/16 correct |
| Shared streaming helper | 1198 | +54 | +12..13 cycles | 0/16 correct |

The controls are DATA0 zero8, ff8 and ramp8, plus empty DATA1, each entered
5/20/30/40 cycles after SOP at nominal host rate. Both integrations corrupt
even these clean inputs, before a useful CRC-admitted ACK can be demonstrated.
For zero8 at entry 20, the baseline captures `c30000000000000000bff4`;
the inline version captures `e7db6db7dd3e`. Full results for all 32 rejected
controls and 32 corresponding baseline controls are in `insertion-results.json`.
These are synthetic public test bytes, not captured user data.

Both prototypes allocate R2/R19 to receive CRC and reuse ZL/ZH for A001 during
RX, restoring the context pointer before packet dispatch. R2's old preservation
promise would change; it is currently unused by foreground code. R0/R1,
R24/R25 and X remain intact in every control. Standalone peak stack remains
4 bytes; adding the caller's cooperative-service frame gives the existing
6-byte nesting bound. The shared CRC call uses the same nesting depth as the
existing acquisition delay call; it needs no additional register spills.

## Emitted receive budget

`budget.py` checks 768 packets: every repeated byte value and 128 random
eight-byte payloads, with both DATA PIDs. Its normalized output has 15 actual
instruction-path variants and all sample-site classes below. Offsets identify
the emitted IN instruction relative to its assembly label.

| Sample path | Cycles |
| --- | ---: |
| acquisition sample -> first regular sample | 10 |
| regular even -> regular odd | 10 |
| regular odd -> regular even / bit6 sample | 11 |
| bit6 -> bit7 | 11 or 12, phase correction |
| bit7 -> next byte bit0 | 11 |
| regular even/odd -> their stuffed sample | 10 |
| stuffed even -> regular odd | 11 |
| stuffed odd -> regular even / bit6 | 12 |
| bit7 -> stuffed-bit7 sample | 10 |
| stuffed-bit7 -> next byte bit0 | 11 |
| stuffed-bit6 retry -> bit7 sample | 11 |

These intervals are occupied by sampling, decoding, stuffing, counter/phase
work and control flow. There is no spare five-cycle slot on every bit. The
one-cycle phase NOP occurs only on selected paths; two-cycle jumps to the next
word occur in particular stuffing paths, not every unstuffed bit.

An optimistic count of **all** NOP/next-word-RJMP cycles after the first complete
payload byte and before EOP finds only 5 cycles for zero8, 3 for ramp8, and
16 for ff8. The table-free byte update below requires 160 arithmetic cycles
for eight bytes, plus 8 copies, even before checking liveness or stage overhead.
It cannot be distributed into those existing delay slots. A new RX schedule
would have to remove useful work or duplicate/restructure the decoder.

## Table-free arithmetic and pipelining check

Let A be one zero-input reflected CRC step with polynomial A001. A streaming
state T can consume the incoming decoded carry directly:

`T' = (T >> 1) XOR (input << 15) XOR (A001 if T.bit0 else 0)`.

The invariant is `standard_state = A^16(T)`. Initial T=1557 corresponds to
standard FFFF; valid received CRC residue B001 corresponds to T=FFFF. The
five-instruction AVR kernel takes 4 or 5 cycles, then one additional LSL
restores the decoded carry for the original byte assembler. This avoids an
input XOR and an extra bit-save register, but still exceeds the available slots.

`crc_arithmetic.py` verifies the invariant for every 65536 state and both input
bits (131072 cases), executes the streaming kernel for 2062 representative
state/input cases, and executes a table-free fast byte kernel for all 65536
effective (old-high, old-low XOR data) combinations. The fast byte kernel is
40 bytes of arithmetic plus RET, **20 cycles per byte**, or 21 including the
completed-payload copy; it needs CRC R2/R19 plus persistent temps R30/R31.
Pipelining changes when those instructions run, not their absent cycle budget.

`vectors_and_slots.py` independently de-stuffs 4864 valid packets, excludes
SYNC/PID, includes both received CRC bytes, and checks the FFFF transformed
residue. It removes 1760 stuffed bits and rejects 3456 single-bit payload/CRC
mutations mathematically. These arithmetic results do not turn either failed
integration into a working receiver or establish malformed-packet ACK timing.

If a replacement schedule made the CRC state available by EOP, the prototype's
final residue test plus context restoration would cost 5 accepted-path cycles.
The blocker found here is the receive schedule, not a demonstrated impossibility
of performing that small final decision before ACK. No valid-packet ACK/EOP
admission is claimed for the rejected prototypes.

## Official prior art and hashes

The official [18 MHz CRC backend](https://github.com/obdev/v-usb/blob/master/usbdrv/usbdrvasm18-crc.inc)
does pipeline byte work across bit slots, but uses two aligned 256-byte tables
(512 bytes), excluded by the user's constraint. Its
[configuration documentation](https://github.com/obdev/v-usb/blob/master/usbdrv/usbconfig-prototype.h)
restricts that backend to 18 MHz. Its separate
[fast outgoing CRC](https://github.com/obdev/v-usb/blob/master/usbdrv/usbdrvasm.S)
provides the table-free byte arithmetic tested above (Slawomir Fras/Shay Green,
Objective Development contributors, GPL v2/v3). Only that small kernel is
adapted; no external tables belong in the project. ATtiny88 has no MUL
instruction ([Microchip AVR515, table 4-1](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8089.pdf)).

Full SHA-256 values:

```text
baseline.S   8d77ea1e82f572f9c550171563573941391562db99c8d1441149503f78608c65
baseline body 07d88bc21d932b2d19c9969f988dfa01f0d68eb4902545aaf07773d5f2fa5fe2
inline_crc.S 5417bd55d228558ecfc3d03f7314e1392b443793bae6c7204270fe265d870e19
inline body  8c94b6523a0fcf9f091172cdfa72d93789697a30963d95ec931eda564d748674
shared_crc.S 6c85d8b706a6acc682f2e39a1792885ae2876bb2fcd6b812fbccb7f4fb86877e
shared body  aad0b63732899ca6a34e56a765df639ae37501a7a7fe55c3ae0b260e810d508a
18MHz source fe25c95cdc4e503475f04bc8888dcedcb27596db18cb04aec4d073b659a677ff
fast source  ad37642c953091124fed7c5b060a52974c227cab1ad0c9e04e4e5f3a5acc5a79
```

## Reproduce

Keep the supplied `baseline.S`; `freeze()` requires its exact SHA-256 and has no
fallback to a moving source. The scoped Git attribute preserves its bytes across
Windows checkouts. This experiment runs offline against the repository's AVR
interpreter; prior-art URLs/hashes are metadata and require no source download.
From the repository root in WSL/Linux with the AVR tools on PATH:

```sh
cd experimental/attiny88/compact/prototypes/rx_crc
python3 probe.py
python3 crc_arithmetic.py
python3 budget.py
python3 vectors_and_slots.py
```

`inline_crc.patch` and `shared_crc.patch` are minimal diffs from the frozen
baseline. `probe.py` regenerates both and rejects undefined symbols and branch
relocation errors; required long branches are expanded explicitly and charged
to size/timing. The CRC algebra is valid, but neither integration is admitted.
