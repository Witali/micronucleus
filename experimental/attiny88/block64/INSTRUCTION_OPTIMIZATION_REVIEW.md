# AVR instruction and pointer review

Reviewed on 2026-10-26 for ATtiny88 / AVR25 at 16 MHz, standalone Clang AVR
assembler with GNU AVR linking, and the project's private register contract.
The MicroMusic AVR cookbook supplied the initial techniques, especially
`docs/avr-asm-cookbook/README.md`, `um88-page-fifo.md` and
`um88-flag-neutral-irq.md`. Its ATmega328P hardware-MUL examples do not apply
to ATtiny88. No MicroMusic source was changed or copied.

Instruction legality, flag effects and timings were checked against the
[Microchip instruction manual DS40002198C](https://www.microchip.com/content/dam/mchp/documents/MCU08/ProductDocuments/ReferenceManuals/AVR-InstructionSet-Manual-DS40002198.pdf).
The [AVR-LibC cookbook](https://avrdudes.github.io/avr-libc/avr-libc-user-manual/inline_asm.html)
is useful for operand restrictions; its GCC inline-assembly constraints are
not the calling convention of these standalone `.S` modules.

## One measured maintained-code candidate

`block_validate_page_range` proves that R16 is either zero (Flash) or one
(EEPROM). Owner selection can therefore use the bit directly:

```asm
; Existing: 8 bytes, four clocks on both valid inputs.
ldi  r18, OWNER_FLASH
tst  r16
breq block_write_set_owner
ldi  r18, OWNER_EEPROM

; Candidate: 6 bytes, three clocks on both valid inputs.
ldi  r18, OWNER_FLASH
sbrc r16, 0
ldi  r18, OWNER_EEPROM
```

An isolated assembly of the complete maintained source measured **1852 to
1850 bytes**. Actual-opcode probes tested both legal memory values against
all 128 relevant incoming flag combinations: 256 cases per version. Both
produce the same owner and preserve the other registers; the candidate also
preserves SREG. The existing TST result is dead before the next flag consumer.
This is a measured candidate, not an applied maintained-source change or a
complete regression run. It does not change the USB bit sampler.

| Isolated build | Body SHA-256 |
| --- | --- |
| Maintained baseline | `a3f600235ab49d66ef357a859b2d1cbd9bb98a873a9fcb0283748ce75dadb433` |
| Owner SBRC candidate | `ed859daa63309148fcf22481a265920ab50bc899fddd306869c3baf11d81fae5` |

## Pointer choices and their actual cost

| Technique | Finding in this project | Decision |
| --- | --- | --- |
| `LD/ST` with postincrement | RX, TX, EEPROM snapshots and Flash refill already combine access with pointer advancement. | Retain; avoid adding a separate ADIW. |
| `MOVW` for even register pairs | Already used for CRC pointers and word transfers; one instruction replaces two MOVs. | Use when both byte lifetimes permit it. |
| `LDD/STD Y/Z+q` | The 0x0100 context keeps hot fields within 63-byte displacement. Two-byte indirect instructions replace four-byte LDS/STS when the base is already live. | Count pointer initialization/restoration as well as the access. |
| Page-local pointer arithmetic | The 0x0116 RX buffer and at most 11 bytes cannot wrap YL. The isolated EOP path omits the YH borrow; Flash refill already advances ZL with SUBI rather than ADIW. | Requires a proved range, not just a typical address. |
| Make EOP Y equal context base | A possible streaming-only follow-up replaces low-byte rewind with LDI YL,0, restores Z using MOVW, and changes token displacements to +23/+24. | Potential one-clock valid-response saving; not implemented or waveform-proved. Early drop paths still need full Z restoration. |
| Move the 64-byte memory buffer to a 256-byte boundary | Can remove low-base conversions, but moves static buffer end from 0x0180 to 0x0240: 192 additional address-space bytes below the stack. | Do not pay that SRAM/layout cost for a few instructions. |
| Replace EEPROM pointer setup with MOVW from Y | Current LDI+ADD+LDI and MOVW+SUBI+ADD both cost three instructions/three clocks. | No isolated benefit. |
| Remove page-address ANDI | Alignment is validated upstream, but the shared SPM helper also provides a local page-alignment defense. | Retain that defense. |
| Replace SBIW Z,0 with OR | Existing full-pointer zero test is already two bytes; OR needs a disposable copy if Z must survive. | No improvement. |

The streaming receiver has competing pointer roles: Y advances through RX
SRAM, while Z indexes Flash CRC tables. X cannot directly replace arbitrary
Y/Z displacement accesses. Assigning more roles to index registers can add
save/restore operations or evict the PID/CRC state from registers.

## Keep the split CRC table pages

The split low/high 256-byte tables require two LDI and two LPM instructions
per lookup: eight clocks. An interleaved word table needs a doubled byte
index, its carry, and two LPM reads: nine clocks with LSL/LDI/ADC followed by
`LPM high,Z+` and `LPM low,Z`. It also writes arithmetic flags.
This is an instruction-cost comparison, not a newly assembled receiver.
`LPM ZL,Z` is defined; `LPM ZL,Z+` has an explicitly undefined result and
cannot be used as a shortcut.

MicroMusic's flag-neutral CPSE/SBRC and GPIOR backup recipes are useful
references, but this USB function already avoids a general SREG backup.
GPIOR0 retains reset causes. Using GPIOR1/2 for Y backup could shorten outer
entry/exit; it does not directly shorten DATA EOP-to-ACK, and would require
exclusive resource ownership plus a fresh synchronization-phase proof.

## Work that can follow the host response

CRC validity, recognized packet/token identity and free-buffer ownership
must be decided before ACK. Parsing vendor command fields and preparing
foreground work can follow packet acceptance. The existing design already
performs EEPROM service outside bit reception and starts blocking Flash SPM
only after the owning status ZLP is acknowledged and the bus is quiet.

RX publication can potentially follow ACK transmission if its count/token
are retained, the buffer stays reserved, and TX cannot overwrite that state.
The maintained TX uses R16..R22 and Y; simply moving the stores across it
would corrupt the transaction. Moving count/token to two additional live
registers costs two clocks before ACK to save four publication clocks, so
the maximum immediate saving is two clocks before extra dispatch/ownership
costs. This remains a design option, not an applied deferral.

The preferred immediate receiver repair uses direct EOP continuations for
each CRC pipeline stage, so it need not spend response clocks dispatching
on a stage number. All timing claims require the full waveform path,
including legal transition-free tails and the actual start of ACK.
