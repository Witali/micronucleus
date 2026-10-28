# USB specification and executable requirements

Reference: [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification),
Revision 2.0, full-/low-speed clauses. Tests execute linked AVR instructions;
their wire encoders and CRC oracles are independent of the firmware.
Firmware identity or a smaller binary alone is never an admission criterion.

| Required behavior | Specification basis | Executable checks |
| --- | --- | --- |
| NRZI and eight-symbol low-speed SYNC | Sections 7.1.8 and 7.1.10 | `test_usb_rx_waveforms`, `test_ep0_failed_sync`, `test_tx_digital` |
| Stuffed zero after six ones, including before EOP; reject seven consecutive ones | Sections 7.1.9/7.1.9.1 | `test_usb_rx_waveforms`, `test_tx_digital` |
| Accept only permitted all-one final dribble; reject arbitrary fractional DATA tails | Section 7.1.9.1, Figure 7-33 | `test_data_framing`, `test_usb_rx_waveforms` |
| SETUP still contains eight payload bytes and both CRC bytes; truncated fields cannot manufacture a byte | Chapter 8 packet/control formats | `test_data_framing`, `test_setup_pending_marker`, `test_rx_context_restore` |
| Supported PIDs have the correct complement; foreign address/endpoint and bad token CRC5 cannot authorize a transaction | Chapter 8 PID, address, endpoint and CRC fields | `test_token_crc5`, raw PID-admission matrix, `test_usb_rx_waveforms` |
| Source EOP SE0 lasts 1.25..1.50 us; receiver accepts 670 ns and ignores differential-crossover SE0 up to 210 ns | Table 7-10, Section 7.1.13.2 | `test_tx_eop_counter`, `test_usb_rx_waveforms`, `test_usb_crossover` |
| A crossover transient cannot authorize a four-byte IN token as a three-byte token plus dribble | Section 7.1.4.1, Table 7-10, Chapter 8 token format | `test_token_crossover_admission` |
| Device data rate is 1.4775..1.5225 Mbit/s; high-speed-capable host low-speed rate is 1.49925..1.50075 Mbit/s | Section 7.1.11, Table 7-10 | Host-rate/phase matrices, `test_tx_digital`, `test_rx_jitter_spec` |
| Driver jitter, clock accuracy and permitted total jitter are assessed with the correct upstream/downstream direction | Section 7.1.15.1, Table 7-5, Table 7-10 | `test_tx_digital`, `test_rx_jitter_spec`; opcode identity alone is insufficient |
| Response begins after at least two response bit periods and before the applicable 6.5-bit connector bound | Section 7.1.18.1 | Physical recovery-J to first-K timing in token and DATA response matrices |
| A following transaction at the physical two-bit gap must be received intact | Section 7.1.18.1 | `test_ack_followup`, `test_sequential_wire` |
| ACK/token response eligibility expires no earlier than 16 and before 18 bit periods | Section 7.1.19.1 | `test_ep0_ack_timeout`, `test_ep0_token_timeout`, dribble deadline matrix |
| DATA/PID remain immutable until eligible ACK or control-status completion; repeats do not duplicate a write | Chapter 8 transaction/retry rules | `test_ack_regression`, `test_ep0_read_completion`, `test_sequential_wire` |
| New SETUP and reset cancel old transfer ownership; no stale erase/program/RUN is released | Chapter 8 control transfers, Chapter 9 reset states | `test_setup_pending_marker`, `test_ep0_shadow`, `test_ep0_reset`, `test_nvm_state` |
| Standard requests, recipients, zero-length direction, SET_ADDRESS status sequencing and protocol STALL are correct | Chapter 9, Sections 9.3.1 and 9.4 | `tests34/test_standard.py`, `test_ep0_standard`, `test_ep0_zero_direction`, `test_ep0_status` |
| Control reads finish correctly at exact/short/zero lengths and required terminating ZLPs | Chapter 8 control transfers | `test_ep0_reply_fragments`, `test_ep0_read_completion` |
| Outgoing DATA CRC16 is correct | Chapter 8 CRC fields | `test_tx_crc_payloads` |

Names without a directory are modules under `tests35/`. The full gate is
`sh verify.sh`; `USB_PHY_EXHAUSTIVE=1` expands supported phase/rate matrices.
Timing is measured from emitted GPIO events and physical input-wave boundaries,
not from a handler-return timestamp or equality with an earlier implementation.

## Signal oracle scope

`test_tx_digital` independently decodes emitted NRZI and stuffed symbols,
including a stuffed zero after the final data bit. An exhaustive byte/run
certificate connects actual opcodes to the finite edge graph used to check
the upstream total source-jitter limits of 95/150 ns. Section 7.1.15.1 permits
trading driver jitter against clock accuracy while meeting those totals;
the downstream-facing 25/14 ns limits are not substituted for this device.

`test_rx_jitter_spec` checks actual receive effects under 28 signed/rotated
edge patterns reaching the receiver's 75/45 ns next/paired limits. Source
frequency error consumes the same input budget; it is not added a second
time. The patterns are useful extrema, not an exhaustive proof over every
arbitrary jitter history. The test also applies a conservative response gate
using the smaller of host bit period and the certified 85/8-clock unstuffed
response cadence. This is a stricter engineering check across timing-reference
interpretations; it does not relax the specification's maximum delay.

## Known failures remain mandatory

At the current 1382-byte strict checkpoint, legal dribble is rejected. A scratch
receiver also admitted SETUP DATA with an illegal final zero; that finding is
covered by `test_data_framing`. Its 6185 cases use valid CRC16 base packets and
all 1..7-bit tail patterns across CRC-ending classes, plus truncated CRC fields
and missing CRC bytes. `test_ack_followup` separately catches a completed old
write followed by a lost minimum-gap SETUP. These failures must be fixed;
neither test is an expected-failure waiver.

`test_token_crossover_admission` adds 5454 negative cases. A short possible
GPIO both-low observation inside a fourth token byte must not be mistaken for
EOP after a valid three-byte prefix. This gate passes on the strict receiver
and exposes additional false NAK responses in an unadmitted dribble prototype.

The sole approved exception is omitted incoming DATA CRC16 value validation,
before and after ACK. It does not waive PID, stuffing, byte framing, minimum
packet length, token CRC5, EOP recovery or any timing requirement.

Digital instruction tests do not measure cable propagation, analog thresholds,
pin rise/fall times or oscillator drift. Those need physical measurements;
software tests must not be described as complete electrical USB certification.

The [historical receive comparison](HISTORICAL_USB_RX.md) records which defects
are inherited from official v2.6 / installed compact v3.0 and which appeared
while making the newer receiver stricter. A historical driver's acceptance of
legal dribble does not establish rejection of malformed partial tails.
