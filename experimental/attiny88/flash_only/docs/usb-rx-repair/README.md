# Independently validated receiver repair controls

These patches preserve larger correctness controls while smaller repairs are
investigated. They do not alter the default build. Each applies independently
to the composed receiver at runtime-source checkpoint `cf8278b`; the later
test-suite-only changes do not invalidate their contexts.

| Patch | No-LED bytes at temporary 0x1800 | Body SHA256 |
| --- | ---: | --- |
| [Private bit7 store](bit7-private-store.patch) | 1548 | `eec3ad0dcab2a34bd8034b526cd2d65f9cc4b309c5a2da09cd86fb02eb9924af` |
| [Odd5 crossover recovery](odd5-crossover-recovery.patch) | 1552 | `4e33d76bfcf6d3756c5a578adfe2bd43e34c085471f6e3a5f656276a5c1ef2e3` |

The bit7 repair moves only the next bit0 observation two clocks later; the next
odd sample and fractional state remain aligned. It passes the linked 6656-state
equivalence proof, framing, malformed stuffing, token, jitter and followup checks.
The 180 aperiodic cases improve from thirty failures to the ten inherited EOP
misses. Its full 25200-case matrix preserves the single inherited EOP failure.

The odd5 repair resumes after a short crossover, verifies the mandatory NRZI
transition, and repays confirmation latency before bit7. Its 12332-state
equivalence proof and 2048 negative-transition probes pass. It fixes all fourteen
centered 150 ns zero-jitter failures, with no new failure identities in the
completed crossover, framing, token, followup and dense-EOP checks. It does not
fix the separate bit7 or short-EOP findings.

Use a separate task worktree under the repository root's `.worktree/` and apply
one patch at a time from that worktree's root. Run the builder and verifier from
the Flash-only directory:

```sh
python3 build.py --where variants/combined_rx --boot 0x1800 --require-fit
python3 verify_receiver.py --boot 0x1800 --exhaustive
```

The temporary placement keeps the complete experimental body inside physical
8 KiB Flash. Both patches overflow the 1536-byte region at 0x1A00. Their profile
remains FFFF and is rejected by the host. Neither is a release, a 1280-byte
success, a tested combination of both patches, or permission to program a board.
The verifier remains strict and reports the inherited failures.
