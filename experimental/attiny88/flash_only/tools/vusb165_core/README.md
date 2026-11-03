# Pinned V-USB receive-core experiment

These host tools generate and execute an experimental **286-byte RX component**.
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
  --output build/vusb165-core/receiver.S
python3 tools/vusb165_core/verify.py \
  --source build/vusb165-core/receiver.S \
  --output build/vusb165-core/basic \
  --expected-sha256 db2d8a08e86b493754890072b864e77039a93f7993269cbccf66430303b32d55
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
  --source build/vusb165-core/receiver.S \
  --output build/vusb165-core/all-values \
  --all-byte-values \
  --expected-sha256 db2d8a08e86b493754890072b864e77039a93f7993269cbccf66430303b32d55
```

## Current evidence and open failure

The R23 body is 286 bytes at component placement `0x1B00`, SHA256
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

The basic 630-case command exits successfully. The 2934-case expanded command
currently exits with failure and records all nine cases. Do not add expected
failure exceptions or call this a qualified receiver. The JSON keeps exact body,
source and model hashes and the test scope. It is written beside the linked
object and body binary under the selected output directory.

Mixed erasure polarities, aperiodic jitter, arbitrary packet shapes, malformed
stuffed symbols, minimum-width EOP, protocol effects and physical hardware
remain outside this bounded component matrix. A per-delta guard is not a proof
that all retained phase inputs are unambiguous under every such waveform.
