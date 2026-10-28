# Reproducible historical USB audits

These tools execute historical AVR instructions with the maintained
`tests35.ep0_model`, synchronized PIN/PCINT model and independent USB wire
fixtures. They record defects as **historical observations**, not as relaxed
expectations for the modern receiver. They do not access a board, execute a
programmer, modify firmware sources or measure analog USB behavior.

From `experimental/attiny88/flash_only`, with Python 3.10 or newer:

```console
python tools/historical_usb/audit.py
python tools/historical_usb/audit.py --full-tail-matrix
```

The JSON defaults to ignored `build/historical_usb/results.json`. The default
run includes 15 token cases, lost-ACK and prepared-address traces, SETUP DATA
PIDs, every mandatory stuffed-zero corruption in DATA0 `FF` × 8, ACK dribble,
representative malformed DATA endings, 162 EOP/rate/entry cases and 72 bounded
crossover observations. `--full-tail-matrix` adds 6,120 valid-CRC DATA ending
and partial-tail cases. Positive controls and image integrity must pass;
malformed-packet behavior is reported rather than declared USB compliant.

## Exact compact 3.0 image

The default target is the already tracked
[Pass27 no-LED body](../../../compact/firmware27/Pass27_off_body.bin):
1,148 bytes at `0x1B80`, SHA256
`e2a771412dfacf7a3ad7575d4ccb526791557c157633637ecf0c7fdbb9096df0`.
This is the public image recorded as installed on 2026-10-27. It is not a claim
about the board's present contents. No private Flash/EEPROM dump is required.

`compact30_symbols.json` comes from the exact linked no-LED rebuild of commit
`e405ea7f31d308d68167f5adb4d27474f0d8aa98`. Its nine source hashes match the
[public manifest](../../../compact/firmware27/manifest.json), and its emitted
body matches the mandatory installed SHA. Current `compact/source` contains
later changes and must not replace this historical image. The fixture supplies
symbols directly, so this target needs no Git checkout indirection, WSL path,
ELF, compiler or external disassembler at runtime.

Observed gaps include accepting bad token CRC5/endpoint/length, freeing an IN
reply before ACK, committing the pending address before ACK, acknowledging
SETUP DATA1 and corrupt stuffed symbols, accepting illegal partial tails and
missing the 670 ns EOP cases. Foreign-address rejection has positive controls.
The accepted historical omission of numeric incoming DATA CRC16 validation is
separate from these framing, token and retry findings.

## Optional official Micronucleus v2.6 comparison

```console
python tools/historical_usb/audit.py --upstream-artifact build/historical_usb/upstream26/artifact.json
```

The artifact must contain a 1,332-byte no-LED `.text` body at `0x1A40`, SHA256
`ec361683baa476be66826c884f2f3759b63451225a35d40a5318d8d1f8ce24bf`.
Metadata supplies `boot`, `sha256`, `bin` and `symbols`; `bin` is normally
relative to the metadata file. SRAM symbols must be data addresses such as
`0x100`, with the ELF `0x800000` tag removed. Constructor-only aliases are
added by the adapter; original instructions are unchanged.

The optional preparation tool uses existing `make`, `avr-gcc`, `avr-objcopy`
and `avr-objdump`. It installs no packages. The audited build used AVR-GCC
7.3.0; a different emitted body is rejected rather than silently substituted.
Choose either an existing public archive or an explicit download:

```console
python3 tools/historical_usb/prepare_upstream.py --archive /path/to/upstream-v2.6.zip
python3 tools/historical_usb/prepare_upstream.py --download
```

Preparation stays under ignored `build/historical_usb/upstream26`, checks ZIP
and source hashes, rejects unsafe archive members, changes only
`LED_MODE ACTIVE_HIGH` to `NONE`, invokes `make CONFIG=t88_default main.bin`
and extracts `.text`. `main.bin` is an ELF despite its extension. Existing
nonempty output is never overwritten; `--output-dir` can choose another child
of `build/historical_usb`. No flash, fuse, upgrade or installation target runs.

The [official v2.6 tag](https://github.com/micronucleus/micronucleus/releases/tag/v2.6)
is commit `882e7b4af38cb2795353e4e99336616963c6cd12`. The earlier supplied
comparison export is `4dd1b49f39cd9d6fc736a720777ed62f4564e0e2`, not that tag.
Its relevant firmware sources match after CRLF normalization; the README
differs. `upstream26_provenance.json` preserves both identities and source/ZIP
hashes. No upstream archive or body is duplicated in the maintained tool tree.

The optional audit executes the original assembly receiver/serializer only.
It includes token/address controls, malformed lengths, stuffing/dribble,
short EOP, lost ACK, prepared pending address and the focused possible 210 ns
crossover counterexample. **Do not infer a Flash write from a short SETUP's
assembly RX publication:** original `usbdrv.c` separately rejects a SETUP
payload whose length is not eight bytes. The foreground C request dispatcher
is not executed by this audit.

All timing is digital at 16 MHz. A possible PIN=00 excursion at a differential
crossover is a conservative observation envelope, not a measured board
threshold sequence. Reports separate source SE0, driven-J ownership and
turnaround; no full USB-IF, oscillator or arbitrary-jitter-history claim follows.
