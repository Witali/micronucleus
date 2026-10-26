# Isolated 16 MHz streaming CRC receiver

The verified 512-byte table and sampler are frozen in the
[table512 checkpoint](checkpoints/table512/README.md). The
[smaller-table experiment](CRC_TABLE_TRADEOFFS.md) measures 32-byte,
16-byte and table-free alternatives against the available receive slots.

The later [opt-in ACK experiments](ACK_EXPERIMENTS.md) evaluate MOVW and
publication during/after ACK. Their recommended EOP candidate saves three
clocks without changing the default image or its NVM protection.

This directory builds an ordinary, read-only diagnostic application at
`0x0800`. It does not replace the maintained Block64 receiver or program
hardware. Both prototypes check DATA CRC16 before selecting ACK. V1 retains
an inverted bit-mask decoder; V2 uses a rolling byte and five-bit cooldown
continuations after stuffed zeros.

## Build and verify

Use the project's LLVM AVR / GNU AVR linker environment and Python pytest:

```sh
python3 prototypes/streaming_crc16/tools/build.py
python3 prototypes/streaming_crc16/tools/verify_streaming.py --suite smoke
python3 -m pytest -q prototypes/streaming_crc16/tests
python3 prototypes/streaming_crc16/tools/verify_streaming.py --suite dribble-full --report prototypes/streaming_crc16/build/dribble.json --quiet
python3 prototypes/streaming_crc16/tools/verify_streaming.py --suite tolerance-full --report prototypes/streaming_crc16/build/tolerance.json --quiet
```

Run from `experimental/attiny88/block64`. The default receiver is
`streaming-v2`; `--receiver streaming` retains the V1 experiment and
`--receiver baseline` builds the maintained decoder in the same diagnostic
wrapper. Neither alternate is a claimed fix for streaming CRC at 16 MHz.
`STREAMING_CRC_MANIFEST` selects a frozen build for pytest; the verifier
accepts `--manifest`. Byte hashes and symbols are frozen when a run starts.

Generated build products stay ignored. Diagnostic commands print
`DIAGNOSTIC ONLY`, even when all tested cases happen to pass. Inspect every
failure count, and the legal-tail subset separately: arbitrary seven-bit
transition-free tails exceed the specification's six-total-interval limit.
The strict pytest regressions do not silently accept known late responses.

## Application and NVM boundary

- The stock loader remains at `0x1B00`; every HEX data record ends before
  its four-byte application postscript at `0x1AFC`.
- The source RESET points to a trampoline at `0x0080`, then `0x0800`.
  The installed stock loader performs its normal RESET/postscript patching.
- Vendor WRITE, ERASE and RUN are rejected. All three SPM instructions and
  the EEPROM EEPE trigger are replaced with NOP in the generated wrapper.
- The inherited inactivity autojump is disabled; its decision does not
  depend on the contents of an unrelated postscript at `0x07FC`.
- The application permits diagnostic Flash reads through all 8192 bytes.
  Metadata still describes its local `0x0800` origin, so the normal Block64
  programmer's geometry/range checks are unsuitable for those full reads.
- CRC tables occupy `0x1600` and `0x1700`. The body file spans 4096 bytes
  including alignment gaps; this is not a 4096-byte bootloader-size claim.

Private board backups, Flash/EEPROM dumps, restore HEX and hardware logs
must remain outside Git. Any physical trial must restore the backed-up
application and verify EEPROM afterward. Operator instructions must say
explicitly whether RESET or complete USB power removal is required.

## Evidence and remaining defect at the initial V2 checkpoint

V1's shortened EOP path passes 6528 normal/stuffed DATA cases and accepts
9360 legal dribble cases within the deadline, but drops 6288 other legal
dribble cases due to partial-byte CRC pipeline state. It is retained as
experimental history, not a hardware candidate.

The initial direct-EOP V2 source hash is
`1c4ea43d38713247fbee8d04d2310cc318480ce4f07676974a399dca00b48384`.
Its rehearsal body hash is
`3dcfca8e6e73ba1ebed0d7735d6c5da10d1b4f7c785eb3cdba70b595f19b9233`.
It passes 6528 positive frames, 768 targeted stuffing/arrival cases covering
all 40 cooldown sample sites, 41472 payload/trailer bit corruptions, and
48864 short-frame/CRC-counter cases. Varying all non-USB PIND bits does not
change decoding. CRC table arithmetic is independently checked for all
16777216 state/byte pairs.

All 15648 legal cases in the full dribble matrix decode and validate CRC,
but **56 rows remain late**: empty DATA1 plus three extra ones can respond
at 70 cycles, exceeding the detachable-cable 69 1/3-cycle limit. Repeated
empty-pattern rows account for some duplication. This checkpoint must not
be uploaded. The dedicated all-phase empty-tail regression exposes it.

The follow-up source `fcc0ad6f463dd0e133808065e8db3d1aa2e4a1762158666dadfc2231205dbd2c`
moves the unchanged residual comparison immediately after index cleanup.
This saves two clocks on the late path and adds two to the full cleanup,
whose prior worst case had enough margin. The body is
`e5b06459481658af1f0b4296000a97dbd7f0226502caf5dd86c234a4407aba82`.
Sampling code, instruction count and all CRC gates remain unchanged. The
dedicated all-phase empty-tail regression and fast negative tests pass;
the full legal-tail and expanded jitter gates subsequently passed too.

## Completed software and application-only trial

Final body `e5b06459...` passes 6528 positive frames, 768 targeted stuffing
frames, 64 varying-PIND frames, all 15648 legal tails in 22848 total tail
probes, and 11664 source-rate/jitter cases. Legal-tail turnaround is
50 2/3..68 clocks; the rate/jitter maximum is 68 2/3, below the nominal
69 1/3-clock limit. The worst bounded digital margin is 2/3 clock (about
41.7 ns); this is not a measured analog margin.

The exhaustive 41472 corruption and 48864 short-frame matrices ran on
`02ef7948...`, before the same-size inactivity NOP and comparison-tail
relocation. CRC arithmetic, length accounting, pin samples and CRC checks
are unchanged. Final-image fast corruption, random-payload, token
CRC5/address, overflow and malformed-stuffing tests also passed.

On 2026-10-26 the final image was loaded through the installed 1274-byte
Micronucleus+ 2.8 into the application region. Fresh Flash/EEPROM still
matched the verified backup before upload. It enumerated as 3.3, passed
962 memory reads with every length 1..64 plus 64 status polls, and returned
two identical copies of all 8192 Flash bytes. A complete Flash read with
64-byte control requests took 1.27993 seconds in this run. EEPROM matched
its backup and the installed bootloader body hash matched.

The original Lumiere Stereo was then restored through the unchanged old
loader. Two reads of all 6908 application bytes and two reads of all 64
EEPROM bytes matched their backups exactly; the loader accepted the
application-start request. Audio was not evaluated. No NVM programming
request was sent through the diagnostic application. Private backup/restore
material and raw hardware dumps remain outside Git. The maintained
Block64 loader still has its separate nonempty-DATA ACK defect and has not
been installed on the board.

The source's bit periods are 10,10,11/12,11,11,11,11,10 clocks. Checks cover
PID, ordinary, stuffed and cooldown samples, actual transmitted ACK PID,
publication and SE0-to-J EOP through J-to-K SOP. DATA tests accept empty
DATA1 and both DATA PIDs for payload lengths 1..8; inherited empty-DATA0
suppression remains explicit.

The optional source-rate/jitter diagnostics separate nominal/500-ppm host
clock changes from constrained receiver interval jitter. USB frequency error
is already allocated in the jitter budgets. Ideal two-bit SE0 is used;
minimum-width EOP, analog rise/fall, noise, measured oscillator accuracy,
continuous foreground service and electrical USB certification remain
outside these isolated digital traces.

See the [upstream review](../../VUSB_UPSTREAM_REVIEW.md),
[design investigation](../../STREAMING_CRC_DESIGN.md), and
[instruction alternatives](../../INSTRUCTION_OPTIMIZATION_REVIEW.md).
