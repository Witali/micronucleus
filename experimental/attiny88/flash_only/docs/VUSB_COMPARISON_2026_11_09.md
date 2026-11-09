# Native V-USB16 comparison, 2026-11-09

The measured growth is concentrated in receive/framing and transaction
ownership, not EEPROM, LED or a larger transmitter. At the same 0x1900
placement the archive is 1030 bytes and the current combined loader is 1768:
738 additional bytes. The USB/ACK region grows 496→1190 bytes (+694), while
the remainder grows 534→578 (+44). That region also includes Flash-buffer
staging moved into the accepted-ACK path; it is not a marginal cost accounting
of USB checks alone. The historical archive at 0x1A40 is 1034 bytes; comparing
that number directly hides a four-byte placement saving.

Some added checks enforce actual USB requirements. Some state implements our
chosen stronger policy. The larger receive implementation has accumulated
special continuations and still fails mandatory legal-input tests. Its size
is neither a compliance proof nor evidence that every added byte is necessary.

## Exact inputs and build scope

The [official download page](https://www.obdev.at/products/vusb/download.html)
identifies GitHub master as current. A fresh full clone and GitHub API check
on November 9 both resolve to
[`801242072fa035e1839e3571df0d9a18e9cec95c`](https://github.com/obdev/v-usb/commit/801242072fa035e1839e3571df0d9a18e9cec95c),
dated August 26, 2026. This is the same upstream pin used in the earlier
partial review, not a newly revised decoder.

Both builds target classic ATtiny88 and an exact 16 MHz clock, PD1=D−,
PD2=D+, no LED. Native V-USB uses AVR-GCC 7.3.0, `-Os`, function/data sections
and linker garbage collection, without LTO or relaxation. Its original source
is unchanged. EP0 only, no optional IN/OUT endpoints, HID, application payload
callbacks, long transfers or strings except the language-zero descriptor.
A four-byte setup callback and minimal init/poll main make a linkable example;
it contains no loader commands, Flash programming or application jump.
Our hand assembly uses the existing LLVM/AVR link pipeline. This is not a
compiler-only comparison or two devices with identical features.

| Image | Placement | Flash bytes | SHA256 |
| --- | --- | ---: | --- |
| Native V-USB minimal EP0 example | 0x0000 | 1178 | `d02ace1a8ed3538071ec8016dfe0090c240af048292e928b62a0649fa31c879a` |
| Native with `CHECK_DATA_TOGGLING=1` | 0x0000 | 1182 | `68c220bc17fc7a76b6ed3ef0a2418bc84fb214feb1040976e71f1ed6c6c2336b` |
| Current combined loader | 0x1900 | 1768 | `82856722a8dc7bfbf19248281dfe3871ac9583a58b807e5691911671adb342b6` |
| Separate ACK experiment | 0x1800 | 1936 | `ba15c3c7e2e63dab56afb7a46ea1c8f7631dd8fc87d16d0e6b7322a524ae2dce` |
| Legacy strict-source fixture | 0x1A40 | 1340 | `f36e38cb72e00bc39c0a361d5f4d2a6cdaa5c0d44a334a0c3daeee5b7634f364` |
| Archive at matching placement | 0x1900 | 1030 | `4f60a746dcdf29e5d2fe4048dd4a7bad1a01b204573d01363fb88734e61c1613` |

Native Flash is `.text` 1176 + initialized `.data` 2; BSS is excluded. The
driver itself, including descriptors and initialized data, occupies 1066
bytes; CRT, vectors, minimal callback/main and exit occupy another 112.
Its assembly is 602 bytes, including 50 bytes of outgoing CRC16. Its inlined
`usbPoll` is 408 bytes and `usbInit` 14. Enabling the toggle option adds four
bytes that expose the received DATA PID to C; it does not implement a full
automatic retransmission/toggle state machine.

## Size and algorithm by responsibility

These are disjoint physical code ranges from linked labels, with shared
paths counted once. They sum to each image. They are not independently
removable functions: native C inlines work into `usbPoll`, and receive/EOP
continuations share instructions. The tool records exact range boundaries.

| Responsibility | Native V-USB | Ours | Difference |
| --- | ---: | ---: | ---: |
| Descriptors | 40 | 36 | −4 |
| Entry and SYNC | 94 | 80 | −14 |
| RX, stuffing, early framing | 142 | 386 | +244 |
| EOP classification and final tail | 46 | 264 | +218 |
| Packet dispatch, transaction state, return | 112 | 290 | +178 |
| TX symbols and driven EOP | 158 | 132 | −26 |
| CRC16 and foreground EP0 replies | 458 | 300 | −158 |
| Initialization, loader and remaining code | 128 | 280 | +152 |
| Total | 1178 | 1768 | +590 |

The last row includes our SELECT/WRITE4/READ8/RUN, application placement and
Flash staging, whereas native has only example/runtime overhead. Native's
46-byte EOP span also begins packet classification; ours has additional early
EOP branches in the RX row. Per-row differences are not isolated feature costs.

| Function | Native algorithm | Current algorithm and USB interpretation |
| --- | --- | --- |
| SYNC | Interrupt entry; fast D− J/K polls; accept a two-K observation and sample PID. | Cooperative PCINT polling; shares the acquisition family while preserving foreground registers. Required PID ownership still fails some legal crossover inputs. An IRQ implementation cannot be inserted into our application-owned vectors unchanged. §§7.1.4.1, 7.1.10. |
| Decode/stuff | Mask samples, XOR adjacent raw states, rotate history; skip a symbol when the six-one threshold fires. | Same compact history idea plus mandatory-transition rejection, early-EOP and boundary continuations. Skipping a stuffed symbol without validating it does not implement malformed-stuff rejection. §§7.1.8–7.1.9.1. |
| EOP/dribble | Detect SE0 mainly at odd-bit/selected stuffer observations, then enter common dispatch. No complete residual-tail or live-J qualifier. | Additional even/final probes, residual-byte/all-one dribble classification, minimum-width and recovery-J checks. Required reception includes 670 ns EOP and legal final stretch; extra partial zeros are not permitted dribble. §§7.1.9.1, 7.1.13.2.1. |
| Token admission | Compare address with endpoint bit shifted out; EP0-only configuration does not validate all endpoint bits or CRC5. | Exact count/address/endpoint/CRC5 compare against a cached endpoint-zero wire value. Required filtering cannot be replaced by trusting the computer. §§8.3.1–8.3.5, 8.4.1, 8.7.1. |
| IN retry/ACK | Clear available TX state on send; explicitly assume delivery succeeds without waiting for host ACK. | Cache identical DATA/PID until eligible ACK/status completion; bounded timeout cancels authorization without freeing the retry copy. §§8.4.5, 8.5.3.1, 8.6. |
| SET_ADDRESS | Compute pending address in foreground and activate during status DATA EOP. | Compute pending address/CRC, activate after eligible ACK. §9.2.6.3 permits status transmission OR ACK as completion: our later point is a project policy, not the only allowed implementation. Replacement-SETUP cancellation is a separate correctness concern. |
| Chapter 9 | Shared general C dispatcher/descriptor builder, including optional configurations. | Small supported request set, shared reply/length limiter, unsupported-request STALL. Do not validate fields whose behavior §9.4 explicitly leaves unspecified. Optional SET_DESCRIPTOR and default-only SET_INTERFACE/Halt machinery need not be added. |
| Reset/side effects | Default reset clears address state, with optional endpoint/reset hooks. | Clear live configuration/address/cache, token/ACK/deferred work and page selection. Flash/RUN are blocked while DATA remains outstanding. A complete reset returns to Default state; memory-write safety is also a loader requirement. §§9.1, 8.5.3–8.7. |

Native source references:
[`usbdrvasm16.inc`](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm16.inc),
[`asmcommon.inc`](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/asmcommon.inc),
[`usbdrv.c`](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrv.c).
The upstream [documented limitations](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrv.h#L38)
explicitly omit stuffing errors, misplaced SE0 and receive token/data CRC in
the ordinary path. Current upstream has a receive-DATA-CRC option at 18 MHz,
not an equivalent switch for the inspected native 16 MHz code.

## Fresh emitted-code results

The native probe executes unchanged linked instructions in our existing
AVRe/GPIO model. SRAM ELF addresses are normalized, constructor-only entry
aliases refer to the actual native ISR, and BSS/NAK are seeded explicitly.
RX stops at `se0`, `overflow` or `sofError` before dispatch/RETI. TX stops at
`doReturn` before restore/RETI. These limits exclude full-stack, vector-routing,
arbitrary ISR latency and analog/electrical qualification.

| Native check | Result |
| --- | --- |
| 670 ns EOP: six packet shapes × three host rates × three ISR entries | 0/54 received; all reach overflow |
| Nominal two-bit EOP | 54/54 exact packets |
| 1500 ns EOP | 54/54 exact packets |
| ACK/NAK/STALL and four DATA payload patterns | 7/7 exact NRZI/stuffed symbol streams |
| Unstuffed byte period | 84 measured clocks; 1.5238095 Mbit/s at exact 16 MHz, above the 1.5225 Mbit/s limit |
| Driven source SE0 | 22 clocks for handshakes, 23 for DATA: within 20..24 clocks |
| Driven recovery J before release | One clock; §7.1.7.4.1 requires one bit time, approximately 10.67 clocks |

For the nominal ACK witness, physical short SE0 spans clocks
170.666667..181.386667. The even-position read at 177.5 sees it but does not
test SE0; the next odd read at 187.5 sees J. This is the actual linked native
16 MHz implementation, not the earlier retimed 16.5 MHz excerpt.

The current 1768-byte image was also tested afresh. Its independent TX gate
passes 1093 packets, 64 unrelated-GPIO cases, 26 final-stuff cases and 1536
byte/run cases. The separate 975-case EOP gate measures 21 clocks of SE0 and
11 driven J. Its TX seed is 0x3B, versus native 0x35; copying native TX would
increase size and restore its different timing graph.

Our fresh legal-input RX tests still fail: 120/2484 asymmetric 210 ns
crossover cases and 144/1080 injected SYNC crossover cases, with 54 pristine
SYNC controls. These are failures on the exact current hash, not older-image
counts relabeled. More protocol guards have not yet produced a fully correct
PHY. The smaller 1340-byte fixture and 1936-byte ACK experiment are separate
images and do not change that conclusion.

Only numeric incoming DATA CRC16 validation/storage is waived by the project.
That is a project deviation, not a USB allowance. All other frame, PID,
token, payload, retry and timing requirements remain; neither implementation
is claimed fully compliant. The primary clauses were checked against the
cached [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification).

## Reproduction and optimization consequence

From the Flash-only directory, with AVR GCC/binutils and LLVM available:

```sh
git clone https://github.com/obdev/v-usb.git /path/to/v-usb
git -C /path/to/v-usb checkout 801242072fa035e1839e3571df0d9a18e9cec95c
python3 tools/compare_vusb16.py --upstream /path/to/v-usb --output build/vusb16-audit
python3 tools/probe_vusb16.py --artifact build/vusb16-audit/native-toggle0/artifact.json --output build/vusb16-probe
```

The measurement script checks the pin/clean checkout, freezes ELF/body/symbols,
checks byte identities and asserts disjoint range totals. The probe checks
ELF/body hashes before and after execution and derives rate from actual byte
timestamps. It exits **1** for these mandatory native failures; no expected-
failure exception turns them green. Completed report directories cannot be
silently overwritten. Generated binaries/JSON stay outside Git.
The native probe intentionally pins this GCC 7.3.0 image; a different compiler
output requires a separate artifact review rather than an automatic hash refresh.

Prioritize a coherent shared receive/framing design, replacing duplicated
cold/final-byte continuations while proving all symbol and recovery paths.
The 288-byte component alone does not establish a valid SYNC/EOP receiver.
Keep the already smaller corrected TX and compact foreground dispatcher.
Post-ACK address activation may be reconsidered as policy, but changing it
alone cannot recover the hundreds of RX bytes. A bare 1178-byte V-USB example
cannot be advertised as a 1280-byte loader with equivalent robustness.

The [fork review](VUSB_FORKS_2026_11_09.md) found useful individual mechanisms
but no verified more-complete 16 MHz AVR replacement among inspected branches.
No firmware source or hardware was changed during this comparison.
