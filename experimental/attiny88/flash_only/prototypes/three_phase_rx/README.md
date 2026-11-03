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

## Remaining integration work

- Stuff entry is at 11/20/31 clocks, whereas the next normal FIRST would be
  at 10/21/32. Each cold continuation needs an explicit physical schedule.
- Consuming a stuffed zero must preserve the logical rolling byte. Its
  post-decode history checks need a five-cell cooldown before becoming live.
- The normal cells have no free DEC/ST slot. Counting and byte publication
  still need funding, including streams that never stuff.
- Zero-FIRST recovery needs a real crossover/EOP distinction; the RET stub
  does not qualify a packet. Short/fractional EOP and final stuffing remain.
- SYNC normalization, all protocol/ownership checks and the 1280-byte complete
  loader objective remain open.
