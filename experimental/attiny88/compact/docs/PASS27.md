# Modular compact candidate, Pass27

The active development source now follows the neighboring Block64 organization.
The original Pass22/24/25/26 checkpoints and Pass26 release images remain the
comparison references. This candidate is not a released or hardware-tested build.

The current checkpoint is **1096 bytes at `0x1C00`**, still **72 bytes above
1 KiB**. Its fitting no-LED placement is `0x1B80`, 1100 bytes in 18 pages.
Earlier checkpoints below retain the scope of their isolated measurements.

| Source | Responsibility |
| --- | --- |
| `source/micronucleus_t88_compact.S` | Descriptors, RESET/startup, polling, deferred SPM and app handover |
| `source/device_attiny88.inc` | Hardware, LED configuration, SREG bits, Flash geometry and clock |
| `source/compact_protocol.inc` | USB context, private requests, descriptors and timing constants |
| `source/vusb_phy.inc` | Low-Speed NRZI, stuffing, synchronization and bus handshakes |
| `source/vusb_ep0.inc` | SETUP dispatch, reply preparation, length limiting and payload CRC |
| `source/vusb_standard.inc` | Standard USB requests |
| `source/compact_memory.inc` | SELECT, combined erase, WRITE4 and RUN |
| `source/compact_eeprom.inc` | Four-byte queue and asynchronous single-byte service |

Comments describe procedure inputs/outputs, register lifetimes, deferred effects,
stack cost, boundary checks and timing assumptions. The split itself preserved
the exact binary SHA-256 and non-linker symbol maps for all nine combinations of
three LED modes and BOOT_AT `0x1B00`, `0x1B40`, `0x1C00`.

## First measured checkpoint

At `0x1C00`, no LED uses **1182 bytes**, down from Pass26's 1202: still **158
bytes over the 1024-byte goal**. At the fitting `0x1B40` placement it is 1186
bytes. At `0x1B00`, active-high/low profiles are 1200/1198 bytes. All three at
`0x1C00` remain research measurements, not installable 1-KiB releases.

The net non-PHY saving is ten bytes: share EEPROM readiness checks, classify
deferred SPM erase/write operations by their defined opcode bits, simplify vendor
dispatch, shift the four-byte EEPROM register queue, and use STD for bus-reset
context stores. Explicitly reject opcode zero and unknown OUT requests before
they can become pending SPM commands.

The PHY saves six bytes by replacing its permanently zero input-buffer offset
calculation with a fixed Y=`0x0116` load and a call to the existing bare RET.
Two LDIs plus RCALL/RET take the same nine cycles as PUSH/LDS/LDI/ADIW/POP.
Peak stack use rises by **one byte**. A raw-opcode audit checks unchanged branch
targets, sampling-path instructions and dead arithmetic flags before redefinition.

The remaining four-byte saving replaces two absolute STS stores with STD in the
bus-reset path: every predecessor establishes Y=`0x0100`. This changes only the
instruction encoding; both stores still take two cycles on this AVR.

The handoff header omitted SREG_N and SREG_S. Pass26 therefore contains undefined
ELF symbols and encodes three intended N/N/S branches as C branches. Pass27
defines the actual bit positions 2 and 4 and checks the emitted instruction bits.
This fixes a correctness defect without reducing size. The candidate build now
rejects all undefined ELF symbols, not only remaining AVR relocations.

## Verification and open work

### Persistent EP0 state checkpoint

Keep the reply byte pointer in `r14:r15`, which every PHY/NVM path preserves.
Three paired SRAM loads/stores become MOVW, saving six bytes. Keep the DATA PID
in `r9`, initialized by each SETUP, saving two bytes when toggling/publishing a
packet. Share the one-byte standard reply tail for another two bytes.

The former pointer bytes at context offsets 16/17 become permanent zeros.
GET_STATUS and GET_INTERFACE reply from this pair, while GET_CONFIGURATION reads
its live context byte directly. This removes four more bytes. The previous
scratch pair 10/11 cannot be permanent zero: an eight-byte TX packet writes its
CRC there. The new zero bytes lie outside both TX and RX write ranges.

`PASS27_REGISTERS.log` records 13824 complete standard SETUP/TX payload/state
cases, 2658 extra stateful transfers (including all descriptor wLength values
0..256), 675 payload/independent-CRC/register-cursor cases, NVM/boundary checks
and all cursor cases. Assertions cover DATA PID alternation, remaining lengths,
repeated configuration changes and poisoned old CRC scratch bytes. These tests
replace comparison of incidental scratch writes with observable USB replies.

Separate waveform work has identified inherited TX bit-rate and driven-J timing
defects. These checkpoints establish neither specification timing nor electrical
USB admission; those require their own corrections and verification.

### Byte-cursor and shared NVM checkpoint

[Protocol v5.6](../PROTOCOL_v5_6.md) moves selector range/alignment work to a
separate host client and removes the four-byte block decoder. The MCU retains
its final Flash erase/write guard and EEPROM WRITE4 low-byte bound. Both memories
share an inactive SETUP payload load; Flash consumes two words using its guaranteed
alignment as the loop phase, then restores r1 before returning. A nested CPSE/SBIC
worker gate replaces a separate empty-queue branch. READ8 reuses its length as
the ADD/ADC cursor increment and does not borrow Z.

This checkpoint saves 48 more bytes relative to the EP0 register checkpoint.
No LED is 1124 bytes at `0x1B80`; LED high/low are 1142/1140 at `0x1B40`.
Host profile sizes and default source placement match those fitting builds.
The new NVM/host tests replace candidate tests that assumed v5.5 block selectors;
the original Pass26 fixtures and client remain unchanged. In addition to complete
EP0/PHY checks, every LED profile executes all 65536 cursor increments, legal and
malformed selectors, all application-page write positions, protected-page erases
and commits, EEPROM bounds/busy transitions and complete mocked programming.

### Shared busy gate and reply tails

One vendor-entry busy check now precedes READ8, SELECT, WRITE4 and RUN. It returns
an empty response without moving the cursor or queue while EEPROM is busy;
standard USB requests remain available. The deferred SPM/RUN gate is still
separate. With only two readiness checks left, inlining IN/OR at both sites is
two bytes smaller than retaining their RCALL/RET helper.

Place the NVM fragment immediately before EP0 so vendor READ8 can fall through
and the other requests use a short backward branch. An explicit main-loop jump
skips the relocated NVM fragment; tests try all 256 stale request-register values.
The standard unsupported-request path and rejected EEPROM address path also
share one empty-reply jump. Combined, these changes save ten bytes relative to
the 1120-byte checkpoint. Fitting profiles are now 1114/1132/1130 bytes.

```sh
sh verify27.sh
python3 build_candidate.py --require-fit
```

The second command is the explicit fit gate and currently **fails**. It must pass
before claiming the goal. `verify27.sh` checks software regressions and reports
the over-budget measurements without labeling them a fitting release.

The candidate runner covers 13824 differential standard-request cases, complete
SETUP-to-staged-TX standard replies with an independent USB CRC16 reference,
all supplied NVM/cursor/erase/TX opcode scenarios and rejection of unknown vendor
commands. The PHY audit checks 60 normalized branch targets and 66 flag-liveness
states per profile. LLVM unknown-instruction groups are split at actual AVR word
boundaries before emulation; decoding is cached by ELF modification time/size.

The first candidate used v5.5 selectors; the current source uses v5.6 and
`host/compact_programmer27.py`. `bcdDevice=0x0560..0x0562` remains reserved for
development. The preserved Pass26 host profile table is unchanged; no Pass27
device programming is part of this checkpoint.
Physical USB, retry/ACK/CRC admission and power-loss behavior remain unproven.
Next work must reduce the remaining code, integrate the corresponding host
geometry/protocol, and preserve the final AVR erase/write boundary guard.

### Shared startup loop checkpoint

After the [descriptor-backed reply change](PASS27_REPLY_SOURCES.md), reuse the
SRAM-clear cursor as the USB disconnect-delay outer counter. Each of 44 delay
iterations clears one context byte. This removes a separate clear loop and the
outer R18 counter, saving six bytes without changing the final RESET state.
The inner count is 27359; emitted opcodes hold D- low for 300.965562 ms at 16 MHz.
MCUSR capture and watchdog disable precede the delay; PCINT is enabled after it.

`tests27/startup_init.py` executes the emitted outer-loop and initialization
instructions with poisoned registers/SRAM. It verifies the exact clear range,
watchdog write order/window, preserved RESET flags, cursor/queue initialization,
Y=0x0100, disconnect duration and final PCINT enable. The inner countdown alone
is accelerated after checking its exact SBIW/BRNE opcodes and cycle count.
All three LED profiles pass. Fitting sizes are now 1100/1118/1116 bytes.

Partially rolling the six RX SYNC probes was also tested and rejected. Two-,
three- and four-probe loop variants save 2..6 bytes but corrupt or overflow a
valid packet at legal receiver jitter. The acquisition probes remain unrolled;
the startup saving does not change USB sampling or transmission instructions.
