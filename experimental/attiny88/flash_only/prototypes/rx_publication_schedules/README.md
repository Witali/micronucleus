# Isolated RX byte-publication schedules

This offline prototype proves selected emitted AVR instruction schedules for
byte publication in the three-phase EXTRA6 receiver design. It is not production
firmware, a complete USB receiver, or part of the full receiver gate. Do not flash
the generated image onto hardware.

The generated image is immutable: **4,328 bytes**, SHA-256
`1db596fefa080b8fe016284bd0792cd132d231ba7d55c33fbf1de63f0c4504aa`.
Both builders must reproduce those exact bytes; changing the expected digest
requires a separate new proof rather than silently accepting a changed fixture.
The source package contains no generated binaries or private validation inputs.

Place this directory at `flash_only/prototypes/rx_publication_schedules`.
With Python 3.10+, Clang with AVR support, LLVM binary tools, and GNU AVR tools
on PATH, run:

```sh
python3 build.py
python3 verify.py --firmware-root ../..
```

`--firmware-root` points to the existing `flash_only` directory, relative to this
script directory unless absolute. An optional `--output-dir` is resolved relative
to the process working directory. Generated source, manifest, ELF, binary,
independent GNU rebuild, and JSON results remain under ignored `build/` by default.
No maintained source, model, or oracle is modified. `generate.py --output-dir DIR`
can emit just the assembly and manifest. No copied base generator is needed.

The fixture covers final DATA zero in phases 0, 1, and 2 with prior run 0..5,
and final DATA one in phases 1 and 2 with prior run 1..5. It deliberately omits
final-one/phase-zero and final-one/run-zero entries. PC records the canonical
NRZI line, run, and fractional phase; R20 and R21 hold J and K. R18 holds a byte
sentinel or the completed byte, R23 preserves the completed byte, and Y points to
the next private packet-buffer byte. These schedules do not enforce a packet
buffer bound.

The verifier independently rebuilds the emitted source with GNU AVR tools and
checks all relative transfer destinations modulo the ATtiny88's 8 KiB Flash.
There are no wrapped transfers in this image. It executes actual linked words
against the repository's unchanged digital AVR/GPIO model. The unit input is an
explicit raw PINB sequence, with unrelated GPIO bits varied independently.

The expected result is 15,936 completed-byte controls, 15,936 non-completion
controls, and 224 negative controls, with zero failures. Both initial values of
SREG.T and two unrelated-pin noise sequences are checked. Checks include physical
FIRST clocks, PC phase/line/run, ordinary-one SECOND and EXTRA at +2/+6, exactly
one completed-byte store or no store, the original stored value, the new sentinel
prefix, preserved registers/T/SRAM/stack, and no GPIO output side effects. Results
record SHA-256 hashes of package sources, generated source/manifest, the binary,
and every imported model or supporting module under the firmware's parent tree.
These hashes identify the exact proof inputs; package sources, linked artifacts
and imported model files must also remain unchanged throughout the audit.
A different model hash is a different qualification basis.

Carry requires explicit PC provenance. The old sentinel leaves C=1 when a byte
completes. LDI reseeding preserves that C=1: `seed_one`, `seed_zero`, `seed_empty`,
and `retain_one` stops still have C=1. A genuine following logical shift retires
the stale completion carry and leaves C=0 for these short prefixes. A mandatory
stuffed symbol does not shift the sentinel. A caller must not interpret the old
C after an LDI as a fresh byte-completion indication.

The negative unit tags are explicitly **unqualified EOP/outside-contract stops**.
They authorize no ACK or state change. This package provides no wire/SYNC proof,
210 ns crossover qualification, EOP/dribble admission, minimum next-packet gap,
payload/count bound, transaction ownership, retry, interrupt, or SPM guarantee.
The incomplete unit entry set must not replace any full receiver oracle.
