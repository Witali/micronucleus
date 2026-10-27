# Pass28 size-reduction candidate

The active source is a software candidate for the 1024-byte goal. The installed
loader and frozen `firmware27/` images remain the e405ea7 hardware checkpoint;
their exact body sizes/hashes and host profile geometry are unchanged. Do not
mistake a candidate build for a new hardware-tested release.

The [application layout contract](APPLICATION_LAYOUT.md) remains fixed:
ordinary application at zero, RESET-only patching, original interrupt vectors,
and four-byte postscript at `BOOT_AT-4`. No status-polling extension, feature
removal, hardware programming, or vector-page relocation is part of Pass28.

## Admitted reductions

The first two-byte reduction places TX preparation directly after the shared
deferred-command tail. Idle/SPM completion falls through, and the busy/RUN
branches target the nearby continuation without a trampoline. Request handlers
move together after the application handoff's unconditional jump. The empty
reply publishes zero directly before returning to cooperative service.

`vusb_requests.inc` owns vendor dispatch and shared reply pointer/length helpers;
`vusb_ep0.inc` owns TX-buffer preparation and outgoing CRC. This module split
emits exactly the bytes tested in the isolated nearby-TX probe.

| Placement/profile | Installed reference bytes | Candidate bytes | Saved |
| --- | ---: | ---: | ---: |
| No LED, `0x1C00` measurement | 1144 | 1142 | 2 |
| No LED, `0x1B80` fitting placement | 1148 | 1146 | 2 |
| Active high, `0x1B40` | 1166 | 1164 | 2 |
| Active low, `0x1B40` | 1164 | 1162 | 2 |

At the intended `0x1C00` boundary the candidate is still 118 bytes too large.
Measurement links use a larger linker region to quantify overflow; this is
not permission to program an image beyond the ATtiny88's 8192 bytes.

The 494-byte PHY remains identical. All fitting profiles pass standard/stateful
EP0, NVM/unknown requests, independent outgoing CRC and cooperative USB checks.
The measured no-packet gap is 31 cycles; adding 5 entry and 3 synchronizer cycles
gives 39 physical-SOP cycles, below the 40-cycle limit. The 62 synchronized cases
per profile retain entry 38 cycles, response 47 1/3 cycles and peak stack 6 bytes.

## Build and admission

```sh
python3 build_candidate.py --all-led
sh verify27.sh
python3 build_candidate.py --boot 0x1C00 --require-fit
```

The final command remains a failing gate until the complete image fits 1024
bytes. `verify27.sh` keeps its historical name but tests the active modular
source. Exact candidate size expectations are the deployed reference sizes
minus `build_candidate.CANDIDATE_SAVINGS`; changing them requires measured
emitted-code evidence, not merely changing a test to permit growth.

The old release builder remains specific to frozen Pass27. Reproduce those
images from e405ea7 rather than overwriting them from a development source.
No candidate image is automatically installed. A new hardware placement must
receive a compatible explicit USB profile before deployment.

Further NVM, EP0 and PHY candidates are tested in isolation before integration.
Their savings cannot be added together as an achieved size until a combined
build and its timing/behavior checks pass. Known protocol limitations and the
accepted incoming DATA CRC exception remain documented in USB_PROTOCOL.md.
