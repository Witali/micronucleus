# Shared-recovery PLL correctness reference

This package supplies the shared DATA receiver generator and a fixed, verified
cluster order for the separately built centered PID guard experiment. It is
an offline component, outside selectable firmware variants. There is no packet
publication/count owner, full framing, recovery-J qualification, ACK, release,
hardware validation, or 1280-byte loader claim.

Build the original `prototypes/pll_extra6` first, then create the centered
experiment and this reference from the Flash-only directory:

```sh
python3 tools/probe_pll_pid_guard.py --output-dir build/pll-pid-guard-centered
python3 tools/probe_pll_recovery.py --centered-dir build/pll-pid-guard-centered --output-dir build/pll-shared-recovery
```

Requires Python 3, Clang with AVR target support, LLVM AVR inspection tools,
GNU AVR gcc/ld/objcopy/nm, and the existing pinned independent repository model.
Every output must be a fresh directory below Flash-only `build/`; original
sealed sources, observer, independent model and previous evidence stay intact.
No private path, archive, prebuilt binary or model snapshot is needed.

Expected body: **7346 bytes at 0x0200**, ending at 0x1eb2, SHA-256
`56e8816afe4b42e1a472992eeabe78478bc082e5a6e53d494ec1b58b343a5611`.
GNU and LLVM bytes, physical 8 KiB fit and all named relative edges must agree.
The DATA graph is 6192 bytes, preserving the frozen graph's 42 semantic roots;
the actual centered acquisition/PID prefix adds 1154 bytes. The fixed cluster
order changes placement only. Original generator SHA-256 is
`8a9616f6195955ecb25d8d433e818633c98a7784d1d5ed420703d3431794720d`.

The generated strict verifier accepts no expected rejection of a valid packet:

```sh
python3 build/pll-shared-recovery/verify.py --firmware-root . --suite controls
python3 build/pll-shared-recovery/verify.py --firmware-root . --suite full
python3 build/pll-shared-recovery/verify.py --firmware-root . --suite payloads
python3 build/pll-shared-recovery/verify.py --firmware-root . --suite fractional
python3 build/pll-shared-recovery/verify.py --firmware-root . --suite fractional_min
```

The five suites contain 24, 9984, 2627, 6048 and 6048 positive observations.
Their waveforms and payload/count checks come from the unchanged existing
observer/model. Every bit, actual PID acquisition, real FIRST calendar and
terminal tag are checked; no PC, phase, register or payload state is injected
after entry. Positive suites alone do not establish malformed-prefix rejection
or complete USB conformance. Use the existing PID-prefix and combined
SYNC/first-DATA-edge tools separately, recording the exact body hash.

The exact 7346-byte reference still misses acquisition handoff in **92 of
13464 combined SYNC/first-DATA-edge cases**. Its 24731 original positive cases
pass, but this expanded corpus exposes a remaining late PID7 poll reading a
valid first-DATA SE1 excursion. Preserve the failure evidence and investigate
the guard separately. This package does not relax or waive those failures.

The builder copies the existing GPL-2.0 license and V-USB provenance alongside
the generated derivative. The original PLL package and its historical expected
failures are preserved; their snapshot policy is not reused by this reference.
