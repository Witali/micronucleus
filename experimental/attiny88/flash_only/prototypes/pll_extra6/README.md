# Offline ATtiny88 PLL acquisition experiment

This is an offline experimental component, not a selectable firmware variant.
It preserves a useful V-USB 12.8 MHz PLL port to the actual 16 MHz ATtiny88
instruction stream and connects its decoded PID to a frozen `EXTRA+6` receiver.
The maintained PHY, profile, default image and CPU/wire model are unchanged.
There is no hardware validation or complete USB implementation in this package.

The emitted component is **5,634 bytes at byte address `0x0800`**, ending at
`0x1e02`. Its instruction-body SHA-256 is
`d668eb3e8b59ecd8a641d77b4a00d38b45326efe9dd607c7d1b0d298b1c1999b`.
The reproducible ELF SHA-256 with the recorded tools is
`1552fe56f8915b26ab8de0f28b8242a6acd3889fe6ea81f705269a175e2596c4`.
Generated PHY source SHA-256 is
`143fc2848f435e9a8324b2538bafeae112ddee87594421be97d5cf25452dd94c`.

## Frozen inputs and dependencies

`inputs.json` pins every assembler/header input. `compose.py` reads only those
files, using the Python standard library; it does not read maintained PHY or
control sources. `build.py` verifies the pins before generating any code.

| Input | Origin and role |
| --- | --- |
| `inputs/pll128-balanced.inc` | Frozen real-entry 16 MHz port of upstream `usbdrvasm128.inc`; includes the actual SYNC front and balanced initial PID clocks. |
| `inputs/extra6.S` | Frozen `extra6-first0` continuous receiver, whose original standalone body was 4,480 bytes, SHA `c54abbad1ab0e178eb0e2193b7bc7ee94be2b43db41efb2ae4815a1102b12a27`. Includes explicit unfinished recovery rejections. |
| `inputs/extra6-manifest.json` | Names the real instructions observed as FIRST, shifts, physical skips, EOF and rejection tags. |
| `inputs/source/*`, `inputs/variants/*`, `inputs/vendor/*` | Frozen hardware/protocol constants and assembler-only AVR I/O subset from firmware commit `6875f32`; LED mode NONE. |
| `model-inputs.json` | Hashes 17 existing independent model/import files. These files are read from the caller-specified repository, never copied into or changed by this tool. |

Primary upstream source is [obdev/v-usb `usbdrvasm128.inc`](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm128.inc),
commit `801242072fa035e1839e3571df0d9a18e9cec95c`, Git blob
`75e119d860697c1cca64d710431eb690973c53ad`, file SHA-256
`7e324e61ac42d9767b2203682dd50330bee0f528ee4debdb721e68996a32ba53`.
The frozen source retains its provenance comment; `LICENSE_GPL-2.0.txt` accompanies
this derivative. Git author/contact metadata and repository history are not
inputs to this package.

Build dependencies are Python 3, Clang with AVR target support, `avr-ld`,
`llvm-nm`, `llvm-objdump`, and `llvm-objcopy`. The recorded build uses Ubuntu
Clang 18.1.3 and GNU AVR ld 2.26.20160125. Verification was run with native
Python 3.14.5; it uses only the standard library and the pinned repository model.
There is no bundled model snapshot. The unchanged backend inheritance is
`flash_only/tests35/ep0_model.CPU` through
`compact/tests27/waveform_model.Timed` to
`attiny88/tests/test_vusb_timing.Timed` and its existing AVR-word decoder.

## Exact reproduction

The intended repository location is
`experimental/attiny88/flash_only/prototypes/pll_extra6`, outside selectable
variants. Run these commands from that directory. In WSL/Linux:

```sh
python3 build.py
```

From that same directory on Windows, the same build is:

```powershell
wsl.exe -d Ubuntu -- python3 build.py
```

The following verification commands run from that same directory; `python`
means the native Python installation. `--firmware-root ../..` identifies the
existing `experimental/attiny88/flash_only` directory with the exact pinned
independent model. A different location can be supplied without changing code.

```powershell
python verify.py --firmware-root ../.. --suite controls
python verify.py --firmware-root ../.. --suite full
python verify.py --firmware-root ../.. --suite payloads
python verify.py --firmware-root ../.. --suite fractional
python verify.py --firmware-root ../.. --suite fractional_min
```

All generated assembly, ELF, binary, source-span audit and detailed execution
reports go under ignored `build/`. `build.py` requires the exact reported body
hash and checks every relative source edge against its linked PC. The audit
contains 988 labels, 2,817 instructions and 943 relative edges; maximum RJMP
span is 1,804 words and maximum conditional branch span is 50 words. This is a
coverage constraint of the current independent executor, which does not model
ATtiny88 modulo-PC wrapping. Valid hardware PC wrapping is not inherently a
linker or firmware defect.

`verify.py` returns success when it reproduces the documented snapshot behavior,
including its known failures and exact failure groups. Every known failure must
contain only an explicit `*_unfunded` rejection and a short count; a wrong-bit,
PID, early-EOF or substitute rejection error cannot keep the total count passing.
The tool checks the sealed package/model hashes and emitted body, ELF, manifest
and source integrity before and after each suite. Its JSON `failures` count is
the qualification result. A known rejection is not a passing USB packet.

## Measured results

| Suite/group | Cases | Failures |
| --- | ---: | ---: |
| Clean controls | 24 | 0 |
| Mixed SE0/SE1 excursions on SYNC edges 5/6 | 3,168 | 0 |
| SYNC corner jitter | 1,848 | 0 |
| One DATA-edge excursion | 4,752 | 261 |
| Excursions on every DATA edge | 216 | 0 |
| All 256 one-byte values at two real entries | 512 | 0 |
| Other payloads, PIDs, tokens, rates and entries | 1,134 | 0 |
| Existing 978 payload crossover cases | 978 | 164 |
| EF next-stuffed-transition ownership witness | 1 | 0 |
| EF/DB current-transition ownership witness | 1 | 1 |
| Adjacent differently placed zero-pulse witness | 1 | 0 |
| Fractional tail/EOP extensions | 6,048 | 0 |
| Fractional tail with 670 ns EOP SE0 | 6,048 | 0 |

The `full` suite is 9,984 cases with 261 failures. `payloads` is 2,627 cases with
165 failures. Every observed failure is an explicit unfinished recovery
rejection plus short bit count. These matrices contain no wrong PID, decoded
payload bit, CRC bit, early EOF tag or missing actual PID-cell-8 acquisition.
The observer compares both transmitted CRC bytes exactly; no observed CRC-bit
mismatch is waived. The component itself does not implement numeric CRC16
validation. `expected-results.json` records the exact original summary and
representative real handoffs.

`fractional` retains `h.Wave`'s nominal two-period SE0 and one-period recovery J.
The separate `fractional_min` suite uses the same image, payloads, rates,
jitter, real entries and sixteen tail extensions, with EOP SE0 set to exactly
10.72 clocks (670 ns at 16 MHz) and recovery J one host period. Each suite has
6,048 cases and zero observed failures. This measures an EOF tag, not a full
EOP qualifier or packet-admission implementation.

The first full-matrix rejection is FF8 DATA `c3fffffffffffffffffe70`, host rate
1,499,250, jitter sign -1, entry 5 clocks, physical transition 27, SE0 fraction
1/21. The actual first-payload origin is 175 clocks, PC state `rx_p2_K_r2`, PID
R18=`0xc3`, previous EXTRA R19=`4`, line constants R20/R21=`2/4`. The graph
reaches `rx_p1_J_r6_inline_60_unfunded` after 18 logical bits. This is a concrete
unfinished mandatory-FIRST recovery route, not an acquisition phase injected
by the test. Detailed samples for each suite's first failure are regenerated
in `build/*-first-failure.json`.

## Runtime acquisition and handoff

The CPU starts at the real `USB_handler` and the supplied cooperative entry
time, including tested entries through 39 clocks after SOP. The front polls
actual PIN bits, guards both differential pins, and uses actual raw samples
and instruction paths. The PLL prefix then decodes all eight PID bits. Its
initial DATA reads occur at 0/11/21 clocks relative to PID0; bit3 joins at 32.
Subsequent phase samples and conditional `LPM r23,Z` delays are actual emitted
GPIO observations and instructions. No timer peripheral or new interrupt is
used. The synchronized PIN aperture remains the model's unchanged half-clock
aperture.

All valid complemented PIDs have four zeros, so the physical line after PID7
is K. Runtime bit6 path ownership and inverse PID5 in `shift` select run2 or
run3 before PID7. The choice uses `CPI shift,32` and a balanced `BRCS` path in
slots formerly occupied by impossible PID-stuff checks. This preserves the
actual PID7 and first-payload deadlines. A last PID zero selects run0. The
decoded PID is not supplied by the observer or host metadata.

The measured entry is phase2 FIRST of the first post-PID physical cell:

| Genuine decoded PID | Entry | Previous physical line/run |
| --- | --- | --- |
| C3 DATA0, D2 ACK | `rx_p2_K_r2` | K, two ones |
| E1 OUT | `rx_p2_K_r3` | K, three ones |
| 4B DATA1, 69 IN, 2D SETUP, 5A NAK, 1E STALL | `rx_p2_K_r0` | K, zero ones |

R18 holds the complete true PID at that FIRST. R20 is J (`2`) and R21 is K
(`4`), initialized in paid instruction slots. For last-PID-one paths, R19 is
the real PID7+6 full-port sample needed by FIRST-only EOF classification.
Last-PID-zero paths do not consult a preceding EXTRA until one has been
captured for a later real DATA one. R16/R17 are receiver scratch; R22/R23 are
prefix scratch. Y points to `0x116`, but this component does not publish bytes.
R18 shifts immediately, so a future byte/publication owner must preserve or
store the decoded PID using a genuinely funded schedule.

The receiver executes a 10/11/11-clock physical-cell calendar selected by its
phase state, with FIRST/SECOND at +0/+2 and real same-line EXTRA at +6. The
observer checks this calendar against actual accumulated instruction clocks;
it never sets PC, clock, phase, run, PID or registers at the handoff. It checks
each real emitted shift against the independent packet bits, preserves the
documented protected registers/configuration, and observes no SRAM publication
or bus drive. Prefix `LPM` explicitly uses R23, preserving R0 and context Z.
SREG.T preservation is tested from T=0; T=1 has not been exercised by these suites.

## Remaining work and proposed repository scope

This component still has unfinished FIRST/zero recovery paths. The ELF contains
debug EOF/reject tags and stub protocol labels. It has no byte counter, SRAM
publication, PID/address admission, complete EOP qualification or ACK/TX owner.
The two 6,048-case fractional suites validate the observed EOF tag and 0..6
trailing dribble ones; they do not establish full firmware packet acceptance, malformed
packet rejection, response timing, electrical compliance or hardware behavior.

A focused experimental preservation commit can contain this directory's
tracked source, pinned inputs, license, manifests, expected summaries and this
report. Exclude `build/`, Python caches, the surrounding prior-study tree,
execution logs and generated binary artifacts. No build or verification step
enables this component as the maintained default. The frozen graph is the
tested `c54abbad` snapshot; later decoder work must receive its own artifact
name and complete rerun rather than silently replacing these inputs.
