# Pinned V-USB receive-core experiment

These host tools generate and execute an experimental RX component. The current
stronger option is **288 bytes** with `--stuff4-delay`; omitting that option
retains the historical **286-byte control** unchanged.
This is not a bootloader or a programming image. SYNC acquisition, qualified
EOP/malformed-tail handling, token/CRC5/ACK ownership, protocol, TX and Flash
operations are absent. No hardware is accessed.

The generator takes the original
[`usbdrv/usbdrvasm165.inc`](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm165.inc)
from upstream commit `801242072fa035e1839e3571df0d9a18e9cec95c`. Its SHA256 is
`c49621176e700f98162c3db66fe49d110e471a6d984731f5cd314fe643119780`;
Git blob is `fb79742794342b2a453ab22c2913e09bb6dfc468`.
Both hashes are checked before generation. Upstream assembly is not vendored
here. The original copyright and GPLv2/GPLv3/commercial licensing remain
applicable to generated derivatives.

## Generation and execution

Run from `experimental/attiny88/flash_only` with Python 3.10 or later and the
existing AVR Clang, AVR binutils and LLVM tools available on PATH:

```sh
python3 tools/vusb165_core/generate.py \
  --input /path/to/usbdrvasm165.inc \
  --stuff4-delay \
  --output build/vusb165-core/current/receiver.S
python3 tools/vusb165_core/verify.py \
  --source build/vusb165-core/current/receiver.S \
  --output build/vusb165-core/current/basic \
  --expected-sha256 30e1e209ef78726a22eb00f4ce95b2a9c62eaf2848ceb5e765c541fc4345a6b3
```

An explicit `--download` can replace `--input`; it downloads only the pinned
public URL and still verifies both hashes. The default raw scratch is R23.
`--raw-register 0` is retained only for reproducing the frozen R0 control.
The verifier's `--root` can select another repository Flash-only directory.

The core observes the actual emitted opcodes through the maintained independent
executor and GPIO model. Its first normal observation is deliberately centered;
this supplies no evidence that a real SYNC acquisition reaches that phase.
The ordinary PLL byte periods are 85 or 86 clocks at 16 MHz. Optional delay
uses a **two-clock RJMP**, not an implicit LPM that would overwrite foreground
CRC R0. R0, cached token R24 and CRC-high R25 are checked after every instruction
in the R23 variant.

The basic command checks 585 retained cases and 45 additional pristine controls.
To include every repeated byte value at the same three host rates and three
periodic jitter signs, use a separate output directory:

```sh
python3 tools/vusb165_core/verify.py \
  --source build/vusb165-core/current/receiver.S \
  --output build/vusb165-core/current/all-values \
  --all-byte-values \
  --expected-sha256 30e1e209ef78726a22eb00f4ce95b2a9c62eaf2848ceb5e765c541fc4345a6b3
```

## Current evidence and historical control

The current R23 option is **288 bytes**, SHA256
`30e1e209ef78726a22eb00f4ce95b2a9c62eaf2848ceb5e765c541fc4345a6b3`.
It adds exactly one NOP after `unstuff4`'s already-timed GPIO read and history
correction, before the continuation jump. The earlier read is unchanged.
This fixes the short 95-clock BF byte path while preserving live registers.

The recorded stages pass all nine original BF witnesses, all 630 retained
controls and all 2304 pristine byte-value cases. The expanded command above
reproduces the 630 + 2304 checks; the nine dedicated witnesses are also covered
by the all-value matrix. These are centered-entry component results only.

For the historical control, omit `--stuff4-delay` at generation and use the
R23 control hash below with the same verifier. The generator's default remains
the historical variant, so existing source generation is reproducible.

The historical R23 body is 286 bytes at component placement `0x1B00`, SHA256
`db2d8a08e86b493754890072b864e77039a93f7993269cbccf66430303b32d55`.
The R0 control remains 286 bytes, SHA256
`096a39e67f9de6f9d2c67c9d9df8e294faf4071d49565b9aec3aa754c74978a2`.

- 45/45 original pristine streams pass.
- 270/270 single-crossover streams pass.
- 270/270 repeated-crossover streams pass.
- 45/45 extra pristine streams (`55`, `AA`, `42`, `03`, `FC`) pass.
- The expanded 2304-case pristine byte-value matrix fails **nine BF streams**,
  one at each host-rate/jitter-sign corner. Both R0 and R23 bodies have identical
  publications and periods in those nine cases; this is not a remap regression.

The first pristine BF witness uses 1,499,250 bit/s and jitter sign -1. It
publishes `bfbfbfbfbf9f5f7f7f7f7f` instead of eleven BF bytes.

For the historical 286-byte control, the basic 630-case check passes and the
2934-case expansion records the nine BF failures. The 288-byte option fixes
those witnesses and preserves all retained controls. Do not add expected-failure
exceptions or call either variant a qualified receiver. The JSON keeps exact body,
source and model hashes and the test scope. It is written beside the linked
object and body binary under the selected output directory.

Mixed erasure polarities, aperiodic jitter, arbitrary packet shapes, malformed
stuffed symbols, minimum-width EOP, protocol effects and physical hardware
remain outside this bounded component matrix. A per-delta guard is not a proof
that all retained phase inputs are unambiguous under every such waveform.


## Exact-clock bounded publication option

The R23 `--stuff4-delay --pointer-bound` option replaces the byte decrement
and underflow branch at bit2 with an SRAM-pointer compare and upper-bound
branch at the same instruction clocks. It remains 288 bytes, SHA256
`2cc5de3cbf7a1c0072ea92fc63a72e4dca7e5cd6987bcfce520d5d98903a9959`.
The default historical and 288-byte unbounded options remain unchanged.

The caller starts Y at `0x115` only to write back the existing configuration
byte through the initial dummy publication; it must preload correction XOR
shift so that this store preserves that byte. Actual RX storage is
`0x116..0x120`, with exclusive end `0x121`. An overlength source reaches
`overflow` before any store to `0x121`. R22 is no longer modified, so it is
available to a future framer. R0, R1, R2..R15, R22, R24, R25 and context Z
are checked after each executed opcode.

```sh
python3 tools/vusb165_core/generate.py \
  --input /path/to/usbdrvasm165.inc \
  --stuff4-delay --pointer-bound \
  --output build/vusb165-core/pointer/receiver.S
python3 tools/vusb165_core/verify_bound.py \
  --source build/vusb165-core/pointer/receiver.S \
  --output build/vusb165-core/pointer/bound-check \
  --all-byte-values \
  --expected-sha256 2cc5de3cbf7a1c0072ea92fc63a72e4dca7e5cd6987bcfce520d5d98903a9959
```

The expanded check executes 2934 overlength-stream cases: 630 retained
rate/jitter/SE0/SE1 controls and 2304 pristine byte-value cases. Every case
must publish eleven exact bytes, preserve configuration `0x115`, keep Y at
`0x121`, preserve the protected registers/context and return through overflow
with all following canaries unchanged. Without `--all-byte-values`, it runs
the 630 retained controls. Generated objects, binaries and reports belong
under ignored `build/` output.

The overflow assertion requires the named bit2 upper-bound branch as its
actual predecessor. An early SE0 branch to the same component RET cannot
substitute for the buffer-ceiling proof.

The measured private audit also compared 270 baseline/bounded observation
prefixes: each PIN read had the same clock, PC and raw level, and publication
bytes matched. A future qualified framer can inline `mov r23,r28` followed by
`subi r23,0x16` to derive length in two clocks/four bytes while preserving Y,
Z and a raw recovery-J sample in R21. This is conditional interface evidence:
the missing caller must establish nonempty, exact framing, legal final stuff
and dribble, a valid EOP and live recovery J before entering protocol logic.
This option does not make the inherited bit1-only SE0 probe a qualified
receiver and must not be used as a hardware programming image.

## Conditional entry-phase and line-polarity checks

`verify.py` accepts repeated `--phase-offset` values in CPU clocks and
`--both-line-polarities`. An offset shifts every physical input boundary;
it does not adjust CPU instruction time. A negative offset starts the core
later relative to the symbols. Swapping J/K changes the initial previous-line
state too, while transient SE0/SE1 levels remain unchanged. With no options,
the original centered, single-polarity command is preserved.

The following screen uses the unbounded 288-byte control, not pointer mode:

```sh
python3 tools/vusb165_core/verify.py \
  --source build/vusb165-core/current/receiver.S \
  --output build/vusb165-core/phase-screen \
  --phase-offset=-2 --phase-offset=-1 --phase-offset=-0.5 \
  --phase-offset=0 --phase-offset=0.25 --both-line-polarities \
  --expected-sha256 30e1e209ef78726a22eb00f4ce95b2a9c62eaf2848ceb5e765c541fc4345a6b3
```

It executes 6300 cases and currently exits with failure: 202 single/repeated
erasure cases fail at the three negative offsets. The tested 0 and +0.25
points pass all 1260 cases each. Clean periodic streams alone give a much
wider apparent window; that does not establish erasure tolerance. These are
finite phase points, not a proof of the entire interval or of real SYNC
acquisition. The tool records every failure without expected-failure waivers.
