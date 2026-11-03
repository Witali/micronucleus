# Three-phase normal receive-loop probe

This is a component experiment for a smaller erasure-tolerant DATA receiver.
It is not a bootloader, does not implement a USB device, and must not be
programmed onto a board. Cold stuffing/EOP branches end in test-only RETs.

The ordinary cell compares the preceding SECOND observation with the current
FIRST. Three registers rotate roles, avoiding a per-cell MOV. The history
conditional branch also provides the normal loop edge: phase zero falls
through in ten clocks, phases one and two branch in eleven clocks each.
FIRST reads occur at 0/10/21/32/42/53/64; SECOND is two clocks later. The whole
linked fixture, including stop stubs, is 68 bytes, SHA256
`c4dcd6562d10d608964b74c0a669a4abaf0358d2d75d5d9c8dd7eda46a8bbd9e`.

The original emitted-instruction sweep checked all 4096 twelve-bit patterns
with four unrelated-pin noise sequences: 16384 cases, 176768 intercell
boundaries and 896 six-one exits. It checks real carry/SREG execution,
history values, raw role handoff, sample clocks and untouched live registers.
This does not prove acquisition or analog tolerance. The cadence matches the
previous independent 774-context normal-grid screen; its phase assumptions
still require a valid SYNC acquisition mechanism.

From the Flash-only directory, with the usual LLVM AVR tools available:

```sh
python3 prototypes/three_phase_rx/verify.py
python3 prototypes/three_phase_rx/verify.py --patterns 32
```

Builds and reports remain in ignored `build/`. The second command is only a
128-case smoke run; it is not the full sweep.

## Deferred publication and byte-limit probe

The separate `verify_publication.py` experiment funds storage even for streams
that never stuff. It is inspired by the deferred store after the next bit0
sample in [USBtiny's receiver](https://github.com/rgwan/USBtiny/blob/6895f68e2bbfbd90287eb654abc3c5a70027148f/usbtiny/int.S#L143-L218).
Its 12 MHz schedule and bit1-only EOP observation do not establish our
16 MHz, minimum-width EOP or crossover requirements.

The last completed-byte test admits history below F0, proving at most three
trailing ones. The next two logical cells cannot require stuffing. Their
retired history tests fund `ST Y+,R18` before the next ROR and count handling.
FIRST/SECOND remain at their existing clocks; ST starts at FIRST+4 and ends
at FIRST+6. R23 holds remaining+7F (8A for eleven bytes, 7F when full). Where
DEC flags are overwritten by decoding, the continuation tests R23 bit7 directly.
The agreed R0/R1, R20-R22, cached R24, live R25 and context Z remain untouched.

```sh
python3 prototypes/three_phase_rx/verify_publication.py
```

The generator, `publication_schedule.py`, keeps all generated assembly, ELF,
body, layout, disassembly and reports under ignored `build/raw_publication_probe/`.
The emitted fixture is **520 bytes**, SHA256
`9acb54d3b75fa0417b61144b1bb0bd6a902bdc0e030a9f813fc40b6acf07e984`.
It uses 24 explicit cell states and is larger than the ordinary loop above:
this proves cycle funding, rather than a complete-loader size reduction.
Fourteen folded fallthrough groups retain short AVR branches without adding
normal-path jumps.

The verifier preserves 2112 publication/count cases, 18 deferred-history cases
and 96 boundary-cold cases. It checks 12672 exact stores, 88704 decoded cells,
all three phases, remaining counts 1..11, actual FIRST/SECOND/ST clocks,
untouched live owners and no twelfth store. All four two-bit full tails are
checked; only the two-one tail reaches the test-only positive classifier.

Full dispatch occurs 22/23/22 clocks after the final publication-boundary
FIRST for entry phases 0/1/2, one clock beyond the next ordinary FIRST.
The test-only tail classifier finishes at 24..26 clocks. A real terminal
continuation still needs those measured entry credits and the corresponding
latest SECOND roles R17/R16/R19. Cold RET stubs merge origins; a real EOP
handler must also distinguish a pending unstored byte from a partial next byte.
Stuffing/EOP/acquisition, malformed-frame recovery and packet authorization
remain unimplemented here. The ordinary 16384-case sweep is separate.

## Remaining integration work

- Stuff entry is at 11/20/31 clocks, whereas the next normal FIRST would be
  at 10/21/32. Each cold continuation needs an explicit physical schedule.
- Consuming a stuffed zero must preserve the logical rolling byte. Its
  post-decode history checks need a five-cell cooldown before becoming live.
- The F0 experiment funds counting/publication by unrolling. A compact shared
  version and its cold continuations still require implementation.
- Zero-FIRST recovery needs a real crossover/EOP distinction; the RET stub
  does not qualify a packet. Short/fractional EOP and final stuffing remain.
- SYNC normalization, all protocol/ownership checks and the 1280-byte complete
  loader objective remain open.
