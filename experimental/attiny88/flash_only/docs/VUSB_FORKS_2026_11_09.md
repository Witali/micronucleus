# Third-party V-USB fork review, 2026-11-09

Scope: source and patch inspection for a more complete USB implementation suitable for the existing ATtiny88 at 16 MHz. Correctness now takes priority over the deferred 1280-byte target. The initial review did not build the forks; the follow-up below executes one ported timing hypothesis in our linked firmware. No fork hardware tests were performed; [native upstream was measured separately](VUSB_COMPARISON_2026_11_09.md). Pins below were checked on 2026-11-09; dates are commit dates. Public GitHub source was fetched through the GitHub connector. Search also covered the upstream issue/PR list, repository searches, commit searches, and author documentation. This is a bounded search, not proof that no other implementation exists.

**Result: no verified more-complete 16 MHz AVR V-USB fork was found among the inspected candidates.** There are useful additions, including delayed CRC rejection, remote wake, more endpoints, and polling/bootloader sharing, but these do not collectively repair receive CRC, malformed stuffing/EOP, ACK retries, token filtering, and SET_ADDRESS completion. No inspected fork demonstrates a complete replacement within this project's size target.

USB 2.0 section 9.2.6.3 permits SET_ADDRESS completion on status transmission
or ACK. A send-time implementation is not, by itself, a violation. The address
differences below must be read separately from stale replacement-SETUP state
or activation before the status stage. Our post-ACK policy is stricter than
that particular allowance; it is not a compliance test for every fork.

## 1. russdill/v-usb, branch vmeiosis: useful integration work, same packet assumptions

Pin: [`f2fc5347d8977016119c02551a4630f5f5402357`](https://github.com/russdill/v-usb/commit/f2fc5347d8977016119c02551a4630f5f5402357), 2024-11-30. Its default `master` is an older upstream copy; the actual fork work is on `vmeiosis`.

The [18-commit comparison against its upstream base](https://github.com/russdill/v-usb/compare/7a28fdc685952412dad2b8842429127bc1cf9fa7...f2fc5347d8977016119c02551a4630f5f5402357) adds interrupt-free operation, selectable interrupt modes, interrupt chaining, alternate descriptor handling, EEPROM/fuse reads, register-held state, re-enumeration support, and remote wake. These are real features. The [remote-wake patch](https://github.com/russdill/v-usb/commit/725c4a925fe42b468c2ea2e49a77716bbeba3702), 2024-11-12, adds request handling, status state, reset clearing, and line-driving macros; it is not a packet-validation redesign or a compliance certificate.

The decoder files have no new receive validation in that comparison. [`asmcommon.inc` lines 180-186](https://github.com/russdill/v-usb/blob/f2fc5347d8977016119c02551a4630f5f5402357/usbdrv/asmcommon.inc#L180) explicitly retain the assumption that IN succeeds without waiting for host ACK. [`usbdrvasm16.inc` lines 319-328](https://github.com/russdill/v-usb/blob/f2fc5347d8977016119c02551a4630f5f5402357/usbdrv/usbdrvasm16.inc#L319) still assign the new address when a DATA packet is sent, rather than in a received status-ACK handler. The optional upstream CRC machinery remains the existing 18 MHz path.

Associated bootloader: [`russdill/vmeiosis` at `6a9778c8d098b33361a52939aa7dc21bc3e6f31d`](https://github.com/russdill/vmeiosis/tree/6a9778c8d098b33361a52939aa7dc21bc3e6f31d), 2024-12-04. [`main.c` lines 277-286](https://github.com/russdill/vmeiosis/blob/6a9778c8d098b33361a52939aa7dc21bc3e6f31d/main.c#L277) check host-to-device request CRC in the application callback and restart enumeration on failure. That protects flash operations, but ACK has already been transmitted. It does not provide normal USB retry. The [README](https://github.com/russdill/vmeiosis/blob/6a9778c8d098b33361a52939aa7dc21bc3e6f31d/README.md) reports a 1614-byte example bootloader and shared-code savings; those are not a measured ATtiny88 complete-USB result.

## 2. JPEWdev/hid-relay: verified delayed receive CRC guard

Patch pin: [`56c7e46fbc6c9a44080e7e8731bde68ef992a6e6`](https://github.com/JPEWdev/hid-relay/commit/56c7e46fbc6c9a44080e7e8731bde68ef992a6e6), 2024-05-10.

The patch adds an enabled-by-default `CHECK_CRC` option and checks `usbCrc16(data, len + 2)` before dispatching received requests in [`usbdrv.c` lines 431-435](https://github.com/JPEWdev/hid-relay/blob/56c7e46fbc6c9a44080e7e8731bde68ef992a6e6/usbdrv/usbdrv.c#L431). This is a concrete integrity improvement, including internally handled requests routed through `usbProcessRx`. Its commit message correctly explains that rejection happens after V-USB has sent ACK. It protects the relay from acting on bad bytes; it does not cause automatic USB retransmission, validate token CRC5, improve stuffing/EOP rejection, or repair IN ACK handling. No malformed-packet qualification is supplied by this patch.

## 3. qmk/v-usb: additional endpoint, not additional error robustness

Pin: [`819dbc1e5d5926b17e27e00ca6d3d2988adae04e`](https://github.com/qmk/v-usb/commit/819dbc1e5d5926b17e27e00ca6d3d2988adae04e), 2022-06-12, branch `qmk-master`.

The [fork comparison](https://github.com/obdev/v-usb/compare/master...qmk:qmk-master) shows the substantive extension in [`bdb53e4c043d089279d9891b68bea77614cb97ee`](https://github.com/qmk/v-usb/commit/bdb53e4c043d089279d9891b68bea77614cb97ee), 2020-08-16: another interrupt-IN endpoint with descriptors, buffers, dispatch, and branch-distance workarounds. The author says its two extra dispatch cycles still fit 16 MHz response timing. No receive decoder, CRC, host-ACK transaction state, or SET_ADDRESS correction appears in those fork additions. Extra endpoints broaden functionality without answering the loader's error-handling requirements.

## 4. Micronucleus and Digistump: bootloader/host compatibility improvements retain V-USB limitations

Micronucleus pin: [`4dd1b49f39cd9d6fc736a720777ed62f4564e0e2`](https://github.com/micronucleus/micronucleus/tree/4dd1b49f39cd9d6fc736a720777ed62f4564e0e2), 2026-02-06. [`firmware/usbdrv/asmcommon.inc` lines 112-157](https://github.com/micronucleus/micronucleus/blob/4dd1b49f39cd9d6fc736a720777ed62f4564e0e2/firmware/usbdrv/asmcommon.inc#L112) still ACKs received DATA and clears IN availability on transmit, with the original explicit error-free-transfer rationale. Its changes include polling, in-order processing, and bootloader size work. A genuine [2014 fix for `--run`](https://github.com/micronucleus/micronucleus/commit/eef6c9736b07669aee8965533dba963a363b8494) waits 5 ms before entering the application to avoid colliding with the final host ACK; this is an application exit-timing fix, not general ACK-based retransmission.

Digistump pin: [`DigistumpArduino` at `111396ffe5163c3613b9315cbea1a3eabc9ba6dc`](https://github.com/digistump/DigistumpArduino/tree/111396ffe5163c3613b9315cbea1a3eabc9ba6dc), 2017-08-29. The bundled [`DigisparkCDC/asmcommon.inc` lines 155-161](https://github.com/digistump/DigistumpArduino/blob/111396ffe5163c3613b9315cbea1a3eabc9ba6dc/digistump-avr/libraries/DigisparkCDC/asmcommon.inc#L155) has the same missing ACK wait. Class-specific CDC changes do not establish USB packet correctness.

A newer, informative derivative is [`marcocarnut/DigiCDCFast` commit `a294a9acb000a712404e4f902873ccddbf396c42`](https://github.com/marcocarnut/DigiCDCFast/commit/a294a9acb000a712404e4f902873ccddbf396c42), 2026-09-13. Inspected changes queue an empty packet before data after 10 ms of IN inactivity; they do not implement ACK tracking. The author reports Digispark Pro/Linux/xHCI testing: post-flood losses went from 8/40 trials to 0/40 after flooding stopped, while simultaneous saturation still lost an 8-byte packet in approximately 1/20 rounds. This is author-reported evidence of a workaround and of remaining limitations, not independent certification or a fix to transplant as compliant USB behavior.

## 5. Architecture ports and compatibility variants

[`12oclocker/V-USB_TinyAvr` at `90b3c449431ffe0245a00536fe4537540c90325c`](https://github.com/12oclocker/V-USB_TinyAvr/tree/90b3c449431ffe0245a00536fe4537540c90325c), 2026-07-10, ports AVR instruction timing/register mapping to tinyAVR 0/1 series. The [16 MHz source](https://github.com/12oclocker/V-USB_TinyAvr/blob/90b3c449431ffe0245a00536fe4537540c90325c/usbdrv/usbdrvasm16.inc#L27) documents cycle differences and compensations. Its [`asmcommon.inc` lines 154-160](https://github.com/12oclocker/V-USB_TinyAvr/blob/90b3c449431ffe0245a00536fe4537540c90325c/usbdrv/asmcommon.inc#L154) retains immediate transmit completion without host ACK. This enables another MCU architecture; it does not add the missing validation for a classic ATtiny88. Upstream [PR #26](https://github.com/obdev/v-usb/pull/26) is another explicitly architecture-specific tinyAVR 1-series port, not an ATtiny88 compliance patch.

[`gblargg/adb-v-usb` at `1bc4316a79ce9b4be7d5caa1b10891658d6d5513`](https://github.com/gblargg/adb-v-usb/commit/1bc4316a79ce9b4be7d5caa1b10891658d6d5513), 2014-04-28, includes a real Dell BIOS/reset compatibility fix in the application keyboard/reset logic. Its [unchanged ACK policy](https://github.com/gblargg/adb-v-usb/blob/1bc4316a79ce9b4be7d5caa1b10891658d6d5513/usbdrv/asmcommon.inc#L154) still makes it unsuitable as evidence of stronger packet error recovery.

## 6. Useful independent reference: cnlohr/rv003usb

Pin: [`16d5cd488279659e51e28dcf37d6fe9c1cac9ca3`](https://github.com/cnlohr/rv003usb/tree/16d5cd488279659e51e28dcf37d6fe9c1cac9ca3), 2026-10-30. This is a software USB implementation for CH32V003-family RISC-V at 48 MHz, not an AVR V-USB fork or a drop-in ATtiny88 replacement.

Its source does demonstrate several of the desired mechanisms: [inline token/data CRC handling](https://github.com/cnlohr/rv003usb/blob/16d5cd488279659e51e28dcf37d6fe9c1cac9ca3/rv003usb/rv003usb.S#L268), [stuffed-transition and whole-byte checks](https://github.com/cnlohr/rv003usb/blob/16d5cd488279659e51e28dcf37d6fe9c1cac9ca3/rv003usb/rv003usb.S#L396), and [IN toggle/count advancement in a received ACK handler](https://github.com/cnlohr/rv003usb/blob/16d5cd488279659e51e28dcf37d6fe9c1cac9ca3/rv003usb/rv003usb.S#L608). These make it a useful conceptual comparison.

It should not be presented as fully compliant either: [SET_ADDRESS updates the address while processing setup data](https://github.com/cnlohr/rv003usb/blob/16d5cd488279659e51e28dcf37d6fe9c1cac9ca3/rv003usb/rv003usb.c#L434), [token dispatch accepts address zero in addition to its assigned address](https://github.com/cnlohr/rv003usb/blob/16d5cd488279659e51e28dcf37d6fe9c1cac9ca3/rv003usb/rv003usb.S#L483), and the [README still calls it beta and lists timing work](https://github.com/cnlohr/rv003usb/blob/16d5cd488279659e51e28dcf37d6fe9c1cac9ca3/README.md#L100). Its reported 1920-byte bootloader is for different hardware and does not satisfy this loader's 1.28 KB goal.

## Search bounds and practical conclusion

Source/patch inspections above were supplemented by comparing the upstream history against `obsidiansystems`, `LogicGreen`, `pctj101`, `bitland`, `tinyusbboard`, `patthoyts`, `hannesweisbach`, `whiteneon`, `pbing`, `spacecoaster`, `tomaja`, and `dimitris-lagos` default branches. These yielded no independent packet-validation patch: most are behind upstream, and whiteneon's extra commit is a merge with no new file diff. The upstream issues and PRs also yielded architecture, descriptor, oscillator, build, and host-tool changes rather than a full 16 MHz validation/retry implementation. Custom branches outside the named inspections were not exhaustively enumerated.

For this project, the useful findings are specific techniques, not a replacement stack: delayed receive CRC guards can protect flash operations; real ACK tracking must retain pending DATA until ACK; malformed-packet handling and correct address commit timing still need explicit qualification. Neither shared-driver savings nor endpoint additions demonstrate those properties. The existing 18 MHz CRC module is already upstream, not a newly discovered third-party solution.

## Follow-up: concrete patch transfer and broader fork comparison

The public fork API returned 249 entries. Compare all 50 default branches whose
metadata reported a push since 2022 or more than three stars against pinned
upstream `801242072fa035e1839e3571df0d9a18e9cec95c`: 45 are behind, one identical,
and four diverged. The [compact comparison snapshot](VUSB_FORK_FOLLOWUP_2026_11_09.json)
pins their heads and changed files. QMK adds its already-reviewed endpoint;
dipesh0xE and whiteneon have no net file changes. The additional receive change
is in `redmcg/v-usb`, default branch `uno`.

The [redmcg patch `089effe8a21977cfab4aff92a985dac0c1eeb72c`](https://github.com/redmcg/v-usb/commit/089effe8a21977cfab4aff92a985dac0c1eeb72c)
inserts one NOP immediately before the first PID-bit input sample. It shifts
the ensuing receive calendar by one clock; it adds no transition, EOP, stuffing
or packet-ownership validation. Its author reports improved success, without
a specification-based qualification matrix.

Port exactly that delay to our default receiver before its first R16 input
sample. The unchanged control is 1766 bytes at 0x1900, SHA256
`9459888f75d3c98fb636cabb910ae401f69f858bc68dfc4d1eb1eb02a89a2f4e`.
The test image is 1768 bytes at the same placement, SHA256
`2e24383395e676dc9cc842142c0091acdc4f05e41bb54af36f5f9e741dcb643a`.
The original independent GPIO/model tests are unchanged.

| Mandatory group | Cases | Control failures | One-clock-delay failures |
| --- | ---: | ---: | ---: |
| Asymmetric SE0 crossings | 2484 | 120 | 66 |
| Transient SE1 crossings | 2486 | 63 | 20 |
| SYNC crossings | 1080 injected + 54 clean controls | 144 | 126 |
| Mixed payload preservation | 981 | 69 | 1 |
| Final CRC positions, stuffing and tails | 450 legal + 1048 negative | 0 | 0 |

The remaining payload witness is the EF stream's next stuffed transition at
physical index 82, rate 1500750, periodic sign -1, entry 8 and fraction 20/21.
The patch improves several finite matrices but fails mandatory reception and
is not enabled in maintained firmware. A fixed delay cannot replace acquisition
that distinguishes the actual physical phase, nor a receiver that retains the
right preceding line through a crossover.

Reproduce the controls and isolated generated sources with the normal AVR/LLVM
toolchain on PATH. Existing output directories are refused to preserve evidence.

```sh
python3 tools/probe_rx_entry_delay.py --delay 0
python3 tools/probe_rx_entry_delay.py --delay 1
python3 verify_receiver.py --source build/rx-entry-delay/default-1 --boot 0x1900 --exhaustive
```

Each probe freezes an ELF, body, symbols and hashes in ignored `build/` and
retains the original ACK implementation as its sole owner. `--ack` selects that
reader at 0x1800: the independently rebuilt 1934-byte control and 1936-byte delayed
bodies are separate experiments, not the table's default-body results.
Building a probe does not declare the full gate passed. Private exact-image
reports remain in `validation/unified-rx-eop-nov09/vusb-followup/`.

Two actual upstream corrections are also relevant:

- [The 2009 16 MHz bit6 unstuff correction](https://github.com/obdev/v-usb/commit/3aa5195808868206835073e3c1a638a5973e20d8)
  repairs fractional leap accounting, including `SUBI leap,-1` for the eleven-clock
  path and `SUBI leap,2` for the ten-clock path. Those adjustments are already
  present in our corresponding paths. Reapplying them does not fix current
  SE1 or SYNC failures.
- [The 12.8 MHz EOP correction](https://github.com/obdev/v-usb/commit/b6a66c5058b8f646f9544582da8c330887ab6bd7)
  replaces an unstable midpoint-only SE0 test with D-minus zero at both bit0
  and bit1 plus D-plus zero between them. It is useful evidence for combining
  phase and end-of-packet reasoning. Its instruction schedule belongs to the
  12.8 MHz PLL; the current source itself warns about delayed EOP at old hubs.
  It is not a proved 670 ns EOP replacement at 16 MHz.

The 18 MHz CRC variant verifies mandatory stuffed transitions and folds CRC work
into receive slots, but uses two 256-byte lookup tables and twelve clocks per
bit. It does not supply a table-free 16 MHz correction for these crossover and
acquisition defects. No borrowed fragment above qualifies the complete loader;
all accepted compositions still need the complete exhaustive gate.

## Actual 16 MHz transfer of the 12.8 MHz phase feedback

The most useful mechanism is upstream's real PIN-sample phase feedback in
`usbdrvasm128.inc`. A separate [offline PLL experiment](../prototypes/pll_extra6/README.md)
retimes that code for the ATtiny88 at 16 MHz and connects its genuinely decoded
PID to the frozen line/run receiver with an extra observation at FIRST+6.
It retains upstream license/provenance and pins all source/model inputs.
This is an experimental source transfer, not a selected firmware variant.

The linked component is 5634 bytes at 0x0800, body SHA256
`d668eb3e8b59ecd8a641d77b4a00d38b45326efe9dd607c7d1b0d298b1c1999b`.
It fits the physical 8 KiB target but has no protocol owner or byte publication;
its size is not comparable to a complete release bootloader. The verifier
starts at the actual USB handler, never supplying a decoded PID, phase, run,
handoff PC or adjusted clock.

| Independent component checks | Cases | Failed valid inputs |
| --- | ---: | ---: |
| Mixed excursions on adjacent SYNC edges | 3168 | 0 |
| SYNC corner jitter | 1848 | 0 |
| Individual DATA-edge excursions | 4752 | 261 |
| Excursions on every DATA edge | 216 | 0 |
| Additional payload/PID/token and ownership witnesses | 2627 | 165 |
| Fractional endings, nominal EOP | 6048 | 0 |
| Fractional endings, 670 ns SE0 and one-bit recovery J | 6048 | 0 |

All failures in these finite matrices are explicit unfinished recovery
rejections with a short decoded count. None is accepted as a passing USB
packet. The checks found no corrupted PID/payload/CRC bit or premature EOF
tag. The observer compares both transmitted CRC bytes exactly; no observed
CRC-bit mismatch is waived. The component does not implement numeric CRC
validation. These checks still do not qualify recovery J, malformed frames,
packet admission, SRAM bounds, status/ACK ownership or response deadlines.
The maintained 1934-byte ACK baseline is unchanged and retains its documented
five failing mandatory groups.

The transfer therefore supplies a tested acquisition mechanism worth keeping.
It does not supply the missing complete DATA/EOP/publication implementation.
Later changes must use separately named exact-image reports and the complete
USB gate before they can replace the maintained PHY.

### Negative PID audit: incomplete ACK remains ambiguous

The positive matrices above do not qualify malformed PID reception. The
separate [PID-prefix probe](../tools/probe_pll_pid_prefixes.py) exposes an
incomplete-PID framing ambiguity in that same 5634-byte body, without changing
its code, independent CPU model, GPIO aperture or cooperative entry.

Across 1134 genuine truncated-ACK prefixes, 162 empty-PID controls and 162
complete ACK controls, there are 270 provisional decoded-D2 handoffs. Of those,
162 subsequently reject; a provisional handoff alone is not a USB violation.
The remaining 108 are seven-bit ACKs that reach a decoded-D2 plus EOF-ready tag
without a post-PID DATA shift. All 162 complete ACK controls pass.
The broader run of all 41148 raw premature prefixes plus the same empty and
complete controls (41472 cases) reproduces exactly those 108 ambiguous tags.

One witness uses host rate 1499250, jitter sign -1, cooperative entry 5 and
SE0 width 64/3 clocks. Its seven physical PID bits end at 160.080040020 clocks;
recovery J begins at 181.413373353. The saved phase input at 160.4999999
(PC 0x0c28) reads SE0; the later PID7 D-minus guard at 164.4999999
(PC 0x0c30) still allows the path. The actual handoff at 175 holds D2 and
reaches an EOF tag at 186. A complete
framer must distinguish that missing bit instead of trusting the assembled PID.
This component has no protocol owner: the observation does not demonstrate
cached-TX retirement, an on-wire ACK, or a hardware failure of native V-USB.

Run from the Flash-only directory after building the offline experiment:

```sh
python3 tools/probe_pll_pid_prefixes.py
python3 tools/probe_pll_pid_prefixes.py --suite whole-prefix
```

The default exit is nonzero while the ambiguity exists. An explicit
`--expect-known-failure` checks the pinned snapshot's exact failure counts and
can return zero for reproduction; its JSON still says
`qualification_passed: false`. The source/model/manifest/body/ELF inputs and the
probe itself are checked before and after the corpus.

The maintained 1934-byte ACK reader remains the control: its existing 41148
premature-prefix cases, 162 empty PIDs and 252 truncated-ACK followups pass.
Retain that correctly qualified ACK path until any replacement passes the
same negative and followup gates. Phase feedback from another implementation
is useful, but cannot replace explicit complete-PID/EOP ownership checks.

## November 10: transfer decision and corrected acquisition seam

Re-read the four linked upstream/fork patches above and rechecked the current
upstream `master`, redmcg `uno`, QMK `qmk-master` and russdill `vmeiosis` heads.
All four match the previous review's pins. The bounded review therefore still
finds no ready-made complete 16 MHz receive repair among these implementations.
The useful upstream contribution is phase feedback plus observations on both
sides of a possible EOP, rather than a wholesale replacement of our ownership
and malformed-packet handling.

The one-clock redmcg transfer was also tested in the separate-ACK composition:
1934-byte control versus 1936-byte delayed image. Its complete frozen 66-group
gate passes 59 groups, compared with the control's 61. Although the original
adjacent-token witness disappears and several crossover counts improve, it
introduces six short-EOP OUT STALL failures, late DATA admission and EOP-matrix
failures. Some smaller failure totals also contain new failing cases. That
patch remains rejected; an aggregate decrease cannot justify new regressions.

The upstream-derived PLL component now has a separately reproducible correction
for the incomplete-PID ambiguity. Keep the original sealed prototype unchanged:

```sh
python3 prototypes/pll_extra6/build.py
python3 tools/probe_pll_pid_guard.py --output-dir build/pll-pid-guard-centered
python3 tools/probe_pll_pid_prefixes.py --experiment build/pll-pid-guard-centered --suite whole-prefix
python3 tools/probe_pll_pid_prefixes.py --experiment build/pll-pid-guard-centered --suite held-se1
python3 tools/probe_pll_pid_prefixes.py --experiment build/pll-pid-guard-centered --suite eop-se1
python3 tools/probe_pll_first_edge.py --experiment build/pll-pid-guard-centered
```

The builder checks the original sealed source/model inputs, rebuilds both GNU
and LLVM images, compares every byte and symbol, and seals its derived source.
The corrected component remains **5634 bytes at 0x0800**, body SHA256
`8058c9de0496cf5fcb163d6f4fb453943da61bc29042c4a419c32e2147041147`.
This is component size, not complete bootloader size.

After actual acquisition, a paid MOV saves the sampled phase into R17; R20/R21
hold J/K constants. The final PID-one path requires both current D-minus-low
and the full saved phase equal to K. Run selection moves before the saved
sample, centering it one clock later in both supported run classes. Existing
guard, EXTRA+6 and next-FIRST+10 sampling clocks remain unchanged. Equal-time
five-clock LPM/RJMP padding pays the extra startup word. R17/R23 are declared
receive scratch; R0, live X and context Z remain protected. Only three symbol
addresses move: `pll128_pid0_sample` +2 bytes and `hybrid_pid7_run2` /
`hybrid_run3_pad` -2 bytes. No numeric CRC table or CPU-model change is involved.

Independent root reruns on this exact body reproduced:

| Check | Result |
| --- | --- |
| Entire premature-PID corpus plus empty/complete controls | 41472 cases; no incomplete D2 EOF tags or failed complete controls |
| Held SE1 at final PID symbol | 99 malformed inputs rejected; 324 controls pass |
| SE1 within incomplete PID EOP | 297 malformed inputs rejected; 324 controls pass |
| Nominal and minimum 670 ns EOP | 6048 cases each; zero failures |
| Acquisition/DATA matrix | 9984 cases; same 261 unfinished DATA rejections as the original component |
| Payload matrix | 2627 cases; same 165 unfinished DATA rejections |
| Combined SYNC and first DATA/address crossing | 13464 cases; no newly failed or lost-handoff cases; both components still fail the same 663 cases |

The combined test is necessary: an earlier current-line-only PID guard passed
the separate positive matrices but failed when legal SYNC and first-DATA
crossovers were combined. Neither relative equivalence nor the repaired PID
boundary qualifies a whole receiver. DATA recovery, bounded byte publication,
EOP/recovery J, packet admission and the complete 67-group composed-image gate
remain required. The maintained complete-image control remains 1934 bytes;
the 1280-byte target is not achieved.

### Actual acquisition joined to the recovered DATA graph

The [shared-recovery reference](../prototypes/pll_shared_recovery/README.md)
now joins the same centered PID prefix to the newer DATA recovery graph.
It executes the real USB handler; no PID, phase, run, handoff PC or intermediate
clock is supplied by its observer. The emitted component is 7346 bytes at
0x0200, body SHA256
`56e8816afe4b42e1a472992eeabe78478bc082e5a6e53d494ec1b58b343a5611`.
The component has no SRAM publication, full framing or transaction owner;
it is a correctness reference and cannot replace a complete bootloader.

Sharing cold handlers first reduced the standalone DATA graph from 6696 to
6192 bytes without changing execution clocks. Intact-cluster placement then
brought all four PID-root relative jumps into range without extra instructions.
An independent emitted-CFG audit compares all 42 graph roots and 3090 paired
nodes: instruction operands, both branch/skip outcomes, physical observations,
shifts and EOF/reject events agree. This establishes the graph's conditional
entry contract; actual acquisition is checked separately with real waveforms.
GNU and LLVM produce identical bytes, all 1084 labels and 1114 named relative
edges agree, and no edge needs program-counter wrapping. The component ends
at 0x1eb2 inside physical 8 KiB Flash.

| Actual-handler corpus | Cases | Failures |
| --- | ---: | ---: |
| Clean controls | 24 | 0 |
| Acquisition and DATA crossings | 9984 | 0 |
| Payloads, PIDs, tokens and original DATA witnesses | 2627 | 0 |
| Nominal EOP and fractional endings | 6048 | 0 |
| Minimum 670 ns EOP and fractional endings | 6048 | 0 |
| Premature PID prefixes plus empty/complete controls | 41472 | 0 |
| Held final-symbol SE1 plus controls | 423 | 0 |
| SE1 inside incomplete PID EOP plus controls | 621 | 0 |
| Combined SYNC and first DATA/address crossing | 13464 | 92 |

All 24731 original positive observations now pass. The earlier component's
261 + 165 unfinished DATA rejections disappear. The combined matrix improves
from 663 to 92 failures, all missing handoffs: a permitted first-DATA SE1
excursion can reach the late PID7 D-minus guard after the saved full-K sample.
For the earliest remaining case, saved phase is sampled at 164.4999999,
the next-DATA SE1 interval is 167.002042688..170.362042688, and the current
guard samples at 167.4999999. It rejects before the DATA graph is entered.
This remains a required acquisition repair, not a passing USB packet.

The generic component also preserves all 32 wire bits through the real EOP
for all 3456 adjacent-crossover fourth-byte token continuations. The portable
[token-tail probe](../tools/probe_pll_token_tails.py) adds 3456 pristine controls,
checks every bit/count/calendar with the unchanged observer, and rejects any
positive error. Protocol rejection of the resulting four-byte token is a
separate owner requirement; no on-wire response is inferred from an EOF tag.

```sh
python3 tools/probe_pll_recovery.py --centered-dir build/pll-pid-guard-centered
python3 tools/probe_pll_token_tails.py --experiment build/pll-shared-recovery
python3 tools/probe_pll_first_edge.py --experiment build/pll-shared-recovery
```

The generated five-suite verifier requires exact corpus counts and zero
valid-packet errors, replacing the older snapshot's expected-rejection policy.
The complete-image control remains 1934 bytes and the 1280-byte goal remains
open; this reference still needs publication, framing/recovery-J, ownership,
response deadlines and the complete composed-image regression gate.

### Late PID poll repaired without changing the sampling calendar

The separately derived [PID-completion experiment](../tools/probe_pll_pid_completion.py)
fixes all 92 missing handoffs above. At each of three final-PID-one sites,
replace the current D-minus test and rejection jump with one two-clock RJMP.
The centered full-pin saved-K check remains. The removed test's successful
skip and the replacement both take two clocks, so EXTRA+6 and next FIRST+10
keep their original observation times. Register effects and the DATA graph
are unchanged; the three replacements save six bytes.

The resulting component is **7340 bytes at 0x0200**, body SHA256
`8d07720c576bf59f2974a9f971567f8d35b39c897adc96e2144c5e8981f437fb`,
ELF SHA256
`51b91da623acf6e19f3c4231eded43b3a41f9f64bb4946ed72a18f7660897853`.
GNU and LLVM bytes agree. All 1111 encoded relative edges are checked against
their actual source destinations, without program-counter wrapping.

The unchanged strict five-suite verifier passes all 24731 positive observations.
The combined SYNC/first-DATA/address matrix now also passes all 13464 cases,
with zero missing handoffs. The 41472-prefix, held-SE1, incomplete-EOP SE1 and
3456 injected + 3456 pristine token-tail gates remain strict and pass on the
same exact body. Source/model/ELF/body pins are checked before and after.

```sh
python3 tools/probe_pll_pid_completion.py --reference-dir build/pll-shared-recovery
python3 tools/probe_pll_first_edge.py --experiment build/pll-pid-complete --require-complete
python3 tools/probe_pll_pid_prefixes.py --experiment build/pll-pid-complete --suite whole-prefix
python3 tools/probe_pll_pid_prefixes.py --experiment build/pll-pid-complete --suite held-se1
python3 tools/probe_pll_pid_prefixes.py --experiment build/pll-pid-complete --suite eop-se1
python3 tools/probe_pll_token_tails.py --experiment build/pll-pid-complete
```

`--require-complete` fails on every candidate error, including a pre-existing
one. The default comparison mode remains available for historical diagnosis.
An independent root rebuild reproduces the exact body and passes the strict
13464-case gate. A negative control on the unchanged 7346-byte reference
returns nonzero with all 92 failures preserved, despite being regression-free
relative to the still older 5634-byte snapshot. The JSON records reception
success and relative regression status separately, with the first absolute
candidate failure retained for diagnosis.

A separate 3564-case diagnostic inserts K/J pulses into a nominally incomplete
ACK tail. Both bodies produce identical outcomes: 2885 reject and 679 reach
a decoded-D2/EOF tag. These altered raw-wave cases are preserved for further
framing analysis; the generator's original bit labels alone do not establish
that every altered waveform still represents an incomplete PID requiring
rejection. They are not a waiver or a complete error-handling qualification.

This fixes the measured acquisition/DATA boundary. It still supplies no SRAM
publication, complete framing/recovery-J, protocol/ACK owner or qualified full
loader. Those integrations and the complete-image gate remain required before
resuming size optimization toward 1280 bytes.
