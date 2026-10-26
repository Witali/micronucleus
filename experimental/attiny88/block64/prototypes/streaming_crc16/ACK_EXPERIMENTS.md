# MOVW and ACK publication experiments

These are opt-in digital experiments against the frozen streaming-V2
receiver. The default diagnostic application and guarded memory benchmark
remain unchanged. No hardware was programmed for this experiment.

## Result

| ACK mode | SOP saving | Extra return work after EOP | Code/static bytes before tables |
| --- | ---: | ---: | ---: |
| immediate, original | 0 | 0 | 3262 |
| context, MOVW only | 1 clock | 0 | 3258 |
| deferred, publication after completed ACK | 3 clocks | 7 clocks | 3268 |
| eop, publication in fixed SE0 wait | 3 clocks | 0 | 3282 |

At 16 MHz, three clocks are 0.1875 microseconds. All images still span
4096 bytes because their 512-byte CRC tables remain at the same aligned
addresses. The EOP candidate adds 20 executable/static bytes; alignment
padding decreases accordingly.

The recommended experimental mode is `eop`. Its nominal legal-tail ACK
range is 47 2/3..65 clocks, with a bounded rate/jitter maximum of 65 2/3
(4.104 microseconds), against the 69 1/3-clock response maximum. The
worst modeled margin increases from 2/3 to 3 2/3 clocks, about 229 ns.
These are instruction-model timings, not measured analog edges.

## Mechanism

Completed EOP paths normalize Y to 0x0100 instead of subtracting the RX
length to restore 0x0116. YH is already one because the fixed 11-byte RX
buffer cannot cross a page. MOVW then restores Z in one clock instead of
two LDI instructions. Token fields use Y+22..24; early drop paths retain
explicit Z initialization because their Y can still be an unfinished cursor.

After CRC, token and free-buffer checks, MOVW R24,R18 stages token/count
and R27 marks a pending publication. This costs two clocks instead of the
original four-clock pair of SRAM stores. A PID-setup padding NOP becomes
LDI R27,0 without moving any input sample.

The strict post-ACK alternative publishes at L1be8. It saves the expected
three clocks before SOP but adds seven clocks afterward. Four fast
retry-response cases differ adversely from baseline. In those cases
baseline itself misses the preceding token and responds using stale
token state, so it is not a complete successful transaction either.
This alternative is retained for reproduction, not selected.

The EOP alternative replaces the existing twelve-clock delay after ACK
PID bits with two balanced twelve-clock paths. The pending path publishes
count/token and clears R27; the other path only waits. Both leave R21 zero,
preserve the relevant flags, and reach the original bus-release instructions
at exactly the same clock. Publication occurs during SE0, before return to
J; it must not be described as after a completed ACK.

## Verification

- 6528 positive DATA frames and 16 functional/boundary regression tests pass.
- All 15648 legal tails and 11664 source-rate/interval-jitter cases pass.
- Original, context and deferred modes each passed 48864 short-frame
  CRC/count cases, explicitly checking Y=0116 or0100 as appropriate.
- The independent continuation model latches PCIFR asynchronously and
  models write-one-to-clear. It executes the real RET and foreground,
  without forcing a buffer release or a second handler entry.
- 108 fast sequences and two full 480-case retry/ACK sweeps have no new
  EOP-candidate regression. All 1624 matched transmissions preserve exact
  normalized PORTD/DDRD waveforms, flags and the zero wait counter.
- Pipeline pytest has nine passing tests and three narrowly typed strict
  expected failures for existing baseline contracts. Unexpected exceptions
  remain failures; a future fix requires removing its strict tracker.

Those inherited defects remain open: minimum-gap OUT/IN tokens can be lost
while foreground repeats CRC/copy work, and the PHY can overwrite an already
owned RX scratch payload before choosing NAK. Matching baseline behavior
does not establish correct continuous USB reception. Raw diagnostic reports
continue to expose all failed contract checks.

Compact hashes and counters are in [the evidence record](evidence/2026-10-26-ack.json).
Raw synthetic trace reports remain in the ignored build directories.

## Reproduce

Run from `experimental/attiny88/block64`:

```sh
python3 prototypes/streaming_crc16/tools/build.py
python3 prototypes/streaming_crc16/tools/build.py --ack-mode context
python3 prototypes/streaming_crc16/tools/build.py --ack-mode deferred
python3 prototypes/streaming_crc16/tools/build.py --ack-mode eop
python3 -m pytest -q prototypes/streaming_crc16/tests/test_ack_pipeline.py
python3 prototypes/streaming_crc16/tools/verify_ack_pipeline.py --manifest prototypes/streaming_crc16/build/streaming-v2-eop/manifest.json --baseline prototypes/streaming_crc16/build/streaming-v2/manifest.json --scenario out-retry --full --quiet
```

`STREAMING_CRC_MANIFEST` selects the ordinary packet tests' image.
`ACK_PIPELINE_MANIFEST` selects the optional pipeline candidate.
`STREAMING_CRC_EXPECT_NORMALIZED_Y=0x0100` makes the short-frame matrix
assert the new pointer convention.
