# External software Low-Speed USB review

Reviewed on 2026-11-03 for the ATtiny88, 16 MHz, no-LED, 1280-byte objective.
The review uses original source and author documentation. Reported upstream
sizes are not measurements of our complete loader. Current firmware remains
1780 bytes for the default control and 1948 bytes for the improved ACK variant;
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
Full firmware sizes after the separate local reductions are 1780/1948 bytes.

The subsequent `--stuff4-delay` option corrects that BF path with one NOP
after its already-timed stuffed-bit observation. This stronger component is
288 bytes, SHA256
`30e1e209ef78726a22eb00f4ce95b2a9c62eaf2848ceb5e765c541fc4345a6b3`.
It passes all 630 retained controls and all 2304 pristine byte-value cases,
including the nine BF witnesses, with unchanged register guards and oracles.
The historical 286-byte option remains reproducible with its strict failures.
These results still supply no real SYNC or EOP/protocol integration proof.
