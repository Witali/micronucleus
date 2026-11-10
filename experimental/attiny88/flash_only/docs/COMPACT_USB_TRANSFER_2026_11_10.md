# Compact USB repair transfer, November 10

The target is a complete no-LED ATtiny88 loader of 1280 bytes. A standalone
receiver count does not meet that target. These changes keep the shared EP0,
TX, Flash and application-layout owners; no table, release profile or hardware
installation is introduced. USB 2.0 chapters 7, 8 and 9 remain the reference, with only
the existing numeric incoming DATA CRC16 validation/storage exception.

## Atomic SYNC confirmation

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

Digital AVR/GPIO tests do not establish analog electrical compliance. No image
from this transfer has been flashed. The 1280-byte target remains unachieved.
