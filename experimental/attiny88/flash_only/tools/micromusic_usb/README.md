# MicroMusic USB executor bridge

This bridge replays linked ATtiny88 firmware through MicroMusic's shared AVRe
JavaScript reference executor. It contains no AVR decoder or instruction
implementation. The target profile and register addresses come from MicroMusic's
Microchip ATtiny_DFP 3.4.278 definitions. Every run checks the firmware SHA256 and
records hashes of the MicroMusic CPU, profile and register-map sources.

The companion MicroMusic change adds CBI, SBIC/SBIS and BST/BLD to the shared JS
and C/WASM cores. It also fixes selected-bit SBI/CBI writes to W1C registers and
routes translated SBI/CBI through the same masked-I/O bridge. An older emulator
that lacks an instruction fails explicitly; this tool does not substitute a
second implementation. The reference executor is selected intentionally:
native/WASM currently has no per-instruction ATtiny88 external-pin callback API.
The full-device runtime models ATtiny13A, and cannot be used as an ATtiny88.
Legacy precompiled translations predating masked I/O must be regenerated; their
ABI key is rejected so a stale read/modify/write SBI cannot retain the W1C bug.

## Run

The required shared-core changes are committed in MicroMusic as `8028a449`
on branch `codex/micronucleus-emulator`. Select that checkout or a later
compatible version. The adapter records actual source hashes on every run.

On Windows, one command runs adapter tests, exports AVR/wire fixtures through
WSL and replays them in native Node:

```powershell
./tools/micromusic_usb/verify.ps1 -MicroMusicRoot C:\path\to\MicroMusic -Dense -Jitter
```

Use `-NodePath` when Node is not on PATH, `-Artifact` for frozen metadata,
and `-Distribution` for a WSL distribution other than Ubuntu. The JSON report
is saved under ignored `build/micromusic/report.json`.

Node.js 22 is sufficient for the replay. Python fixture export uses the existing
tests35 assembler/disassembler environment, normally WSL on Windows. Run from
the `flash_only` directory. Keep generated fixtures and reports in `build/` or
another ignored validation directory; they contain local artifact paths.

```sh
export MICROMUSIC_ROOT=/path/to/MicroMusic
node --test tools/micromusic_usb/adapter.test.mjs
python3 tools/micromusic_usb/export_fixtures.py --output build/micromusic-smoke.json
node tools/micromusic_usb/verify.mjs build/micromusic-smoke.json
```

Use `--artifact frozen-artifact.json` to select an immutable build and `--dense`
for the 1,499,250 / 1,500,000 / 1,500,750 bit/s and five-entry-phase matrix.
Add `--jitter` to reuse the certified 75/45 ns next/paired-edge corner fixtures.
The metadata requires `boot`, `obj`, `bin`, `size`, `sha256` and `symbols`; `bin`
contains only the linked bootloader body. Node on Windows also accepts the
`/mnt/c/...` paths produced by the WSL builder. In PowerShell set the checkout
with `$env:MICROMUSIC_ROOT='C:\path\to\MicroMusic'` before the Node commands.

The export covers token address/endpoint/CRC5 authorization, short and ordinary
EOPs, DATA publication, malformed tails/truncation and ACK ownership. Verification
compares full handler completion time, all registers and SREG, USB context/RX
memory, PIN observations, accepted-handler checkpoints and GPIO transitions.
`run.mjs request.json` provides lower-level single or batch replay; its output
also contains every GPIO write and PCIF W1C event.

These are executor parity checks. A shared firmware defect can pass parity, so
the USB acceptance, framing, crossover, receiver-jitter and turnaround oracles
remain mandatory. This bridge does not declare any candidate USB compliant.

## Explicit digital timing contract

The CPU runs at 16 MHz, with word-addressed PC and a real ATtiny88 SRAM stack.
Fast blocks and idle acceleration are disabled so every I/O instruction is
observed. The handler starts at the fixture's `entry` cycle and must return
with the stack balanced.

For PIN reads, Microchip doc8008H Figure 10-4 shows an IN beginning on the rising
edge that updates PINxn, with the source latched at the preceding falling edge.
Consequently an IN starting at cycle `n` reads the external line at `n - 0.5`.
MicroMusic invokes its read hook after `clock(1)`, so the adapter retains the
instruction-start time. This is a causal input-pipeline model, not a fitted
phase offset. OUT writes occur at its ending edge; SBI/CBI write after two
cycles. The configurable aperture defaults to `-1e-7` cycle to order an exact
boundary explicitly.

The limited polled PCINT18 model compares the direct PD2 input at rising edge
`n` with the previous pin synchronizer input at `n - 1.5`; a difference schedules
a flag-set event at `n + 2`. Events pending in that pipeline survive a W1C.
`flagPriority: "clear"` and `"set"` explicitly select same-edge W1C ordering.
Default `flagDriver: "external"` matches the existing Python fixture, which
feeds PCINT from host edges only; `"combined"` includes device-driven edges.
That latter mode is a separate fixture assumption, not equivalent coverage.
PIN samples always combine host input with DDRD/PORTD output. The adapter
supports only PD2's PCINT group and polled operation with global interrupts
disabled; unsupported PCINT ISR entry fails.

The bridge deliberately does not implement SPM, fuse access or EEPROM
programming, and those operations fail. It cannot prove flash-programming
latency, analog thresholds, rise/fall times, metastability, differential
receiver behavior, oscillator tolerance or the physical priority of a
simultaneous set/clear. It performs no hardware access.

## Reproduction evidence

Initial independent parity used the frozen `physical_early1` body, 1,620 bytes
at `0x1900`, SHA256
`796260250eacd27c22420ffab5ec2efbab38e327fb7908f5f1773766c4a57703`.
The 247-case smoke, 1,781-case dense and 5,561-case dense-plus-jitter matrices
matched the corrected Python executor exactly.
That candidate retains a separately recorded partial-token crossover defect;
parity does not erase it. The MicroMusic isolated branch began at `22e50e01`.

The subsequent frozen `partial_early1_combined` body, 1,654 bytes at temporary
`0x1800`, SHA256
`64a69843758e7b4aed2f2ac499a2d9d6506599e22a16b609f6ecf45516f764f3`,
also matched all 5,561 dense-plus-jitter comparisons. Its independent existing
oracles passed 6,185 DATA framing, 11,475 token-tail/authorization, 5,454
malformed-token crossover, 1,520 PID, 3,882 raw/stuffing/EOP and 2,016 certified
receiver-jitter cases. Private DATA framing now bypasses the former generic
framing label; the raw observer watches its actual full-frame exit, and PID
authorization is checked by accepted effects rather than a pre-validation
dispatcher label. Exact decoded-byte/count assertions remain in place.
A separate 9,072-case DATA-tail/response sweep still found one missed legal
670 ns EOP on this image. Executor parity does not close that receive defect.
The conservative recovered-nonzero crossover path can still discard a valid
packet; these results do not establish full physical receiver qualification.

MicroMusic validation passed 211 focused JS/WASM/translated/profile/system
tests. Independent review also exercised 1,440 skip, two-word and Flash-wrap
cases. The W1C correction includes EECR command masks: clearing EERE must not
renew an unselected EEMPE four-cycle authorization window.

Primary references: Microchip [ATtiny48/88 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf),
Figure 10-4 and register-summary note 3 (SBI/CBI affect only the selected bit),
and AVR Instruction Set Manual DS40002198A. MicroMusic retains its original
source, device-definition provenance and licenses; no emulator source is copied
into this repository.
