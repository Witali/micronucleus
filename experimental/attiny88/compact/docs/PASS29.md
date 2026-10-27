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

| Placement/profile | Pass28 bytes | Candidate bytes | New saving |
| --- | ---: | ---: | ---: |
| No LED, `0x1C00` measurement | 1102 | 1090 | 12 |
| No LED, `0x1BC0`, 17-page milestone | 1106 | 1094 | 12 |
| No LED, `0x1B80`, installed geometry | 1106 | 1094 | 12 |
| Active high, `0x1B40` | 1124 | 1112 | 12 |
| Active low, `0x1B40` | 1122 | 1110 | 12 |

The 17-page fit gate is still six bytes over budget at this stage.

The PHY8 checkpoint passed verify27.sh for all three existing fitting profiles:
15 negative PHY-audit cases per profile, complete standard/NVM/cursor tests,
125943 no-packet intervals, 186 synchronized minimum-IPD scenarios and 12654
TX waveform/state cases. The physical-SOP bound is 39 cycles; observed
synchronized entry is at most 37 2/3 cycles, response 44 1/3 cycles and peak
stack six bytes. The new 0x1BC0 placement is measured separately until its
own page-boundary admission.

## Verification and release boundary

```sh
sh verify27.sh
python3 build_candidate.py --boot 0x1BC0 --require-fit
python3 build_candidate.py --boot 0x1C00 --require-fit
```

The fit gates remain strict. Exact-size regression expectations are the
deployed reference sizes minus measured CANDIDATE_SAVINGS, which is currently
54 bytes. No code, descriptor or reserved application bytes are excluded.

The installed firmware remains e405ea7: 1148 bytes at `0x1B80`, USB profile
0x0300. Frozen firmware27 images and host profile geometry remain unchanged.
Measurement builds at a new boundary are development artifacts; a deployable
image there needs its own recognized profile under the
[application contract](APPLICATION_LAYOUT.md). No hardware write is part of
this size work. The receive-CRC exception and other open protocol findings in
[USB_PROTOCOL.md](USB_PROTOCOL.md) remain separate from size/timing admission.
