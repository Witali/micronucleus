# PC-typed phase0 lookahead entry

This is an additive receive-entry experiment, not a USB device, full receive
engine or programmable loader. It has no acquisition, packet publication,
protocol ownership or memory-write implementation. Do not program it onto a board.

The 154-byte body at 0x1800 has SHA-256
`caba7bb6fc8de651156c64956be8740a19f5362562cd12c5f405f38648461b01`.
Actual-five callers use `typed_five_setup` at FIRST-1 or `typed_five_entry`
at FIRST. Actual-six uses its separate `typed_six_entry` at FIRST. The five
entry never infers a six-one run from the retained byte FF. This fixes the
post-stuff case in which five new logical ones leave the true payload/history
byte FF despite the actual run still being only five.

The entry observes FIRST/SECOND at 0/2, 10/12 and 21/23, then joins at 32.
A sixth DATA one shifts at 9 and the mandatory zero is observed at 10,
avoiding the previous phase0 late observation at 11. A DATA zero shifts at
11 after the following FIRST; the subsequent captures remain unchanged.

T exports the continuation class at clock 32: T0 means the DATA-zero path;
T1 means one stuffed zero and the first following DATA bit were consumed,
so four further post-decode history checks may still need suppression.
Marker operations replace existing NOPs and add no clocks or bytes. The
verifier poisons the initial flag to the opposite expected value and checks
837 T0 and 864 T1 exports. The 297 actual-six controls use their separately
typed short continuation and preserve the caller's T.

Run from the Flash-only root with its AVR LLVM toolchain available:

```sh
python3 prototypes/three_phase_rx/typed_entry/verify.py
```

The verifier rebuilds the exact body and checks all 1998 retained legal
controls: 567 fresh-five/sixth-one, 837 fresh-five/DATA-zero, 297 actual-six
and 297 post-cooldown-five cases. Fixtures are synthetic frozen entry states
with explicit provenance; waveforms are rebuilt from source packets and
retain source-rate, periodic-jitter, conditional ownership and SE0/SE1
excursion controls. Fixtures contain no production run-class algorithm.
All generated assembly copies, objects, binaries and reports stay under
ignored `build/typed_entry_component/`.

The retained negative guard truncates genuine-CRC packet `c302c17e` before
mandatory physical39, emits a 10.72-clock EOP, and appends a minimum-gap SETUP
token. This entry rejects at 431.1399991 before SOP 448.0533333 and performs
zero observations during that following token. This is entry rejection,
not proof that a complete loader reacquires and processes that SETUP.

## Ordinary caller integration remains separate

The caller must provide a genuinely known run class. A separate bounded
caller experiment measured fresh phase2's CPI F8 at 29, lookahead CPI FC at 31,
captures at 32/34, SE0 branch35 and five/six branch36. A known fifth post-stuff
cell can instead compare FF at 29 and use its PC-typed-five prefix. Its PC
proves the history age: FF then means five new ones, never already-six.
That caller classification passed the same 1998 inputs, but is not linked
to this marker body by this verifier. Source folding, fresh-caller T
initialization, publication and the remaining complete receiver are unproved.

The current combined receiver uses T for PID-family dispatch. A future
replacement must reconstruct that discriminator from the stored PID before
its old EOF classifier, or replace the classifier. The continuation marker
must also be consumed without appending an unfunded branch before the next
capture. These component results are not whole USB qualification or proof of
the 1280-byte complete-loader objective.
