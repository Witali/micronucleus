# Compact USB repair transfer, November 10

The target is a complete no-LED ATtiny88 loader of 1280 bytes. A standalone
receiver count does not meet that target. These changes keep the shared EP0,
TX, Flash and application-layout owners; no table, release profile or hardware
installation is introduced. USB 2.0 chapters 7, 8 and 9 remain the reference, with only
the existing numeric incoming DATA CRC16 validation/storage exception.

## Atomic SYNC confirmation

The subsequent [conditional SYNC qualification](COMPACT_SYNC_QUALIFICATION_2026_11_10.md)
is the latest 1960-byte checkpoint. It repairs another 24 SYNC contexts with
the complete 69-group comparison and separately records newly covered SE1/SYNC.
The sections below retain the earlier 1934/1946-byte transfer evidence.

The ACK composition now confirms full K from one masked PIN capture rather
than testing D-minus alone. Success costs five clocks instead of three; remove
the later two-clock delay to preserve the first PID sample. Non-K retry still
costs eight clocks. R16 is scratch. The non-ACK base variant remains byte-identical.

| Complete image at 0x1800 | Bytes | SHA256 |
| --- | ---: | --- |
| Before | 1934 | `03393220e9d0b5da9c6c554d0f301b3ac1abe017fe2f00d59a61da7cfca77e4c` |
| Atomic confirmation | 1934 | `4f0b3ca3c10f2e68d9b730a99f44bf4653b14e11b48870ca178d346aa5541497` |

Two independently frozen exhaustive runs each executed all 67 groups and
verified unchanged inputs before/after each group. Both exited 1 with 62/67
passing. SYNC crossover failures fell 144→59: 85 repaired, zero new failing
contexts. The other mandatory failures are unchanged: token admission 720,
asymmetric DATA 120, SE1 DATA 63 and payload crossover 69. Those are still failures.
Shared failing cases also retain exactly the same recorded observations.
All 143 independently frozen model, test, fixture and source inputs match.

The [context-comparison record](compact_sync_atomic_2026_11_10.json) pins both
bodies, report digests and failure sets. The portable comparison tool checks
completed immutable runs, corpus equality, new failing groups and actual input
contexts; its success is regression evidence, not USB qualification:

```sh
python3 tools/compare_compact_usb_failures.py --baseline baseline-run --candidate candidate-run --output build/comparison.json
```

The full gate remains strict:

```sh
python3 verify_receiver.py --source variants/ack_terminal --boot 0x1800 --exhaustive
```

The remaining SYNC phase error can start when the initial D-minus poll sees a
legal crossover SE0 before real K. Correct confirmation alone cannot recover
that early phase. A larger raw-phase/double-K experiment closes the directed
SYNC matrix but adds DATA failures and misses 12 OUT response deadlines; it is
rejected. Aggregate failure-count improvements cannot justify those regressions.

## Reuse the terminal receiver for tokens

The terminal-token checkpoint is **1946 bytes at 0x1800**, SHA256
`ade87a8d622f0c52eaaabbd53caf375571fb20fd8dd137247ac6b1f87d787e3a`.
This is 12 bytes above the original control and 666 bytes above the target.
The non-ACK 1766-byte control retains its original bytes.

R23 holds the final-byte pointer until EOF replaces it with the actual count.
Normal reception defaults to a three-byte token; typed PID bit 1 selects
eleven bytes for DATA using slots where a six-one history is impossible.
The normal first-PID/next-even sampling clocks are unchanged. Three existing
bound checks use this pointer rather than a fixed maximum. The existing
terminal receiver consequently rejects an overlong token instead of confusing
two separate transition excursions with EOP after its valid prefix.

Publication computes 85-N for actual count N. A valid endpoint-zero token's
third byte starts with three endpoint zeros and has only five CRC5 bits after
them; that byte cannot require stuffing. Its raw final value is therefore
exact. Invalid endpoint bits remain checked, and incoming token CRC5 has no
waiver. A known-not-taken T branch pays the extra normalization clock.

Every accepted SETUP/OUT token now has residual zero. Remove the obsolete
FF/55/AA phase paths and use count 29 instead of 28: one ANDI clock plus an
additional five-clock PCIF poll replaces six padding clocks. After that useful
poll, all old quiet poll times and expiry are identical. Selected 108 quiet
and 540 paired tests retain every admission/ownership result. All 180 two-bit
gap entries advance five clocks; 16/18-bit gap entries and quiet deadlines
remain unchanged. This saves 12 bytes from the unpromoted 1958-byte intermediate.

One further alignment clock performs useful work: normal reception clears the
old IN-ACK eligibility marker R2 at packet completion. The equivalent later
token-only MOV is removed. The separate ACK owner bypasses this entry, and
normal paired DATA has already consumed a token that cleared the marker.
Token polling/deadlines stay fixed; short-DATA response clocks match the
original control. Terminal DATA gains one clock, still within the checked USB
response limits. This avoids a NOP and adds no code bytes.

The old-model exhaustive gate and the corrected-model 69-group control/current
runs retain separate scopes. The corrected model records actual OUT completion
at one clock and SBI at two; its 78 emitted-word regressions also check both
possible simultaneous set/clear policies separately. No silicon priority is
inferred from a test policy. See the [AVR model audit](AVR_MODEL.md).

## Completed corrected-model comparison

The original 1934-byte body and final 1946-byte body each completed all 69
groups with the corrected model. All 145 independently frozen reference
files are byte-identical. Both runs verified their source/model/artifact pins
before and after every group. The linked body and all symbols also match the
selected R2 control; each ELF hash is pinned separately.

| Mandatory finding | Original failures | Final failures |
| --- | ---: | ---: |
| Adjacent overlong-token excursions | 720/3456 | 0/3456 |
| Asymmetric DATA excursions | 120/2484 | 120/2484 |
| SE1 DATA excursions | 63/2486 | 63/2486 |
| DATA payload excursions | 69/981 | 69/981 |
| SYNC excursions | 144/1080 | 59/1080 |
| Short-status interior boundary | 12/108 | 12/108 |

The original passes 63/69 groups; the final passes 64/69. Both exit 1.
There are zero new failing contexts/groups and zero changed shared failure
observations. The [pinned comparison](compact_token_transfer_2026_11_10.json)
records report hashes, exact failure identities and all 805 repaired contexts.
Remaining errors are not expected passes or additional USB waivers.

The final gate includes 268 instruction/skip timing cases and every linked
code instruction's explicit cycle class, 78 PCIF controls, 213248 token
address/endpoint/CRC5/count cases, outgoing CRC16, NVM/ACK ownership, minimum-gap
followups, 670 ns EOP, threshold-dependent EOP, legal dribble and certified
jitter/crossover matrices. These are finite software tests.

An independent set-wins PCIF-policy run passes 25/26 targeted groups; its only
failure is the same 12-case short-status finding. All 15 common strict outcomes
match the default-policy checks; the complete status observations and persisted
OUT-response, polling and late-entry timing reports match exactly. No silicon
set/clear priority is assumed. An additional 192 thresholded SETUP/OUT quiet
and paired cases preserve the token wait decisions between the two controls.

The earlier 8046bc82 body completed the old-model 67-group gate with 63/67
passing, but shifted the inherited short-status error one clock earlier.
The final R2 move restores its original timing. A separate DATA recovery
experiment changed an existing drop into ACK with corrupted EF-to-DB payload;
it was rejected. Failure counts alone cannot justify either semantic change.

Digital AVR/GPIO tests do not establish analog electrical compliance. No image
from this transfer has been flashed. The 1280-byte target remains unachieved.

## Additional short-status EOP finding

The new `test_status_boundary_crossover` adds a mandatory group. Its
literal `4b04417c` is DATA1 with payload `04` and valid CRC16. Two separately
settled monotonic crossover observations in its fourth wire byte can be
mistaken for EOP after three bytes. This is a permitted nonempty read-status
inquiry under USB 2.0 section 8.5.3.1; shortening the accepted payload is not
a valid repair. The test checks complete PID/payload/count, no drive before
the real packet end, physical response timing, pin release and stack balance.

The baseline, atomic-SYNC image and 1958-byte terminal-token candidate all
fail 12 of its 108 cases. All 54 pristine controls pass. At host 1499250,
jitter sign -1 and entry 5, the baseline enables USB drive at clock 404,
before true EOP begins at 426.8801067200267; the terminal-token candidate
drives at 403. The numeric incoming CRC waiver cannot excuse early drive.
The earlier frozen 67-group comparisons did not contain this new oracle and
do not supersede it. The finding remains open; no test is marked expected-pass.
