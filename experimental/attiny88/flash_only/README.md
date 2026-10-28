# ATtiny88 Flash-only USB loader

This separate experimental target imports Pass35 from the EEPROM handoff archive.
The EEPROM-capable [compact v3.0](../compact/README.md) remains available unchanged.
No image in this directory has been installed or physically USB-tested.

Vendor protocol v4.1 uses absolute-address WRITE2/READ8 and explicit page commit.
It is incompatible with the v3.0 client. The corrected no-LED audit profile is
0x0460 at 0x1A40, with 6716 application bytes. The active client rejects the
unqualified archive profiles 0x0450..0x0452 and unknown identities before any
memory commands. Applications
stay linked at zero, with RESET-only patching and a four-byte postscript under
the [application contract](../compact/docs/APPLICATION_LAYOUT.md).

The import baseline is 1034 bytes without LED.
At 0x1C00 the baseline without LED is 1030 bytes, six over 1 KiB. The rejected
1024-byte archive prototype can start Flash SPM before status ACK completes;
its smaller size is not an admission criterion. Active work fixes USB defects
before treating an optimized image as usable.

The current 1408-byte image has SHA-256
`d7f817ee872f9d481c1d2bce756ee3ba73dcc3b8ed8d40ffe9dcdd8e5ca9405a`.

Size optimization and release placement consider **no LED only**. LED options
remain available for behavioral checks. Alternate placements and LED builds
advertise 0xFFFF unless an explicit new profile is supplied; the active client
does not recognize them. Current measured bytes are pinned in host/profiles.py
and checked against the linked image when generating an audit artifact.

## Build and software verification

```sh
python3 build.py --require-fit
sh verify.sh
python3 host/flash_only_programmer35.py --help
```

The builder links AVR relocations before opcode tests or BIN export. Generated
output stays in ignored build/ and firmware35/. References 33/34/35 are frozen
audit inputs; unsafe ISP images and nested ZIPs were not imported. Original
archive/source hashes are in ARCHIVE_PROVENANCE.json.

## Scope and open findings

The sole accepted USB exception is omitted received DATA CRC16 validation,
both before ACK and afterward.
Outgoing CRC16, token CRC5/endpoint/length admission, retry/ACK ownership,
SET_ADDRESS, reset cancellation and Flash guards require independent checks.
The archive does not close those protocol findings; its tests are a baseline.
Digital models at exactly 16 MHz do not establish electrical USB compliance.

Receiver qualification remains in progress, including legal final dribble and
single-ended observations during differential crossovers. Generated images are
software audit checkpoints while these findings are open. The existing board
has not been changed. The no-LED receiver, control-state and token tests use
the same linked AVR words that are exported, with independent waveform inputs.

For this checkpoint, the software checks passed 2212 standard-request cases,
214272 token cases, 4032 foreground IN injections, 1889 complete-packet waveform
cases, 57 control-read completion sequences and 12 vendor-status guard cases.
The complete verification run fails when an ACK has one legal extra final one
bit (dribble). This failure remains mandatory and visible. Passing the other
checks does not qualify this image for hardware use.

EEPROM is absent from this permanent loader. eeprom_stage/ is an offline planner
for a temporary application and subsequent main-image restoration. USB
re-enumeration alone is insufficient proof of EEPROM success; no automatic
hardware installation is part of this import.

## Comparison with official Micronucleus

Measured checkpoint, October 28, 2026: ATtiny88, external 16 MHz, LED disabled,
BOOT_AT 0x1A40, code bytes excluding erased Flash padding. Official source is
commit `4dd1b49f39cd9d6fc736a720777ed62f4564e0e2`; its executable firmware sources
match release v2.6 (only the size-report script and firmware README differ).
It was built with the upstream flags and AVR-GCC 7.3.0, changing LED_MODE only.
Our standalone assembly uses linked LLVM 18 output; this is not a compiler-only
comparison or a claim of identical features.

| Image | Measured code bytes |
| --- | ---: |
| Official v2.6 t88_default, no LED | 1332 |
| Previous compact v3.0 size milestone, no LED | 1088 |
| Imported Pass35 Flash-only baseline | 1034 |
| Current Flash-only audit checkpoint | 1408 |

The official README's published t88_default figure is 1432 bytes; the original
configuration enables LED. The measured no-LED image is the fair size reference
here. The current checkpoint is 76 bytes larger, with unresolved receiver work.
The 1088-byte v3.0 milestone and 1034-byte archive baseline predate this audit's
added checks; their smaller sizes do not establish equivalent USB behavior.
The physically installed v3.0 image is an earlier 1148-byte build.

| Behavior | Official t88 v2.6 | Current Flash-only experiment |
| --- | --- | --- |
| Flash upload payload | Four bytes, advancing cursor | Two bytes, absolute address |
| Page programming | Automatic at page boundary | Explicit COMMIT_PAGE |
| Application Flash readback | No command in this protocol | READ8, including host verification |
| Permanent EEPROM USB access | None | None; separate offline temporary-app plan |
| RESET redirection | Host postscript plus firmware RESET safety override | Host RESET/postscript packing |
| Incoming CRC5 / CRC16 | Neither checked | CRC5 checked; DATA CRC16 explicitly waived |
| IN retry state | Assumes successful ACK and frees TX on send | Cached DATA/PID retained until ACK/status completion |
| SET_ADDRESS activation | During status DATA EOP | After eligible status ACK |
| Host delay after programming | 7 ms normally; 5 ms in fast mode | Configurable, 7 ms default |

The upstream [driver limitations](https://github.com/micronucleus/micronucleus/blob/4dd1b49f39cd9d6fc736a720777ed62f4564e0e2/firmware/usbdrv/usbdrv.h)
explicitly list unchecked token/data CRC, stuffing errors, misplaced SE0 and
DATA toggle handling. Its [common RX/TX code](https://github.com/micronucleus/micronucleus/blob/4dd1b49f39cd9d6fc736a720777ed62f4564e0e2/firmware/usbdrv/asmcommon.inc)
documents the successful-ACK assumption. Therefore the official implementation
is a compact practical bootloader, not evidence that all USB error recovery is
implemented. Our added checks cover specific gaps, but our current strict
framing gate still rejects legal dribble; the full verify suite deliberately
exposes that failure. Neither image is declared USB-IF certified here.

Standard control requests also differ. Upstream has handlers for enumeration,
status, configuration and interface queries, but limited request-shape checking
and a zero-length default for unsupported requests. This experiment adds
explicit standard/class/vendor separation, STALL paths, preserved SETUP fields,
reset cancellation and exact-length reply completion. These are tested subsets,
not proof of all Chapter 9 behavior. Zero-length requests ignore their direction
bit as required by USB 9.3.1; 16 wire sequences cover IN status and retries.

The compiled upstream t88 image warrants a separate standard-reply check:
GET_STATUS and GET_CONFIGURATION select SRAM reply pointers, while the selected
read path uses LPM. This is a source/disassembly finding, not a measured failure
on hardware. The official 16 MHz PHY has not received the same waveform audit
as this experiment; no relative timing-compliance claim follows from code size.

The official uploader and this vendor v4.1 client are incompatible. At a
64-byte page our WRITE2 path needs 32 staging requests instead of 16 WRITE4
requests, plus explicit commit. No on-board throughput equivalence is claimed.
The upstream [command implementation](https://github.com/micronucleus/micronucleus/blob/4dd1b49f39cd9d6fc736a720777ed62f4564e0e2/firmware/main.c),
[standard-request implementation](https://github.com/micronucleus/micronucleus/blob/4dd1b49f39cd9d6fc736a720777ed62f4564e0e2/firmware/usbdrv/usbdrv.c)
and [host delay policy](https://github.com/micronucleus/micronucleus/blob/4dd1b49f39cd9d6fc736a720777ed62f4564e0e2/commandline/library/micronucleus_lib.c)
are pinned to the compared commit. Only the selected t88 configuration is
compared; upstream supports other AVR devices and clock/configuration options.
