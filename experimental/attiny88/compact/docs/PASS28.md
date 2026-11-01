# Pass28 size-reduction candidate

This records the e70a9f7 checkpoint. Active development continues in
[Pass29](PASS29.md). The installed
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

Startup then shares one Z pointer between the watchdog register and the two
nearby PCINT registers. Indirect watchdog stores replace STS without changing
their two-cycle separation. Z is untouched by the disconnect countdown; STD
offsets configure PCMSK2/PCICR later. This saves four more bytes. Compile-time
guards enforce the memory-map assumptions. The startup decoder executes the
real indirect memory-mapped IO stores while retaining every original watchdog,
SRAM, disconnect-time and USB-enable ordering assertion.

The next six bytes come from NVM state ownership and instruction reuse. The
EEPROM queue count moves from R8 to R2, so the completed startup countdown can
clear R2:R3 with one MOVW. Deferred SPM/RUN dispatch uses R3 directly; its only
reachable values are 0, 2, 3, 4 and 5. An exhaustive public-opcode/prior-state
check covers 2560 transitions per profile. Accepted EEPROM WRITE4 uses the
bounds comparison's carry with request value 3 to form queue count 4 with ADC.
The tests retain asynchronous busy handling and poison the now-free R8.

PHY changes save another sixteen bytes. External calls enter with the complete
Y context pointer, so MOVW initializes an immutable Z and later restores Y.
Two useful LDIs call the existing polynomial-load/RET tail to provide the same
ten-cycle RX initialization. A two-cycle RX_LENGTH load replaces an alignment
jump; DATA and IN dispatch reuse the snapshot instead of loading it again.
After atomic DDR release, CBI clears the D-minus output latch. Rescheduled delay
words retain the eleven-cycle driven J interval. The emitted-word audit pins
each replacement, unchanged sampling instructions and branch destinations;
cooperative execution now checks the complete external Y pointer.

EP0 then saves fourteen bytes. A full-word CP/CPC comparison clamps replies to
wLength; SUBI both selects an eight-byte packet and computes its remainder.
Descriptor kinds share the Flash-pointer high-byte tail, with a compile-time
page guard. Main-loop and cooperative SETUP paths share one token validator.
A valid SETUP discards exactly one real return frame before field capture;
the invalid cooperative path retains its fast RET. The non-bitstream executor
now uses the same byte stack for RCALL/RET and ordinary PUSH/POP. Independent
timed execution rejects a missing POP at field capture, and stateful transfers
assert an empty stack after SETUP and packet preparation.

| Placement/profile | Installed reference bytes | Candidate bytes | Saved |
| --- | ---: | ---: | ---: |
| No LED, `0x1C00` measurement | 1144 | 1102 | 42 |
| No LED, `0x1B80` fitting placement | 1148 | 1106 | 42 |
| Active high, `0x1B40` | 1166 | 1124 | 42 |
| Active low, `0x1B40` | 1164 | 1122 | 42 |

At the intended `0x1C00` boundary the candidate is still 78 bytes too large.
Measurement links use a larger linker region to quantify overflow; this is
not permission to program an image beyond the ATtiny88's 8192 bytes.

The PHY is 478 bytes, with unchanged RX sample instants. All fitting profiles
pass standard/stateful
EP0, NVM/unknown requests, independent outgoing CRC and cooperative USB checks.
The measured no-packet gap is 31 cycles; adding 5 entry and 3 synchronizer cycles
gives 39 physical-SOP cycles, below the 40-cycle limit. The 62 synchronized cases
per profile have entry 37 2/3 cycles, response 45 1/3 cycles and peak stack 6 bytes.
The complete `verify27.sh` suite passes, including 4218 TX waveform/state cases
per profile. These are instruction/waveform-model checks; the candidate has
not been installed or electrically measured on the board.

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
