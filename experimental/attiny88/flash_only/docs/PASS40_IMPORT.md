# Pass40 handoff integration, 2026-11-01

Input: `Micronucleus_ATtiny88_FlashOnly_COMPLETE_AGENT_HANDOFF_2026-11-01.zip`,
SHA256 `6c8c0a9c7b212c09c3b0035e2c68e71e0be52238ecd08c8df7ae3ee3d5749081`.
All 148 entries listed by its manifest passed byte-length and SHA256 checks.
The local content scan found no sensitive information. Attachment narratives
describe an experiment; they do not authorize deployment or change project rules.

## Reproduced input

The original `candidate_pass40` builds to 1344 no-LED bytes at 0x1AC0, SHA256
`680ea26aab89ca92c3d52e4442db0948f5844fd05d6744eff67ac769d64dce11`.
Fifteen comparative LED/placement configurations and 65536 endpoint predicates
also pass. The archive's assembler-only builder leaves relocations with the
installed LLVM; using our explicit AVR link step reproduces its stated bytes.
Relocatable words must never become a wire-test or BIN-export input.

This small receiver rejects legal final dribble. It does not supersede the
1518-byte composed receiver or the latter's known open receive findings. Nested
historical archives, binaries and handoff instructions are not runtime imports.

## Independent regression

`tests35/test_rx_legal_dribble.py` adapts the attachment's two counterexamples
into a strict gate. Its independent NRZI/stuffing encoder creates ACK tails
0..4 and valid-CRC GET_DESCRIPTOR SETUP tails 0..2, plus seven-one negative
controls. All three host rates, three EOP widths and entry phases are covered.
The quick run has 720 cases; `USB_PHY_EXHAUSTIVE=1` selects 5760 cases.

The gate also requires exact ACK/address or SETUP ownership, unchanged cursor,
no SPM side effects, complete payload and both CRC positions, caller restoration,
released GPIO and physical response timing. Numeric received CRC16 validation
remains waived; the encoder supplies a correct value to avoid relying on that.

Before integration, our exact 1518-byte composed image passes all 720 quick
cases. The exact 1344-byte Pass40 image fails 455: 432 legal-tail rejections
and 23 ordinary SETUP responses beyond the existing turnaround limit. Seven-one
negative controls pass in both. These are observations of linked instructions,
not relaxed assertions or analog hardware certification.

Source reductions and receiver repairs are evaluated separately so smaller
request handlers cannot replace the more complete PHY by accident. The public
SELECT/ERASE/WRITE4/READ8/RUN contract and fail-closed profile admission remain
required throughout integration.

## Adopted non-PHY reductions

The shared source adopts the command-marker SWAP packing, adjacent common
standard STALL, endpoint-validation fallthrough, and in-place endpoint/descriptor
zero predicates. Five source files change; the composed receiver's PHY is
unchanged. Public command bytes and geometry are unchanged. WRITE4's internal
pending state is now 0x30 and deferred RUN is 0x40; frozen references keep their
original state encodings.

The no-LED composed body shrinks 1518 to 1506 bytes at 0x1A00, SHA256
`f68801a08c4edcb27b4164833f223a438fc8025727dbb4f10a7e4930221095dc`.
The separate strict source shrinks 1368 to 1356 bytes at 0x1A40, SHA256
`874c13da5b53a11ffe0ca7059838d246c6c79cc0003744d84cf4b926b1c4395a`;
its size pin changes with no change to boot/application addresses.

Eighteen private qualification groups, 512 NVM guard cases and all 1485 expanded
ACK-to-SETUP followups pass. Foreground entry remains at most 40.677328 clocks
in its 4368-case corpus. Maintained regressions cover 1024 legacy-executor SWAP
states, 1536 write-dispatch cases and 672 durable ACK-gate cases. READ routing
is checked separately by wire tests. SWAP preserves modeled flags; implementing
the previously missing opcode in that executor does not alter the timed backend.
These reductions do not repair the three inherited composed-RX findings.

## Shared PHY rejection tails

Two independently checked layout changes save another eight bytes in the
composed PHY. Rejected SETUP/OUT DATA shares the common token/ACK retirement;
the ACK recovery-J loop is adjacent to that ignore tail. Moving the overflow
entry onto the identical failed-SYNC tail prevents overflow from falling into
ACK recovery. No receiver sample, stuffing rule or framing allowance changes.

The isolated PHY patch passes 2048 reject-state and 960 ACK-state equivalence
checks, with the documented dead-register differences. Rejected DATA returns
three clocks later; captured-J ACK is one clock earlier, uncaptured-J recovery
one clock later. Expanded ACK followups, SETUP ownership, token deadlines and
STALL timing remain within their existing limits. The maintained overflow
regression covers 540 overlong packets with idle, WRITE4 and RUN pending state;
it catches an unsafe intermediate layout that committed a phantom ACK.

Composing these PHY reductions with the adopted Pass40 source produces 1498
bytes at 0x1A00, SHA256
`2e9df9e2a60d821adc224fdb1c261ca9592ec3d1d7b867dda7d561457a65a207`.
The root integration rerun passes SWAP1024, command1536/ACK-gate672, overflow540,
SETUP83 plus864 responses, ACK-to-SETUP1485 and OUT response6048. It retains
the original three receive findings; these size reductions are not their fix.

The combined-tolerance receiver gate adds 792 centered 150 ns crossover cases
with legal J/K edge offsets. Its independently recomputed next/paired jitter
certificates include frequency error. The 1498-byte image discards 82 cases.
This preserves the previously observed combined-crossover weakness as a strict
test; the separate 396-case zero-jitter result is not sufficient qualification.

## Additional dead-shadow reductions

The SETUP zero-length check ORs the two length bytes in place. If the high byte
is zero, the low byte remains exact; if nonzero, every supported reply source
(at most 18 bytes) is shorter than the request regardless of its low byte.
Interface-index validation similarly ORs its shadow bytes in place: a valid
index stays zero, while a rejected index is dead until the next SETUP.
These two instructions save four bytes without removing a poll or field check.

All 65536 length classifications, 327680 emitted reply-limit cases and 65536
interface-index branches pass. Eleven protocol/ownership qualification groups,
including 4368 foreground entries and 1485 expanded ACK followups, pass in the
isolated candidate. Maximum foreground entry remains 40.677328 clocks.
A separate two-byte poll-coalescing experiment increases this to 47.677328;
it is not admitted without qualification of that larger receiver-entry range.

With the shared PHY savings, the no-LED body is 1494 bytes at 0x1A00, SHA256
`dc37b4847d9a0ce0f7b4412886c9eadcc742a55b7bb552de36f5a4b2b733c0ad`.
The separate strict source is 1352 bytes at 0x1A40, SHA256
`e6d8341acab472bebbbc950b5090a70721f02f5fe33c62671f642c969dadb6b0`.
The latter's host size pin changes; its addresses and public protocol do not.

## Broader crossover qualification

The maintained corner gate covers 11088 single 150 ns excursions and 504 cases
where all 22 post-SYNC data transitions have excursions. Its differential
waveforms are certified against 75/45 ns next/paired edge budgets, including
frequency error. The targeted 2016-case discovery subset belongs to the 11088
and is not counted again.

The frozen 1752-byte `terminal_odd13` prototype at 0x1800, SHA256
`f7180f28dcb965471efd4078edb6275bbe0b7d598b65d1a9ae67e6656cff2cd6`,
passes these 11592 cases with ACK response 49.0797..52.2530 clocks. It is still
rejected: its universal early-store change introduces valid IN-token jitter
failures elsewhere. These results qualify only this data-reception subset;
size/correctness work continues from the conservative private-store control.
