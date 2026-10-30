# USB specification and executable requirements

Reference: [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification),
Revision 2.0, full-/low-speed clauses. Tests execute linked AVR instructions;
their wire encoders and CRC oracles are independent of the firmware.
Firmware identity or a smaller binary alone is never an admission criterion.

| Required behavior | Specification basis | Executable checks |
| --- | --- | --- |
| NRZI and eight-symbol low-speed SYNC | Sections 7.1.8 and 7.1.10 | `test_usb_rx_waveforms`, `test_ep0_failed_sync`, `test_tx_digital` |
| Stuffed zero after six ones, including before EOP; reject seven consecutive ones | Sections 7.1.9/7.1.9.1 | `test_usb_rx_waveforms`, `test_tx_digital` |
| Accept only permitted all-one final dribble; reject arbitrary fractional DATA tails | Section 7.1.9.1, Figure 7-33 | `test_data_framing`, `test_usb_rx_waveforms`, `test_rx_eop_matrix` |
| SETUP still contains eight payload bytes and both CRC bytes; truncated fields cannot manufacture a byte | Chapter 8 packet/control formats | `test_data_framing`, `test_setup_pending_marker`, `test_rx_context_restore` |
| Supported PIDs have the correct complement; foreign address/endpoint and bad token CRC5 cannot authorize a transaction | Chapter 8 PID, address, endpoint and CRC fields | `test_token_crc5`, `test_pid_admission`, `test_usb_rx_waveforms` |
| Source EOP SE0 lasts 1.25..1.50 us; receiver accepts 670 ns and ignores differential-crossover SE0 up to 210 ns | Table 7-10, Section 7.1.13.2 | `test_tx_eop_counter`, `test_usb_rx_waveforms`, `test_rx_eop_matrix`, `test_usb_crossover` |
| A crossover transient cannot authorize a four-byte IN token as a three-byte token plus dribble | Section 7.1.4.1, Table 7-10, Chapter 8 token format | `test_token_crossover_admission` |
| Token tails obey the wire dribble rule independently of internal decoder phase tags | Section 7.1.9.1, Chapter 8 token fields | `test_token_framing_wire` |
| Device data rate is 1.4775..1.5225 Mbit/s; high-speed-capable host low-speed rate is 1.49925..1.50075 Mbit/s | Section 7.1.11, Table 7-10 | Host-rate/phase matrices, `test_tx_digital`, `test_rx_jitter_spec` |
| Driver jitter, clock accuracy and permitted total jitter are assessed with the correct upstream/downstream direction | Section 7.1.15.1, Table 7-5, Table 7-10 | `test_tx_digital`, `test_rx_jitter_spec`, `test_rx_aperiodic`; opcode identity alone is insufficient |
| Response begins after at least two response bit periods and before the applicable 6.5-bit connector bound | Section 7.1.18.1 | Physical recovery-J to first-K timing in token and DATA response matrices |
| Persistent and newly generated OUT protocol STALL obey the same physical response deadline without releasing pending writes | Sections 7.1.18.1 and 8.5.3.4 | `test_out_response_timing` |
| A following transaction at the physical two-bit gap must be received intact | Section 7.1.18.1 | `test_ack_followup`, `test_sequential_wire` |
| An ordinary malformed packet cancels authorization and permits a separate valid SETUP after its real EOP and legal host gap | Sections 7.1.10, 7.1.18.1 and 7.1.19.1, Chapter 8 error handling | `test_rx_resync` |
| Foreground delay cannot corrupt an IN token or its complete reply; later observed entries retain jitter tolerance | Sections 7.1.11, 7.1.15.1 and 7.1.18.1 | `test_ep0_polling`, `test_rx_late_entry` |
| ACK/token response eligibility expires no earlier than 16 and before 18 bit periods | Section 7.1.19.1 | `test_ep0_ack_timeout`, `test_ep0_token_timeout`, `test_dribble_deadlines` |
| DATA/PID remain immutable until eligible ACK or control-status completion; repeats do not duplicate a write | Chapter 8 transaction/retry rules | `test_ack_regression`, `test_ep0_read_completion`, `test_sequential_wire` |
| New SETUP and reset cancel old transfer ownership; no stale erase/program/RUN is released | Chapter 8 control transfers, Chapter 9 reset states | `test_setup_pending_marker`, `test_ep0_shadow`, `test_ep0_reset`, `test_nvm_state` |
| Standard requests, recipients, zero-length direction, SET_ADDRESS status sequencing and protocol STALL are correct | Chapter 9, Sections 9.3.1 and 9.4 | `tests34/test_standard.py`, `test_ep0_standard`, `test_ep0_zero_direction`, `test_ep0_status` |
| Control reads finish correctly at exact/short/zero lengths and required terminating ZLPs | Chapter 8 control transfers | `test_ep0_reply_fragments`, `test_ep0_read_completion` |
| Outgoing DATA CRC16 is correct | Chapter 8 CRC fields | `test_tx_crc_payloads` |

Names without a directory are modules under `tests35/`. The full gate is
`sh verify.sh`; `USB_PHY_EXHAUSTIVE=1` expands supported phase/rate matrices.
Timing is measured from emitted GPIO events and physical input-wave boundaries,
not from a handler-return timestamp or equality with an earlier implementation.

## Shared small standard replies

USB2.0 sections 9.4.2 and 9.4.4 specify wLength=1 for GET_CONFIGURATION and
GET_INTERFACE and explicitly leave other lengths unspecified (printed
pages 253/254). GET_INTERFACE shares GET_STATUS's two-zero source. GET_CONFIGURATION keeps
its configuration-value pointer and shares the same two-byte availability
and publication entry. The existing wLength limiter still returns exactly
one byte for each specified request, or two for a specified GET_STATUS.
Recipient, interface-existence, configuration and descriptor checks remain.
Positive fixtures use the specified lengths; malformed-length tests still
require bounded read-only handling and unchanged command/configuration/address
state. This uses an explicit specification allowance and adds no USB waiver.

## Explicitly permitted simplifications

Minimize the implementation using allowances that apply to this low-speed,
single-interface, default-setting, endpoint-zero-only device. For each proposed
omission, record the specification clause, its applicability and the smaller
implementation before making it a test expectation. Do not require a particular
reply for inputs whose behavior the specification explicitly leaves unspecified;
keep bounded execution and memory/command safety for those inputs.

| Specification allowance | Minimal implementation retained |
| --- | --- |
| Sections 9.4.2 and 9.4.4 leave other GET_CONFIGURATION/GET_INTERFACE lengths unspecified. | Share GET_STATUS's two-byte availability and the existing length limiter; the specified one-byte requests still return one byte. This saves four code bytes. |
| Section 9.4.8 makes SET_DESCRIPTOR optional. | No mutable-descriptor handler; the ordinary unsupported-request STALL handles it. |
| Section 9.4.10 permits STALL for SET_INTERFACE when only the default setting exists. | No alternate-setting state or SET_INTERFACE success handler. GET_INTERFACE still reports setting zero. |
| Section 9.4.5 says the Halt feature is neither required nor recommended for the Default Control Pipe; section 8.5.3.4 distinguishes functional from protocol stall. | No persistent EP0 Halt feature or set/clear-Halt machinery. Required protocol STALL lasts until the next SETUP. |
| Section 8.5.3.1 allows any received packet length as a control-read status inquiry. | Accept a completely framed status packet without a zero-payload-length check. Both CRC-byte positions and DATA-toggle ownership remain required. |
| Section 9.4.6 leaves SET_ADDRESS values above127 and nonzero wIndex/wLength unspecified. Section 9.4.7 similarly leaves nonzero wIndex/wLength/upper wValue unspecified. | Do not add request-shape checks for those undefined cases. Keep valid address activation after its status ACK and configuration-value validation. |
| Section 7.1.15.1 allows trading source-driver jitter against clock accuracy within total upstream limits. | Keep the compact fractional TX schedule when its independently measured total error meets the applicable limits; do not impose the tighter downstream-driver limits on this device. |

Except for the four-byte shared-reply reduction, these are existing omissions
or choices, not additional measured savings. Permanent EEPROM commands, strings,
alternate configurations and nonzero endpoints are also absent from this target.
The explicit incoming DATA CRC16 waiver below is a separate project deviation,
not a claim that this check is optional for a USB control endpoint.

## Signal oracle scope

`test_dribble_deadlines` preserves 108 quiet-token and 540 paired-packet probes
at the historical timeout extrema. Legal final-one dribble, three host rates,
short/full EOPs and signed skew exercise four ending classes. The final PIN
observation must lie in the rate-specific 16..18-bit window. Actual 2/16/18-bit
token-to-DATA gaps also check complete payload, SETUP shadow, cursor/status
commit, exactly one ACK and rejection without state changes. Late foreground
reentry advances the same CPU clock phase instead of resetting device state.
The strict receiver still fails required dribble cases; they are not waived.

`test_pid_admission` checks all 256 PID bytes in ACK, token, SETUP DATA and OUT
DATA shapes, then exercises selected classes at host-rate, EOP-width and entry
corners: 3040 cases. It observes responses, accepted SETUP, cursor/address
effects, actual token-wait I/O, live CRC-register preservation and stack balance.
A visit to a generic dispatcher before exact validation never counts as
acceptance. This finite matrix does not claim all possible packet histories.

The [AVR model audit](AVR_MODEL.md) checks explicit instruction-cycle classes,
conditional/skip timing, arithmetic flags and the distinction between GPIO
access phase and instruction completion. Unsupported timing cannot silently
default to one clock.

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

`test_rx_aperiodic` independently certifies 180 ordinary DATA0 waveforms with
rounded, nonperiodic SYNC/data edge correlations, both short/long EOP and finite
fractional-entry windows. It consumes frequency error from the same 75/45 ns
interval budget. PID/payload/count, accepted SETUP, one ACK, response timing,
caller/stack and released pins remain required; numeric CRC16 storage is the
sole exception. The 1536-byte composed receiver fails 30 cases inherited from
the preceding 1542-byte image: some never observe SE0, others reject framing
after observing it. Two small proposed SYNC corrections add failures and were
rejected. These are mandatory regressions, not expected-failure waivers.

## Known failures remain mandatory

`test_out_response_timing` adds 6048 OUT packet corners: both DATA toggles,
empty/eight-byte payloads, all legal final-one tails, slow/fast host, short/long
EOP, signed skew, entry phase and existing/new STALL state. It checks the actual
STALL PID/count, command cancellation, completion marker, cursor, caller/stack,
released pins and physical recovery-J-to-first-K time. The 1526-byte composed
checkpoint passes all 4032 persistent-STALL cases but fails the deadline in 464
of 2016 newly generated protocol-error STALL cases (maximum 73.2830 clocks).
The 1534-byte parent had 489 such failures. The strict test rejects all remaining
errors; these are not unspecified-request allowances or expected failures.

At the strict checkpoint, legal dribble is rejected. A scratch
receiver also admitted SETUP DATA with an illegal final zero; that finding is
covered by `test_data_framing`. Its 6185 cases use valid CRC16 base packets and
all 1..7-bit tail patterns across CRC-ending classes, plus truncated CRC fields
and missing CRC bytes. `test_ack_followup` separately catches a completed old
write followed by a lost minimum-gap SETUP. These failures must be fixed;
neither test is an expected-failure waiver.

`test_rx_eop_matrix` combines 9,072 legal DATA-tail cases with 16,128
certified-jitter cases. It checks actual PID/payload bytes, complete byte count,
caller restoration and recovery-J-to-response timing. Complete-frame observation
includes the private DATA exit used by a faster dispatch; authorization and
live-J checks remain independently required. Incoming numeric CRC storage is
excluded only under the existing DATA CRC16 waiver. A shared decoder defect
cannot be cleared by an executor-parity comparison.

`test_rx_resync` checks 72 ordinary error-recovery cases through actual foreground
polling: an existing bad-stuff DATA or illegal ACK zero-tail fixture, its real
EOP, and a separate valid SETUP. The host waits 18 bits after DATA and two bits
after ACK. The strict checkpoint loses the next SETUP in 12 short-EOP ACK-tail
cases while preserving command/cursor/address/reply state. The reviewed
1,654-byte receiver passes all 72. This is bounded recovery evidence, not a proof
of quarantine against arbitrary malformed streams or arbitrary recovery gaps.

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
