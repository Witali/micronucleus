# Combined SYNC and packet crossover regression

The 1960-byte receiver at `0x1800` (`e081fcf7`) fails 2721 of 6480
injected cases in the new exhaustive corpus. All 810 pristine controls pass.
The current firmware target is 1536 bytes without LED at `0x1A00`.

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

## Complete baseline at the 1536-byte goal

The linked `e081fcf7` body completed the exhaustive 71-group gate in
1207 seconds. It passed 64 groups and failed seven. All pinned inputs
matched throughout the run and all 189 exported files were verified.
The full report SHA256 is
`789998b5fad3c269a0f12abcf2387a2759ffb8587459ee76ee022237584abb47`.

| Mandatory group | Failing cases |
| --- | ---: |
| Short DATA status boundary | 12/108 |
| Asymmetric DATA crossover | 120/2484 |
| SE1 DATA crossover | 63/2486 |
| Payload crossover | 69/981 |
| SE0 SYNC crossover | 35/1080 |
| SE1 SYNC crossover | 90/1080 |
| Combined SYNC and packet crossover | 2721/6480 |

The prior size audit measured a composed image of exactly 1536 bytes at
`0x1A00`. Its receiver qualification was still open. The target uses the
current required USB checks, including the expanded corpus above. See the
[historical size record](SIZE_REDUCTIONS.md#share-small-standard-replies-under-their-specified-lengths).

Rebuilds at `0x1A00` produced 1534 bytes at `a617db5`, 1526 at `f89b853`,
1520 at `91c3814` and 1518 at `cf8278b`. In the 1518-byte body, the current
aperiodic suite finds 30 failures in 180 cases and the truncated-ACK
followup suite finds 48 in 252. The 18 bytes of remaining capacity must
cover these receive requirements along with the crossover repairs.

The linked regions explain the size difference between that historical
1518-byte image and the current 1960-byte body. Region boundaries use the
same instruction ownership labels where present. The TX range includes
post-response control, and the receive range includes framing and ACK state.

| Linked region | 1518-byte body | 1960-byte body |
| --- | ---: | ---: |
| Vector and descriptors | 38 | 38 |
| Receive, framing and ACK state | 484 | 580 |
| Dispatch and TX preparation | 202 | 178 |
| TX and post-response control | 228 | 224 |
| Additional terminal token/DATA receive path | 0 | 226 |
| Separate ACK receiver | 0 | 174 |
| Startup, foreground EP0 and Flash | 566 | 540 |

The two added receive paths occupy 400 bytes. Meeting the target with the
current 1000 bytes outside these three receive ranges would leave 536 bytes
for acquisition, packet reception, framing and ACK handling. The historical
484-byte receive range demonstrates the size of shared decoding with weaker
recovery. The open work is to share the byte/terminal and ACK paths while
retaining the newer receive and timeout guarantees.
