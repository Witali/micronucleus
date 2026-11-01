# Pass29 page-boundary candidate

The next milestone is a real 17-page, 1088-byte no-LED region starting at
`0x1BC0`. The final objective remains 16 pages / 1024 bytes at `0x1C00`.
Pass28 checkpoint e70a9f7 measures 1102 bytes at `0x1C00`, but 1106 at
`0x1BC0`: a nonzero boot-address low byte needs four more bytes in the final
SPM boundary check. Only the actual placement's fit gate establishes a page
milestone; rounding a measurement from another address does not.

## Admitted reductions after Pass28

The PHY saves eight bytes, from 478 to 470. RX pointers never borrow into
YH=1, so RX-end SBCI and IN-path high-byte reload are unnecessary. The RX
pointer/count/flag proof covers 39936 combinations. Every sampling instruction
and its order remain pinned by the emitted-word audit.

Two PCIF reads use bit-addressable SBIC directly. The token-to-DATA wait now
uses twelve five-cycle idle iterations instead of ten six-cycle iterations;
both empty timeouts last 59 cycles. A detected flag and packet-done chain
handoff advance by one cycle. These are intentional changes to chained timing,
while the per-bit decoder and external-entry sampling schedule stay unchanged.
The isolated dense sweep covers 3384 token/DATA chains per image across host
clock endpoints, minimum gaps and quarter-cycle entry phases. The combined
candidate retains the synchronized GPIO/PCINT and TX waveform checks.

The poll loop saves four more bytes by pre-decrementing X before sampling.
Seeding one extra tick lets the first sample fall through and removes two
timeout jumps. A thirteen-cycle loop retains 6153 samples and a 79996-cycle
quiet timeout (4.99975 ms). The five-cycle PCIF-to-handler call edge is unchanged.
The combined source passes startup/deferred-command/RUN checks and 2160 actual
main-poll captures across all three profiles; maximum physical entry is twenty
cycles. Sustained SE0 clears both USB addresses after exactly one hundred samples.

Useful zero loads save four more bytes in NONE, two in LED builds. The constant
context byte at offset 14 replaces a zero LDI plus NOP in the stuffing path.
For NONE, the same two-cycle load replaces DDRD read/mask at EOP release:
RESET and the exact emitted writer inventory prove that every non-USB DDRD bit
remains zero. LED builds retain the dynamic read/mask. Sampling, GPIO times and
flags are unchanged. Startup, exact-opcode audits and 16872 TX waveform/state
cases pass across four placements; NONE rejects 19 audit mutants and LED
profiles reject 18. The PHY is now 466 bytes in NONE, 468 with LED.

The final two-byte reduction removes the periodic WDR after startup has already
disabled the watchdog. The startup WDR and timed disable remain. An emitted-code
lifetime audit closes direct WDTCSR writes and all non-context Z stores; it
pins the four startup stores for watchdog/PCINT initialization. Main-entry
tests execute all 1024 RX length/token combinations with real stack bytes,
checking both valid SETUP capture and invalid reception paths.

| Placement/profile | Pass28 bytes | Candidate bytes | New saving |
| --- | ---: | ---: | ---: |
| No LED, `0x1C00` measurement | 1102 | 1084 | 18 |
| No LED, `0x1BC0`, 17-page milestone | 1106 | 1088 | 18 |
| No LED, `0x1B80`, installed geometry | 1106 | 1088 | 18 |
| Active high, `0x1B40` | 1124 | 1108 | 16 |
| Active low, `0x1B40` | 1122 | 1106 | 16 |

The strict 17-page size gate passes exactly: 1088 bytes at 0x1BC0, ending at
0x2000 exclusive. The 1024-byte goal remains sixty bytes over budget when
measured at its own 0x1C00 boundary.

The final combined source passes verify27.sh for all three existing fitting
profiles and the new NONE placement at 0x1BC0. This includes complete standard,
NVM/cursor and watchdog/frame tests, 167924 no-packet intervals, 248 synchronized
minimum-IPD scenarios, 16872 TX waveform/state cases and 2880 actual main-poll
captures. The physical-SOP bound is 39 cycles; observed synchronized entry is
at most 37 2/3 cycles, response 44 1/3 cycles and peak stack six bytes.
The reproducible body hashes and test counts are recorded in
[the milestone result](../results/page17-pass29.json).

These are emitted-instruction and digital GPIO/PCINT model checks at exactly
16 MHz. They do not add electrical measurements or close the documented
protocol findings. The 17-page image has not been installed on hardware.

## Verification and release boundary

```sh
sh verify27.sh
python3 tests27/page17.py
python3 build_candidate.py --boot 0x1BC0 --require-fit
python3 build_candidate.py --boot 0x1C00 --require-fit
```

The fit gates remain strict. Exact-size regression expectations are the
deployed reference sizes minus measured CANDIDATE_SAVINGS, which is currently
60 bytes for NONE and 58 for LED profiles. No code, descriptor or reserved
application bytes are excluded.

The installed firmware remains e405ea7: 1148 bytes at `0x1B80`, USB profile
0x0300. Frozen firmware27 images and host profile geometry remain unchanged.
Measurement builds at a new boundary are development artifacts; a deployable
image there needs its own recognized profile under the
[application contract](APPLICATION_LAYOUT.md). No hardware write is part of
this size work. The receive-CRC exception and other open protocol findings in
[USB_PROTOCOL.md](USB_PROTOCOL.md) remain separate from size/timing admission.
