# External software Low-Speed USB review

Reviewed on 2026-11-03 for the ATtiny88, 16 MHz, no-LED, 1280-byte objective.
The review uses original source and author documentation. Reported upstream
sizes are not measurements of our complete loader. Current firmware remains
1768 bytes for the default control and 1936 bytes for the improved ACK variant;
both retain mandatory receive findings.

The [source index](../tools/external_usb/SOURCES.tsv) pins fourteen inspected
files by commit, Git blob and SHA256. Original source stays in local/ignored
reference caches. This review does not replace protocol tests or change the
sole incoming numeric DATA CRC16 waiver.

## Sources and useful mechanisms

| Source | Useful mechanism | Transfer limit |
| --- | --- | --- |
| [USBtiny AVR receiver](https://github.com/rgwan/USBtiny/blob/6895f68e2bbfbd90287eb654abc3c5a70027148f/usbtiny/int.S) | Store the completed byte after observing the next bit0; place byte-limit accounting inside the unrolled receive schedule. | Native 12 MHz/eight-clock cells. Its bit1-only EOP probe and ACK handling do not satisfy our current requirements unchanged. |
| [V-USB 16.5 MHz receiver](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm165.inc), [12.8 MHz receiver](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm128.inc) | Additional phase observations and conditional delays form a software phase-locked receiver. Window masks also supply the stuffing branch condition while a correction byte preserves payload bits. | These clocks and phase assumptions differ from our 16 MHz target. Erasures must not corrupt either DATA or phase evidence. |
| [RV003USB](https://github.com/cnlohr/rv003usb/tree/16d5cd488279659e51e28dcf37d6fe9c1cac9ca3) | Separate coarse/fine SYNC acquisition, ordinary/stuffed paths and in-line CRC work. | RISC-V timing, registers, compressed instructions and interrupt entry cannot be copied as AVR cycle counts. Its README's 1920-byte bootloader figure is a different complete target. |
| [vmeiosis](https://github.com/russdill/vmeiosis/tree/6a9778c8d098b33361a52939aa7dc21bc3e6f31d) | Cooperative V-USB entry and sharing USB functions with a cooperating application. | The reported 348-byte overhead is the difference after application/loader sharing; the cited loader itself is 1614 bytes. Sharing alone does not prove a standalone 1280-byte loader. |
| [STM8S-USB](https://github.com/ZiB/STM8S-USB/tree/1844b1bc4d40433e264c68cd51c8f76a3d349eb6), [author's receiver explanation](https://ziblog.ru/2014/02/22/programmnyiy-usb-na-stm8-chast-2.html) | Hardware-timed compensation for variable interrupt latency before sampling. | The author explicitly describes incomplete stuffing/protocol support. The STM8 timer/pin routing and instruction pipeline differ from ATtiny88. |

USBtiny's [README](https://github.com/rgwan/USBtiny/blob/6895f68e2bbfbd90287eb654abc3c5a70027148f/README)
estimates 1250–1350 bytes for its USB driver, excluding optional strings. Its
token handler checks the seven-bit address before replying to IN, without our
endpoint/CRC5 admission gate there. It ignores received handshakes. We must
retain our durable status-ACK, retry and pending-address ownership rules.

The vmeiosis tree pins its V-USB submodule at
`f2fc5347d8977016119c02551a4630f5f5402357`; the later fork head was inspected
separately. These refs are distinguished in the source index.

The [18 MHz CRC receiver](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm18-crc.inc)
spreads table-driven CRC work across bit slots. Its extra clock budget and
tables do not give a table-free saving on this 16 MHz target. No CRC table was
added. The already present V-USB 16 MHz family remains a historical baseline;
the useful new investigation is its other receiver representations and phase
mechanisms, rather than importing the same 16 MHz code again.

## Emitted-code checks

### USBtiny's byte-boundary shortcut

The pinned receive/stuffing excerpt was compiled and executed at its native
12 MHz with an ideally centered PID entry, five packet shapes, three host
rates and three sampling origins. GPIO pin mapping and GNU instruction aliases
are the only adaptations. The 236-byte fixture is not a complete stack.

All 45 nominal two-bit EOP controls and all 45 full-width controls decode
correctly. All 45 minimum observed 670 ns EOP cases miss the packet ending.
At 12 MHz that minimum is 8.04 clocks; the late bit1 probe can already observe
recovery J. The [maintained auditor](../tools/external_usb/README.md) verifies
the original Git blob and returns nonzero for these receiver failures. The
IRQ/prologue, higher protocol and hardware electrical behavior are outside
this particular component test.

### Smaller V-USB-derived phase receiver

A private original core excerpt is 290 bytes, with 87/89-clock byte periods.
At 16 MHz, eight nominal bits occupy 85 1/3 clocks. Retiming the actual code
produced a stronger 286-byte component with 84/86-clock alternatives:

- 45/45 pristine patterned streams pass.
- 270/270 single-crossover cases pass.
- 251/270 repeated-crossover cases pass; 19 remain failures.

Its SHA256 is
`466717422dfd1f915ff8a66a6b04cc32729e7693a01e5bdeeadccc327bc54391`.
This component includes byte publication and stuffers, but lacks complete
SYNC/EOP qualification and protocol integration. Thirteen failures first alter
the phase vote, and six first alter an ordinary DATA observation. A same-size
parity-vote experiment regressed to 188/585 failures and was rejected.

A deterministic 85/85/86 byte calendar also failed: 125/585 cases, including
four pristine cases. Correct average rate alone does not prove within-byte
ownership. No tested replacement was installed in the active receiver.

### Applying the deferred-store idea

Our independent [three-phase experiment](../prototypes/three_phase_rx/README.md)
keeps the completed byte in R18 until ST occurs before the next data shift.
If its recent history is below F0, the next two logical cells cannot need a
stuffed symbol. Their retired history tests can fund ST and byte-limit work
while preserving the 10/11/11 capture schedule. This is a scheduling proof;
sharing the resulting state graph and qualifying its cold/terminal paths
remain necessary before replacing the current firmware.

## Reuse constraints and next implementation work

An interrupt-driven AVR stack is not a direct entry replacement here. The
[ATtiny48/88 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf)
lists PCINT2 at program word 0x005 (byte 0x000A), printed page 52, and reserved
MCUCR bits rather than IVSEL/IVCE on page 40. Our RESET-only application
contract preserves that application-owned vector. A bounded vector-routing
check confirmed it in 24 fixtures; no application vector was patched.

The next useful steps are erasure-safe phase evidence for the small receiver,
compact byte publication, and early recovery from partial packets. Every
candidate must retain exact PID/payload/count, mandatory stuffing, short EOP,
next-packet acquisition, token CRC5, ACK ownership and Flash guards. A smaller
component or an upstream enumeration demo does not close those gates.

## Follow-up phase evidence and register remap

The [portable V-USB core tools](../tools/vusb165_core/README.md) retain a
stronger 286-byte component. A phase delta contributes only when the same
observation changes both USB bits; selected raw captures and guarded votes
are retimed within their actual opcode budget. The raw scratch is now R23,
preserving foreground CRC R0, cached token R24 and CRC-high R25 after every
executed instruction. The two-clock optional jump remains two clocks.

This exact body, SHA256
`db2d8a08e86b493754890072b864e77039a93f7993269cbccf66430303b32d55`,
passes all 585 retained cases and 45 additional pristine controls. Expanding
the pristine matrix to every byte value finds nine BF-stream failures among
2304 new cases. The old R0 control fails the same nine cases with identical
publications and periods. First witness: 1,499,250 bit/s, negative periodic
jitter, output `bfbfbfbfbf9f5f7f7f7f7f` instead of eleven BF bytes.

The verifier returns failure for that 2934-case run. No expected-failure
exception is added. Its first observation is supplied centered by the test;
real SYNC, qualified EOP, malformed packets and protocol integration remain
unimplemented. The generator checks the original upstream SHA256/Git blob;
only tools are retained in Git, with generated derivatives in ignored build/.
At that stage, full firmware sizes after the separate local reductions were
1780/1948 bytes. Later control-state reductions are recorded separately.

The subsequent `--stuff4-delay` option corrects that BF path with one NOP
after its already-timed stuffed-bit observation. This stronger component is
288 bytes, SHA256
`30e1e209ef78726a22eb00f4ce95b2a9c62eaf2848ceb5e765c541fc4345a6b3`.
It passes all 630 retained controls and all 2304 pristine byte-value cases,
including the nine BF witnesses, with unchanged register guards and oracles.
The historical 286-byte option remains reproducible with its strict failures.
These results still supply no real SYNC or EOP/protocol integration proof.

## Follow-up qualification limits

The same-clock pointer-bound option remains 288 bytes, SHA256
`2cc5de3cbf7a1c0072ea92fc63a72e4dca7e5cd6987bcfce520d5d98903a9959`.
Its independent 2934-case overlength check permits exactly eleven stores in
0x116..0x120, preserves configuration 0x115 and rejects before a twelfth store.
R22 becomes available to a future framer. This does not repair its inherited
bit1-only EOP probe or validate every mandatory stuffed transition.

The portable entry-phase screen executes 6300 cases at five finite offsets
and both coordinated line mappings. It finds 202 single/repeated-erasure
failures at negative offsets, including -0.5 clocks. The tested zero and
+0.25 points pass 1260 cases each. A clean-input phase margin cannot be reused
as an erasure-tolerance interval or a SYNC guarantee.

Two linked acquisition experiments were rejected:

| Acquisition and retained core | Bytes | Cases | Complete-byte failures | Mandatory PID/payload/count failures |
| --- | ---: | ---: | ---: | ---: |
| Cooperative full-K persistence | 344 | 3042 | 219 | 183 |
| Paired per-symbol SYNC phase feedback | 446 | 6316 | 1962 | 1950 |

The first front can mistake actual ACK PID0 J for a broken eighth-SYNC
persistence check, restart, and decode physical cell 15 as the first PID bit.
Fourteen delay-only images, zero through six added clocks and both mappings,
execute 112 witness cases; no delay fixes that earlier restart decision.

The second front fixes both original integer-entry witnesses but fails a
pristine fractional entry. At DATA entry 24.75, FIRST/SECOND at 30.25/32.25
both see SYNC cell 2. The next pair at 40.25/42.25 straddles cells 3/4.
The following FIRST equals the already advanced SECOND, falsely declaring
the final SYNC one; the supposed PID sample at 62.25 belongs to cell 5.
Actual 10/11-clock cadence therefore does not establish sample ownership.
All 3158 paired mapping results are symmetric; a pin assignment correction
cannot repair this failure. Numerical DATA CRC16's waiver does not permit
the wrong PID, payload or count.

A private 320-byte stuff-after-bit6 guard also passes all 2934 retained
positive controls but fails two independent legal-crossover cases out of 270.
One is a new guard regression; the other is an inherited decode failure.
The guard's full two-pin XOR comparison uses a prior raw operand that can
itself be erased. For valid DATA0 `C3 01 FE FE FE FE FE FE FE`, 1500750 bit/s,
periodic sign -1 and crossover fraction 1 at stuffed edge 31, that prior
operand sees legal SE0 while the stuffed observation sees full J. The
unguarded core publishes all eleven correct bytes; the guard rejects them.
The matched SE1 case already misdecodes payload in both baseline and candidate
without entering this stuff6 guard; it is not a second new guard regression.
This shortcut is rejected. Its use of R22 as transient raw scratch is
an explicit private-mode ABI; the accepted pointer-bound option's R22
preservation contract is unchanged.
The rejected body's SHA256 is
`427d0c6f87140018ea3a8a719dec26557e62d0c3305bf17800762266b7f76c76`.
Nine malformed counterparts reject. Four matched controls cover both mappings
and SE0/SE1, attaching excursions only to genuine subsequent physical edges,
without inventing an edge at the missing-stuff position. Their success does
not cancel the valid-packet regression or qualify the other stuffing routes.

The private link-budget scaffold is 1310 bytes at 0x1900, SHA256
`317bddec7118f9d2ee9db81052c66d69130c8dc82ddf0ae42cb0d9cee1828298`.
It combines the earlier shared owner with the 288-byte core, but acquisition
and unqualified SE0/overflow fail closed. Its 1288 direct admitted-frame
comparisons test only the protocol seam. The scaffold is already 30 bytes
over 1280 before real acquisition/EOP, and is not a working receiver.

Exact sources, immutable bodies and traces remain under the local validation
directories `vusb-loader-integration-nov03`, `vusb-sync-integration-nov03`
and `vusb-eop-integration-nov03`, including the SYNC `followup/` report.
The guarded-stuff witness is in `vusb-stuff-validation-nov03/RESULT.md`,
with `valid-counterexample.json`, `counterpart-report.json` and `finite-report.json`.
The maintained portable generator and strict oracles stay in the repository.
No failed front/guard was selected for a loader or installed on hardware.
