# Combined SYNC and packet crossover regression

The 1960-byte receiver at `0x1800` (`e081fcf7`) fails 2721 of 6480
injected cases in the new exhaustive corpus. All 810 pristine controls pass.
The firmware target remains 1280 bytes.

The corpus applies the independently certified both-low or both-high
voltage witnesses to each differential transition after SOP in an eligible
ACK and two valid SETUP DATA0 packets. Adjacent transitions settle between
the witness intervals. Their differential edge positions stay within the
75/45 ns receiver limits. All tests retain the existing packet, response
timing and state ownership checks. See sections 7.1.2.1, 7.1.4.1 and 7.1.10
and Table 7-10 of the [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification).

## Wait-for-K poll experiment

The receiver uses six consecutive two-clock polls while the bus reads J.
`SBIS PIND,D-` and `SBIC PIND,D+` branch identically on settled J and K and
differ on SE0 and SE1. A finite screen compared all 64 configurations on
1080 SE0, 1080 SE1 and 54 pristine SYNC waveforms for SETUP DATA0.
It executed linked body words, reusing an execution when the configurations
agreed at every ambiguous poll it reached. The two previously recorded
uniform-poll controls reproduced their failure counts exactly.

The second/fifth D+ configuration repaired 54 SYNC-only cases and 57
of 99 failed ACK SYNC cases. Its rebuilt 1960-byte image (`dd74fffe`)
differed at precisely two instruction words, `0x1834` and `0x1840`, with
identical symbol addresses. The combined corpus found 32 new failures at
integer entry phases. The exhaustive verifier on this candidate stopped
after 51 completed groups when those failures made it unsuitable.

The third-only and fourth-only D+ configurations showed no new failures
in the integer combined corpus. The fractional phases exposed 35 and 21
new failing contexts, respectively. One witness for the third-only variant
is an ACK with both-high reverse-alternating excursions at 1,499,250 bit/s,
zero periodic jitter and handler entry 40.5 clocks. The baseline decodes
and retires the ACK, while the changed acquisition loses the frame and
leaves the eligible transaction pending.

The maintained verifier now includes `test_rx_combined_crossover` and
compares its failure contexts in complete gate runs. The earlier
[SYNC qualification](COMPACT_SYNC_QUALIFICATION_2026_11_10.md) records the
tested baseline and its previous gate scope. The new coverage shows why
phase decisions must preserve the following packet observations across
both isolated and combined crossover signals.
