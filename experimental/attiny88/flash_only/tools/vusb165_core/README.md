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
