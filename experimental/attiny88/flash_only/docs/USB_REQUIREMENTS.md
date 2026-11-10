# USB specification and executable requirements

Reference: [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification),
Revision 2.0, full-/low-speed clauses. Tests execute linked AVR instructions;
their wire encoders and CRC oracles are independent of the firmware.
Firmware identity or a smaller binary alone is never an admission criterion.

The [2026-11-01 audit](USB_AUDIT_2026_11_01.md) records the 1788-byte checkpoint.
The [November 3 record](USB_SIZE_2026_11_03.md) tracks its 1768-byte
composed body at 0x1900 and its selected checks. The [November 9 receive/EOP
record](USB_RX_EOP_2026_11_09.md) tracks the subsequent 1766-byte body.
The verification default is the 1934-byte separate-ACK composition at 0x1800;
the smaller combined image remains an explicit size/behavior control.
Named older checkpoints below retain their historical findings;
default standalone `source/` tests still target the legacy strict fixture.
`sh verify.sh` checks the corrected selection and separate legacy fixtures.
The newly witnessed asymmetric 210 ns regressions remain mandatory and red on
the 1788-byte checkpoint; see the current audit rather than interpreting its
earlier 54-group pass as complete qualification.

| Required behavior | Specification basis | Executable checks |
| --- | --- | --- |
| NRZI and eight-symbol low-speed SYNC, including legal single-ended crossover observations during acquisition | Sections 7.1.4.1, 7.1.8 and 7.1.10 | `test_usb_rx_waveforms`, `test_ep0_failed_sync`, `test_rx_sync_crossover`, `test_tx_digital` |
| Stuffed zero after six ones, including before EOP; reject seven consecutive ones | Sections 7.1.9/7.1.9.1 | `test_usb_rx_waveforms`, `test_tx_digital`, `test_rx_terminal_bounds` |
| Accept only permitted all-one final dribble; reject arbitrary fractional DATA tails | Section 7.1.9.1, Figure 7-33 | `test_data_framing`, `test_usb_rx_waveforms`, `test_rx_eop_matrix`, `test_rx_terminal_crc` |
| Accept noninteger final-symbol stretching on ACK and DATA with the minimum 670 ns received EOP | Sections 7.1.9.1 and 7.1.13.2 | `test_rx_fractional_dribble`, `test_rx_fractional_data` |
| SETUP still contains eight payload bytes and both CRC bytes; truncated fields cannot manufacture a byte | Chapter 8 packet/control formats | `test_data_framing`, `test_setup_pending_marker`, `test_rx_context_restore` |
| Supported PIDs have the correct complement; foreign address/endpoint and bad token CRC5 cannot authorize a transaction | Chapter 8 PID, address, endpoint and CRC fields | `test_token_crc5`, `test_pid_admission`, `test_usb_rx_waveforms` |
| Source EOP SE0 lasts 1.25..1.50 us; receiver accepts 670 ns and ignores differential-crossover SE0 up to 210 ns | Table 7-10, Section 7.1.13.2 | `test_tx_eop_counter`, `test_usb_rx_waveforms`, `test_rx_eop_matrix`, `test_usb_crossover` |
| A crossover transient cannot authorize a four-byte IN token as a three-byte token plus dribble | Section 7.1.4.1, Table 7-10, Chapter 8 token format | `test_token_crossover_admission` |
| Separate adjacent transients cannot impersonate one EOP and authorize transmission during the host packet | Sections 7.1.4.1, 7.1.13 and Chapter 8 token framing | `test_token_crossover_admission`: 3456 injected cases and 3456 pristine controls, including all 64 fourth-byte tails with two initial zero bits |
| Source-valid differential EOP timing remains receivable when an allowed single-ended input threshold lengthens the observed PIN SE0 | Sections 7.1.2.1 and 7.1.13.2.1, Table 7-10, Figure 7-50 | `test_rx_eop_thresholds`: 24 cases with explicit monotonic line curves and response timing measured from differential recovery J |
| A plausible centered 150 ns single-ended crossover preserves reception, not only silence before the real EOP | Sections 7.1.2.1 and 7.1.4.1, Table 7-10 | `test_rx_crossover_legal` |
| Monotonic matched 300 ns edges may produce asymmetric 210 ns single-ended crossover intervals without shifting differential jitter | Sections 7.1.2.1, 7.1.4.1 and 7.1.13.1.1 | `test_rx_crossover_asymmetric`, `test_rx_crossover_payloads` |
| Legal differential crossings can also produce transient both-high single-ended observations at a permitted lower threshold | Sections 7.1.2.1 and 7.1.4.1 | `test_rx_crossover_se1` |
| ACK PID and ownership survive legal single/repeated SE0/SE1 crossing observations | Sections 7.1.4.1, 8.3.1 and 8.4.5 | `test_ack_crossover_legal` |
| One or two actual zero bits after ACK cannot be mistaken for all-one dribble, including when crossover observations hide the opposite interval | Sections 7.1.9.1 and 8.4.5 | `test_ack_tail_crossover` |
| A PID shorter than eight bits, including SYNC followed directly by EOP, cannot retire an eligible ACK transaction | Sections 8.3.1 and 8.4.5 | `test_ack_pid_prefix`, `test_ack_empty_pid` |
| A prematurely terminated ACK PID must be discarded soon enough to receive the next minimum-gap SETUP intact | Sections 7.1.18.1 and 8.4.5, Chapter 8 error handling | `test_ack_prefix_followup` |
| Token tails obey the wire dribble rule independently of internal decoder phase tags | Section 7.1.9.1, Chapter 8 token fields | `test_token_framing_wire` |
| A permitted nonempty read-status DATA packet cannot produce ACK at an interior byte boundary when two adjacent crossovers resemble SE0 | Sections 7.1.4.1, 7.1.13.2 and 8.5.3.1 | `test_status_boundary_crossover`: valid CRC16, 54 injected cases and 54 pristine controls, real EOP-to-response timing |
| Device data rate is 1.4775..1.5225 Mbit/s; high-speed-capable host low-speed rate is 1.49925..1.50075 Mbit/s | Section 7.1.11, Table 7-10 | Host-rate/phase matrices, `test_tx_digital`, `test_rx_jitter_spec` |
| Driver jitter, clock accuracy and permitted total jitter are assessed with the correct upstream/downstream direction | Section 7.1.15.1, Table 7-5, Table 7-10 | `test_tx_digital`, `test_rx_jitter_spec`, `test_rx_aperiodic`; opcode identity alone is insufficient |
| Response begins after at least two response bit periods and before the applicable 6.5-bit connector bound | Section 7.1.18.1 | Physical recovery-J to first-K timing in token and DATA response matrices |
| Persistent and newly generated OUT protocol STALL obey the same physical response deadline without releasing pending writes | Sections 7.1.18.1 and 8.5.3.4 | `test_out_response_timing` |
| The next minimum-gap IN sees STALL and a replacement SETUP recovers the pipe after error retirement; canceled work cannot run | Sections 7.1.18.1 and 8.5.3.4 | `test_stall_followup` |
| A following transaction at the physical two-bit gap must be received intact | Section 7.1.18.1 | `test_ack_followup`, `test_sequential_wire` |
| An ordinary malformed packet cancels authorization and permits a separate valid SETUP after its real EOP and legal host gap | Sections 7.1.10, 7.1.18.1 and 7.1.19.1, Chapter 8 error handling | `test_rx_resync` |
| Foreground delay cannot corrupt an IN token or its complete reply; later observed entries retain jitter tolerance | Sections 7.1.11, 7.1.15.1 and 7.1.18.1 | `test_ep0_polling`, `test_rx_late_entry` |
| ACK/token response eligibility expires no earlier than 16 and before 18 bit periods | Section 7.1.19.1 | `test_ep0_ack_timeout`, `test_ep0_token_timeout`, `test_dribble_deadlines` |
| DATA/PID remain immutable until eligible ACK or control-status completion; repeats do not duplicate a write | Chapter 8 transaction/retry rules | `test_ack_regression`, `test_ep0_read_completion`, `test_sequential_wire` |
| New SETUP and reset cancel old transfer ownership; no stale erase/program/RUN is released | Chapter 8 control transfers, Chapter 9 reset states | `test_setup_pending_marker`, `test_ep0_shadow`, `test_ep0_reset`, `test_nvm_state` |
| Standard requests, recipients, zero-length direction, SET_ADDRESS status sequencing and protocol STALL are correct | Chapter 9, Sections 9.3.1 and 9.4 | `tests34/test_standard.py`, `test_ep0_standard`, `test_ep0_zero_direction`, `test_ep0_status`, `test_set_address_ownership` |
| Control reads finish correctly at exact/short/zero lengths and required terminating ZLPs | Chapter 8 control transfers | `test_ep0_reply_fragments`, `test_ep0_read_completion` |
| Outgoing DATA CRC16 is correct | Chapter 8 CRC fields | `test_tx_crc_payloads` |

Names without a directory are modules under `tests35/`. The full gate is
`sh verify.sh`; `USB_PHY_EXHAUSTIVE=1` expands supported phase/rate matrices.
Timing is measured from emitted GPIO events and physical input-wave boundaries,
not from a handler-return timestamp or equality with an earlier implementation.

`verify_receiver.py --exhaustive` selects one linked no-LED image for all maintained groups,
including transmitted-EOP measurement and 512 explicit-artifact poisoned-page
guards. The standalone NVM test still builds three independent LED modes for
1536 cases; selecting one image must not substitute it for those other modes.
Host packing, failure/readback behavior, offline EEPROM planning, historical
opcode/reference checks and canonical release generation remain separate checks.
The strict-source recognized release roundtrip does not qualify an unknown-profile
composed image at another address.

## Change and verification workflow

Correct USB behavior takes priority over firmware size. Repair the remaining
mandatory receive, framing, synchronization and transaction failures before
resuming size optimization. A larger private reference implementation is useful
when it establishes correct behavior; a passing symbol component is not a
qualified complete receiver.

For each substantial firmware change, preserve the linked ELF, unpadded body,
symbols, source revision, toolchain and body/ELF hashes. Run the complete
`python3 verify_receiver.py --exhaustive` gate against that resulting image, plus
any separate affected host, geometry or release checks. Retain failure details
and actual GPIO sample/drive times. During repair, report remaining mandatory
failures explicitly; do not count them as passes or weaken the independent
waveform, payload, recovery, timing or ownership oracles.

Once that gate passes, retain its image and report as the correctness baseline.
After every substantial size optimization, rerun the same complete gate on the
new linked image before accepting the optimization. Compare size at the same
placement and configuration; separately report any changed boot boundary or
profile. Source-line count, fewer branches, successful assembly or equality
with an older defective implementation do not establish correctness or savings.
Keep the documented numeric incoming-DATA-CRC16 waiver unchanged.

These instruction/GPIO checks cover their stated finite signal and transaction
matrices. They do not replace physical-board, analog or USB certification work.

The DATA fractional-ending gate adds 9720 complete SETUP-DATA exchanges:
six payload patterns, three host rates, three signed jitter patterns, fifteen
sixteenth-bit extensions, two EOP widths and six entries. Half use 670 ns SE0.
It requires the complete PID/payload and both CRC positions, exactly one ACK,
unchanged protected state and the physical ACK deadline. This covers an EOP
falling between a receiver's eleven-clock FIRST observations, which the
separate ACK-only fractional test cannot qualify for a DATA decoder.

The EOP matrix retains its 1344 NAK/STALL waveform cases as forbidden host
handshakes. USB2.0 section 8.4.5, printed pages 206/207, prohibits the host from
issuing either PID. The device need not publish their decoded buffers. These
cases instead seed an eligible IN reply and pending SET_ADDRESS, then require
silence, no SPM, unchanged cached reply/address/cursor and protected registers,
balanced stack and released GPIO. All valid-host ACK, token and DATA cases
still require complete decoding and their original physical timing checks.
This corrects a fixture expectation; it adds no firmware or protocol waiver.

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
| Section 9.4.6 leaves SET_ADDRESS values above127 and nonzero wIndex/wLength unspecified. Section 9.4.7 similarly leaves nonzero wIndex/wLength/upper wValue unspecified. | Do not add request-shape checks for those undefined cases. Retain configuration-value validation. Our post-ACK address activation is a chosen policy; section 9.2.6.3 also permits completion on status transmission. |
| Section 7.1.15.1 allows trading source-driver jitter against clock accuracy within total upstream limits. | Keep the compact fractional TX schedule when its independently measured total error meets the applicable limits; do not impose the tighter downstream-driver limits on this device. |

Except for the four-byte shared-reply reduction, these are existing omissions
or choices, not additional measured savings. Permanent EEPROM commands, strings,
alternate configurations and nonzero endpoints are also absent from this target.
The explicit incoming DATA CRC16 waiver below is a separate project deviation,
not a claim that this check is optional for a USB control endpoint.

`test_set_address_ownership` additionally enforces the project's post-ACK
publication policy. USB section 9.2.6.3 permits status transmission or ACK as
SET_ADDRESS completion, so that stricter oracle must not be used to declare
every send-time implementation invalid. Stale requests, early activation
before status and failed control-transfer retry are separate questions.

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

## Historical findings remain mandatory regressions

`test_out_response_timing` adds 6048 OUT packet corners: both DATA toggles,
empty/eight-byte payloads, all legal final-one tails, slow/fast host, short/long
EOP, signed skew, entry phase and existing/new STALL state. It checks the actual
STALL PID/count, command cancellation, completion marker, cursor, caller/stack,
released pins and physical recovery-J-to-first-K time. The 1526-byte composed
checkpoint passed all 4032 persistent-STALL cases but failed the deadline in 464
of 2016 newly generated protocol-error STALL cases (maximum 73.2830 clocks).
The 1534-byte parent had 489 such failures. Deferring error retirement to the
post-handshake owner fixes all of them at zero byte cost: all 6048 cases now
pass, with new-error responses at 40.7139..68.2830 clocks. This is a timing fix,
not an unspecified-request allowance or an expected-failure exception.

`test_stall_followup` adds 576 physical two-bit-gap error-STALL followups across
queued erase/write/RUN states, both DATA toggles, standard/vendor write flags,
host rates and entry phases. Next-IN retains STALL; replacement SETUP accepts
the new request. It requires retirement before later receive/foreground code,
caller/stack restoration, unchanged cursor and no stale NVM work. A next physical
SYNC may already have begun while retirement runs; intact reception is tested.

At the strict checkpoint, legal dribble is rejected. A scratch
receiver also admitted SETUP DATA with an illegal final zero; that finding is
covered by `test_data_framing`. Its 6185 cases use valid CRC16 base packets and
all 1..7-bit tail patterns across CRC-ending classes, plus truncated CRC fields
and missing CRC bytes. `test_ack_followup` separately catches a completed old
write followed by a lost minimum-gap SETUP. These failures must be fixed;
neither test is an expected-failure waiver.

The independent Pass40-derived `test_rx_legal_dribble` adds 720 cases, or 5760
with `USB_PHY_EXHAUSTIVE=1`: eligible ACK final tails, valid-CRC SETUP tails,
seven-one rejection, exact publication/ACK ownership, GPIO release and physical
turnaround. Its encoder is independent of the older waveform builders. The
[import record](PASS40_IMPORT.md) distinguishes failures in the small archived
receiver from the composed receiver's results.

`test_rx_crossover_jitter` combines the existing centered 150 ns monotonic
transition witness with 792 legal jitter/rate/entry cases. The next- and paired-
transition budgets, including source frequency error, are independently checked
before inserting the GPIO threshold excursion. These cases are required positive
reception gates, unlike an uncertified endpoint-placed stress report. The
1498-byte integration baseline discards 82 of them; zero-jitter reception alone
does not close the combined-tolerance finding.

`test_rx_crossover_corners` extends this to all 28 certified edge templates,
three host rates, 22 data transitions and six entries: 11088 single-excursion
cases plus 504 cases with all 22 data crossings affected together. Repeated
excursions check whether a resumed stuffer accumulates phase error. Its strict
oracle checks complete reception, publication, response timing and caller state;
an independent test-subset success does not admit an otherwise failing image.

`test_rx_crossover_wide` repeats all four positive crossover families at 210 ns
for 12780 cases. Its explicit piecewise monotonic voltage witness has matched
300 ns 10..90% rise/fall times, a 1.3 V differential crossing and VIH=2 V.
Consequently a centered 210 ns excursion is not dismissed merely because the
earlier constant-slope witness would exceed the rise-time limit. Endpoint-placed
stress remains separate without its own witness. The 1494-byte baseline fails
28 of the 396 ordinary, zero-jitter wide cases; a pass at 150 ns is insufficient.

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

The older 3564-case GPIO crossover stress report includes 714 exact-wire
mismatches on the 1518-byte image: 700 discarded packets and 14 differences
confined to numeric CRC16 storage. Only the latter are covered by the existing
waiver. The endpoint-placed 210 ns stress observations do not each have an
independently established analog realization, so that total is not a count of
proved physically compliant failures.

`test_rx_crossover_legal` instead preserves 396 centered 150 ns cases with zero
injected jitter. Its documented monotonic ramp witness crosses differentially
at the center, at 1.3 V, with equal 282.857 ns rise/fall times; a 2.0 V
single-ended threshold gives the 150 ns both-low interval. The 1518-byte image
discards 14 cases at mandatory stuffed transitions. All 382 accepted cases
preserve PID/payload/count, SETUP ownership, caller/stack and pin release.
Rejection prevents a false EOP but does not establish required crossover receive
tolerance. This required regression remains strict while firmware repair is open.

The sole approved exception is omitted incoming DATA CRC16 value validation,
before and after ACK. It does not waive PID, stuffing, byte framing, minimum
packet length, token CRC5, EOP recovery or any timing requirement.

The November 10 adjacent-pulse expansion tests all 64 fourth-byte values
whose first two wire bits are zero: 3456 injected packets and 3456 pristine
controls, alongside the unchanged 5454 single-pulse cases. The maintained
1934-byte ACK composition fails 720 injected cases; all pristine and single-pulse
controls pass. The earlier 54-case adjacent matrix exposed only 12 cases and
is retained solely in frozen historical reports. A cached recovery-J guard
reduces that expanded count to 384 but remains unsafe and is not selected.

The mandatory gate now has 69 groups, including `test_pcif_clear`,
`test_rx_eop_thresholds` and `test_status_boundary_crossover`. The last exposes an inherited short-DATA
premature-drive failure in 12 of 108 cases; the November 10 transfer record
distinguishes this expanded gate from the earlier frozen 67-group comparisons.
That test uses explicit monotonic matched 300 ns curves, a 1.3 V differential
crossover and a 2.0 V single-ended threshold. The source SE0 interval is
1.29 or 1.50 us; the corresponding PIN interval is 1.50 or 1.71 us.
All 24 cases pass on the maintained composition. Removing the bounded
SE0-to-J wait loses two valid responses, so clean digital observations alone
cannot justify that size reduction. These model certificates are bounded
evidence and do not replace electrical measurement on a board.

Digital instruction tests do not measure cable propagation, analog thresholds,
pin rise/fall times or oscillator drift. Those need physical measurements;
software tests must not be described as complete electrical USB certification.

The [historical receive comparison](HISTORICAL_USB_RX.md) records which defects
are inherited from official v2.6 / installed compact v3.0 and which appeared
while making the newer receiver stricter. A historical driver's acceptance of
legal dribble does not establish rejection of malformed partial tails.
