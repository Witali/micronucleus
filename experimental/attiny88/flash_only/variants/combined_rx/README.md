# Composed USB receiver

This experiment combines the working receive components while retaining one
copy of the active EP0, Flash command, reply and reset implementations. The
small assembly wrapper selects only a different PHY and its calibrated
token-to-DATA wait. No CRC or decode lookup table is added.

| Component | Source of the behavior retained |
| --- | --- |
| SYNC, NRZI and fractional 16 MHz sampling | The compact/V-USB receive core |
| Mandatory stuffed-symbol checks | The strict Flash-only receiver |
| Complete-byte and permitted final-dribble classification | The scheduled receiver experiment |
| Early byte-boundary EOP observations | The independently tested early1d retime |
| Token PID, exact length, address, endpoint and CRC5 admission | Current Flash-only authorization |
| ACK eligibility, immutable retry and SET_ADDRESS ownership | Current Flash-only EP0 state machine |
| Accepted SETUP shadow and OUT-status retirement after transmitted ACK | The scheduled receiver experiment |
| Source waveform and EOP generation | Current 21-clock SE0 / 11-clock J transmitter |

The selected body is measured at 0x1A00 and advertises the noncanonical 0xFFFF
identity. The host rejects this geometry. This directory does not add a release
profile or a hardware installation path.

```sh
python3 build.py --where variants/combined_rx --boot 0x1a00 --require-fit
python3 verify_receiver.py --exhaustive
```

Run these commands from the Flash-only directory. The verifier executes the
same maintained protocol tests, instruction model and independent signal
fixtures against the selected linked image. It does not relax expectations
for this variant, and returns failure if any group fails. JSON results are
written under build/variants/combined_rx/receiver-verification.json.

The current composed checkpoint is **1518 bytes**, SHA256
`bc4faea264abcd7382f3dca31824fd44536838e71337471db91fbe3d57a9f818`.
It fits in the 24 Flash pages from 0x1A00 to 0x1FFF, with eighteen bytes spare.
The source is 132 bytes smaller than the preceding 1650-byte receiver. It still
exceeds the 1280-byte objective.
At the target placement 0x1B00 it remains 1518 bytes, 238 bytes over capacity;
the builder reports the overflow instead of admitting that geometry.

The PHY saves 104 bytes by sharing corrected-byte storage, dribble classification
and bounded live-J recovery. Ordinary and corrected-byte producers use the same
three-clock history-test tail. ACK retains its earlier captured-J path; token
and DATA dispatch use the common live bus check with an explicit observation
bound. No request, field check or timeout is removed. Shared startup, standard
reply publication and CRC5 finalization contribute another ten bytes of savings.
Reusing the validated OUT token as a protocol-error completion marker saves
another two bytes without changing STALL, reply lifetime or command cancellation.
GET_CONFIGURATION and GET_INTERFACE still return exactly one byte for their
specified wLength=1; other lengths are explicitly unspecified by USB9.4.2/9.4.4.

The independently frozen PHY, with the preceding main source, is 1546 bytes,
SHA256 `8fccb164f4b9e9d753be3c7338118cbc471718d46f5bef84fbfb820491dcaeb1`.
It passes 6185 DATA framing, 11475 physical token-tail/authorization, 5454
overlong-token crossover, 3040 PID-effect, 225 ACK-followup, 2016 receiver-jitter
and 324 token-deadline cases. The preceding 1542-byte composition additionally
passes all 72 ordinary error-recovery cases and the control/Flash/read/TX checks
recorded by the selected-image verifier. Its startup is checked with 1536
poisoned-state/first-packet cases, including the first descriptor's CRC.
Its completed selected-image run passed 32 of 33 groups; its sole failing
group is the EOP matrix below. The 3040 PID-effect and 72 recovery cases also
passed separately on these exact bytes and are now wired into the verifier.
An additional 108 quiet-token and 540 paired-packet deadline-extrema check
passes, including all four dribble phase classes and 2/16/18-bit host gaps.

The preceding 1536-byte composition passes 2231 standard cases, 213248 token-field
cases and 128 atomic address/cache commits, 2304 outgoing CRC payloads, 33 reply
fragments, status/read/reset/shadow checks and 225 minimum-gap exchanges.
Foreground checks at 0x1800 retain the measured 40.6773-clock maximum entry.
Its complete 968-byte descriptor/PHY/acknowledged-write prefix is byte-identical
to the previous 1542-byte image. The preceding 1534-byte image additionally passes
19 status, all 128 negative-marker lifetime, reset, pending-SETUP and 3040 PID
effect checks. The error response is one clock earlier; these changes do not
fix the receive defects below.

Sharing DATA0/DATA1 OUT guards and loading literal handshake PIDs directly saves
another eight bytes. Exact PID, length, direction and persistent STALL checks
remain. Only validated DATA1 retires the read after ACK; DATA0 is acknowledged
without accepting the status again. The unchanged TX stuffing helpers occupy
the existing pre-SE0 jump gap. All 58368 linked dispatch-state comparisons pass,
including full context, Y/Z, caller byte, handshake count and T/I flags. Status,
reply lifetime, TX waveform and minimum-gap write/read tests pass. SETUP ACK is
one clock later, IN NAK/STALL two clocks later, and accepted OUT ACK one/two
clocks earlier. The complete 25200 EOP cases retain the same single failed
waveform, and the 180 aperiodic cases retain the same 30 failing identities.

Sharing three identical receive-tail jumps saves another six bytes. Distinct
even/odd confirmation samples and phase/count adjustments remain. Linked graph
comparison proves all 308 original RX instructions and 99 relative edges keep
their opcodes, control flow and clocks; 46080 tail-state executions agree in
registers, full SREG, SRAM and GPIO observations. The integrated 1526-to-1520
composition independently proves 327 instructions and 105 edges. Framing,
mandatory stuffing, PID, token/crossover, deadlines, 1485 minimum-gap exchanges
and 12096 periodic-jitter cases pass on the isolated sharing change. The full
25200 EOP and 180 aperiodic results preserve their exact inherited failures.

Shared GET_STATUS validation falls through to its reply, saving two more bytes
in the common control code. All guards and USB polls remain. The specified
device/interface paths are faster; endpoint success keeps its timing. The
unsupported endpoint-request path is two clocks later and joins the maintained
foreground sweep. All 4368 foreground exchanges pass across the original and
added isolated sweeps, with the same 40.677328-clock maximum entry. Standard,
reply/state and outgoing CRC checks pass on the exact 1518-byte body.

An additional 6048-case OUT response audit found protocol-error STALL deadline
failures in the preceding composition: 464 of 2016 new-error cases, down from
489 in the 1534-byte parent. The rejected 1524-byte attempt added failures and
was not integrated.

Error retirement now uses the existing post-handshake path. Validated OUT has
closed R2, so its negative R3 marker must be retired before any later receiver
or foreground code runs. The transmitted literal STALL distinguishes error
retirement from an accepted read ACK. Command cancellation and both state stores
finish there; no stale SPM/RUN or old DATA can be released. This begins the
protocol-error response five clocks earlier without changing code size. All
6048 OUT timing cases pass: new STALL is 40.7139..68.2830 clocks and persistent
STALL 38.7139..66.2830. Ordinary read ACK is one clock later and remains in bounds.
All 576 new minimum-gap IN/SETUP followups, 1485 ACK followups, ownership/lifetime,
read/write and TX checks pass on the isolated fix. The full 25200 EOP and 180
aperiodic matrices retain only their inherited receiver failures.

The actual 1518-byte composition independently passes all 6048 OUT timing and
576 STALL-followup cases, 3040 PID effects, 19 status cases, all 15 SETUP service
callers and 864 response waves, completion lifetime and context restoration.
Its 739 linked instructions all have explicit AVR cycle classifications.

The 1534-byte parent also completed an exhaustive selected-image run: 35 of 37
groups passed, with only aperiodic reception and the EOP matrix failing. The
new OUT response and STALL-followup gates add two required groups, making 39;
do not interpret the older report as a complete current-image verification.

Qualification remains open. In the unchanged 9072 legal DATA-tail cases plus
16128 certified-jitter cases, the PHY still misses one legal short EOP:
DATA0 with eight 0x15 payload bytes, two final dribble bits, host rate 1500750,
SE0 width 10.72 clocks, J/K edge offsets -0.55/+0.55 clocks, entry 24.75 clocks.
The report records both missing decode and missing response for that one case.
All other cases in that sweep pass, with response times 39.6417..67.2191 clocks.
The conservative recovered-crossover reception path also needs qualification.
These findings remain mandatory; this is an experiment, not a release.

Legal aperiodic SYNC/data jitter also exposes inherited receive failures outside
that periodic matrix. The maintained aperiodic regression preserves those valid
waveforms and rejects proposed SYNC changes that add new failures. Periodic
jitter corners alone do not establish arbitrary-history receive correctness.

Incoming DATA CRC16 value checking remains the sole approved exception.
Neither that exception nor correct reception of dribble permits malformed
stuffing, arbitrary partial tails or missing packet bytes. See the
[historical comparison](../../docs/HISTORICAL_USB_RX.md) and
[requirements matrix](../../docs/USB_REQUIREMENTS.md).
