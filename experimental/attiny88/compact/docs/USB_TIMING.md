# USB Low-Speed timing requirements and audit status

The source is the USB-IF [USB 2.0 specification package](https://www.usb.org/document-library/usb-20-specification),
[downloaded package](https://www.usb.org/sites/default/files/usb_20_20250603.zip).
The contained `usb_20.pdf` has SHA-256
`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`.
The local copy is audit input, not a redistributed project artifact.

Relevant printed pages: 159 (SYNC and signaling rate), 168 (turnaround),
182-183 (Table 7-10), 191 (Figures 7-49/50/51). The PDF physical page numbers
are these printed numbers plus 28. Tables and waveform figures were rendered
and visually checked rather than relying on extracted table-column order.

## Digital constraints at an exact 16 MHz CPU clock

One CPU cycle is 62.5 ns; a nominal 1.5-Mbit/s bit is 10 2/3 cycles. Integer
instruction slots cannot make every individual bit exactly that long. The audit
must check rate and transition jitter separately, including bit stuffing.

| Requirement | Limit | Specification |
| --- | --- | --- |
| Low-Speed function transmit rate | 1.4775-1.5225 Mbit/s | 7.1.11, Table 7-10 |
| Source jitter, next transition | -95 to +95 ns | Table 7-10, Figure 7-49 |
| Source jitter, paired transitions | -150 to +150 ns | Table 7-10, Figure 7-49 |
| Differential-to-SE0 skew | -40 to +100 ns | Table 7-10, Figure 7-50 |
| Transmitted EOP SE0 | 1.25-1.50 us, 20-24 cycles | Table 7-10 |
| Drive J before disabling outputs | One bit time | 7.1.18.1 |
| Device response interpacket delay | At least 2 bit times; at most 6.5 detachable / 7.5 captive | 7.1.18.1 |

SYNC is three KJ pairs followed by KK; stuffing inserts a zero after six ones.
Turnaround is measured from incoming EOP's SE0-to-J to the response's J-to-K,
not from a sampled SE0 instruction. Next and paired transition errors use the
different edge pairs shown in Figure 7-49; accumulated phase over an entire
packet is useful diagnostic data but is not a replacement for those limits.

For receiver tests, a USB 2.0 host/hub source has the tighter +/-0.05% clock
requirement, not the Low-Speed function's +/-1.5%. Source and receiver jitter
envelopes must be distinguished. Oscillator error consumes the same timing
budget; an ideal-clock model does not admit every nominally 16-MHz oscillator.

## Defects exposed by the audit

The inherited TX seed `0x35` produces 84 cycles per unstuffed byte, or
1.5238095 Mbit/s at 16 MHz: outside the function rate interval. The inherited
tail drives J for only one cycle before DDR release. Preserving this instruction
stream byte for byte therefore does not establish specification timing.

The integrated repair uses seed `0x3B`, useful work scheduled after
asserting J, and a shifted pending-address representation to shorten the final
data-to-SE0 path. The alternating-seed alternative was rejected because its
transition jitter exceeded the limits. At exactly 16 MHz, 85 cycles per
unstuffed byte gives 1.5058824 Mbit/s. DATA SE0 is 23 cycles, handshake SE0 is
22 cycles, and J remains actively driven for eleven cycles before DDR release.

Holding J for the required time also exposes a flag race: the caller's redundant
PCIFR clear can erase a next SOP at the legal minimum gap. Inline timeout cleanup
plus removing the caller clear avoids that race, without an uninitialized-Z
store. The current timeout and TX tail share a context/polynomial return;
the internal acquisition delay calls only its polynomial-load/RET suffix.

The old resynchronization tail could
discard legal next-packet edges while reply work is underway. A correct bit
generator alone does not prove bounded response timing. Cooperative service
now covers the long paths, including WRITE4 and zero-length replies. The
no-packet foreground sweep has a maximum 32-cycle interval between PCIF reads;
five cycles to enter the PHY plus up to three PCINT synchronization cycles give
a conservative 40-cycle physical-SOP bound for those modeled paths.

That bound excludes the hardware CPU halt during page erase/write SPM.
The host must leave a quiet interval after SELECT+ERASE and the WRITE4 that
commits a complete Flash page. The v3.0 client defaults to 7 ms after each,
configurable with `--flash-delay-ms`; the archived v5.5 client retains 15 ms.
The shorter wait passed same-board testing; see [the measurements](MEMORY_BENCHMARK30.md).
For the archived protocol,
its protocol contract is documented in [PROTOCOL_v5_6.md](../PROTOCOL_v5_6.md).
The digital instruction model checks protected operands and command gating,
not USB servicing while the Flash hardware has halted the processor.

## Evidence and remaining scope

The user-approved receive-CRC16 exception is recorded separately in
[USB_PROTOCOL.md](USB_PROTOCOL.md). It permits early ACK for incoming DATA;
it does not relax the timing limits above or the transmitted DATA CRC16.

Raw-opcode RX experiments independently encode packets, including CRC5/CRC16,
NRZI, stuffing and EOP, then compare captured bytes. Finite rate/entry/jitter
sweeps currently support a conservative 40-cycle entry budget; they do not prove
every legal waveform. The maintained cooperative model includes the digital
GPIO synchronizer and PCINT pipeline, including flag reassertion after W1C.
Analog propagation, rise/fall times, voltage thresholds, oscillator drift and
physical hubs remain outside the model.

`sh verify27.sh` records the integrated checkpoint in
[PASS27_COOPERATIVE.log](PASS27_COOPERATIVE.log). Across three LED profiles it
passes 186 synchronized transaction scenarios, 125943 no-packet poll intervals
and 12654 TX waveform/state cases. The selected transaction maximums are
38 2/3 cycles from physical SOP to PHY entry and 47 1/3 cycles from received
SE0-to-J to response SOP; peak modeled stack use is six bytes.

The TX sweep checks actual PORT/DDR writes against an independent stuffed-NRZI
encoder, covering both DATA PIDs, all payload lengths, random payloads and all
byte/trailing-ones combinations. At exactly 16 MHz it measures:

| Measured quantity | Observed range | Required interval |
| --- | --- | --- |
| Next-transition jitter | -62.5 to +41 2/3 ns | -95 to +95 ns |
| Paired-transition jitter | -83 1/3 to +41 2/3 ns | -150 to +150 ns |
| Differential-to-SE0 skew | 0 to +41 2/3 ns | -40 to +100 ns |

These finite results do not establish all-waveform receiver coverage or close
the separate protocol defects and hardware checks.

Each timing optimization must preserve/register its live inputs, count all
conditional/skip paths and expose margin to both interval edges. Replacing a
delay with useful work is admitted only after the complete affected path has
been measured. A fitting image and passing old/new equivalence checks alone
must not be labeled USB timing admission or USB-IF compliance.
