# Historical USB receive comparison

This audit compares the official Micronucleus v2.6 ATtiny88 / 16 MHz driver
with our exact installed compact v3.0 image and the current Flash-only receiver.
All new experiments execute linked AVR instructions against independent digital
GPIO/PCINT waveforms. They do not access the board or measure electrical behavior.

## Provenance

| Image | Identity | Code bytes, no LED |
| --- | --- | ---: |
| Official v2.6 | Tag commit `882e7b4af38cb2795353e4e99336616963c6cd12`, t88_default | 1332 |
| Installed compact v3.0 | Source checkpoint `e405ea7`, BOOT_AT 0x1B80 | 1148 |
| Strict Flash-only checkpoint | `3c64c90`, BOOT_AT 0x1A40 | 1382 |

The official tagged firmware inputs match the previously pinned
`4dd1b49f39cd9d6fc736a720777ed62f4564e0e2` inputs after line-ending normalization.
The tagged no-LED build reproduces that pin byte for byte with AVR-GCC 7.3:
SHA256 `ec361683baa476be66826c884f2f3759b63451225a35d40a5318d8d1f8ce24bf`.
Its only configuration change is LED_MODE=NONE.

The installed v3.0 audit rebuilds the archived source rather than the later
optimized compact/source tree. All nine source hashes match firmware27's
manifest. Its body matches the archived Pass27_off_body.bin, the updater
payload before its four erased padding bytes, and the installation report:
SHA256 `e2a771412dfacf7a3ad7575d4ccb526791557c157633637ecf0c7fdbb9096df0`.
No private board-memory backup is needed for this comparison.

## What the older versions actually check

Both older receive implementations check supported PID values and the device
address, but omit token CRC5 and complete endpoint/length validation. Their
stuff-removal loops consume a mandatory symbol without verifying that it is
an NRZI transition. Their SE0 path also does not classify the residual bits
as a complete byte or permitted dribble before publishing DATA.

These limitations are inherited from the V-USB driver. The official
[driver limitations](https://github.com/micronucleus/micronucleus/blob/v2.6/firmware/usbdrv/usbdrv.h)
explicitly describe unchecked stuffing, misplaced SE0, token/data CRC and
DATA-toggle handling. Its
[common receive/transmit code](https://github.com/micronucleus/micronucleus/blob/v2.6/firmware/usbdrv/asmcommon.inc)
also documents freeing transmitted DATA before receiving the host ACK.
Source findings and executable counterexamples are distinguished below.

| Case | Official v2.6 | Exact installed compact v3.0 |
| --- | --- | --- |
| Correctly addressed normal IN token, two-bit EOP | Decoded and answered | Decoded and answered |
| Address-zero IN/OUT/SETUP, 670 ns EOP, entry 8 clocks | Misses EOP/admission | Misses EOP/admission |
| Device address 1 while active address is 0 | Address comparison exists | Ignored in the directed wire test |
| Bad token CRC5 | No check in the original code | IN, OUT and SETUP accepted in directed wire tests |
| Endpoint 1, 2 or 15 | Endpoint fields not fully checked | IN accepted in directed wire tests |
| Short or overlong token | No exact-length admission guard | PID-only, missing-CRC and overlong IN examples accepted |
| Damaged mandatory stuffed zero in DATA | No transition check | All 12 directed corruptions ACKed and published |
| Arbitrary zero after complete DATA | No residual-tail classifier | ACKed and published |
| Legal final dribble | No strict residual-tail rejection | Correct PID/payload/count in all 120 legal DATA cases below |
| Lost host ACK after IN DATA | Driver assumes successful ACK | Next identical IN gets NAK instead of the cached DATA |
| SET_ADDRESS status before host ACK | Address update occurs during transmitted status EOP | Active address changes before ACK; old-address retry is ignored |

The two 670 ns findings reproduce the same physical edge case on the actual
historical instructions. They do not mean ordinary host transmissions always
fail: the normal two-bit source EOP is longer. USB 2.0 Table 7-10 nevertheless
requires the receiver to accept a 670 ns SE0.

## Compact v3.0 directed corpus

The DATA corpus uses 24 valid CRC16 base packets: eight final-CRC classes each
for SETUP with eight payload bytes and OUT with two or eight payload bytes.
It appends every 0..7-bit physical tail pattern after normal stuffing:

- 6120 cases total, including 120 permitted full-byte/dribble endings.
- All 120 legal cases publish the exact PID, payload and byte count.
- 1590 of the 6000 illegal tails are still published by the old PHY.
- The separate all-FF DATA packet has 12 mandatory stuffed symbols; changing
  each one to a logical one is accepted and ACKed in all 12 cases.

The token-EOP matrix uses IN, OUT and SETUP to address zero, three host rates
1.49925/1.50000/1.50075 Mbit/s and six entry phases 5/8/16/24/32/38 clocks.
All 54 cases at 670 ns miss admission; all 108 cases at 21.333 or 24 clocks
reach the historical EOP path. This is a directed corner matrix, not a general
percentage of USB compliance.

DATA publication here means the original PHY exposes the received packet to
its foreground parser. It does not prove that every malformed request performs
a Flash write; the command parser and memory guards are later boundaries.

## Consequence for combining decoders

The old decoder's successful dribble reception cannot be copied as a complete
EOF rule: the same permissive path admits arbitrary partial tails and damaged
stuffing. Conversely, the newer strict receiver's legal-dribble rejection is
a regression introduced while adding framing validation. It is not evidence
that the older versions rejected those legal packets too.

A combined receiver should preserve the compact NRZI sampling schedule while
adding proven stuffed-symbol checks, complete-byte/dribble classification,
short-EOP qualification, token authorization, eligible ACK ownership and
deadline handling. Every composed image must rerun the same physical-wave and
control-state regressions; individually passing components are insufficient.

The sole approved exception remains incoming DATA CRC16 value validation.
It does not excuse stuffing, framing, missing CRC bytes, token CRC5 or timing.
The current [requirements matrix](USB_REQUIREMENTS.md) remains the admission
gate; neither historical version is a complete compliance reference.

Local evidence is under validation/historical-usb-audit in the workspace:
upstream26/provenance.json and upstream_model.py;
compact30/provenance.json, build/artifact.json and token-control-results.json;
raw_compact30.py and raw_compact30/results.json. Source reconstruction and
body hashes are checked before waveform execution.
