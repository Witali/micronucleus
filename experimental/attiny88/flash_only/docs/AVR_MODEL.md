# AVR execution and cycle-count audit

The USB tests execute linked ATtiny88 instructions. The applicable core is
AVRe, not AVRxt, AVRxm or reduced-core AVRrc. Instruction counts follow the
[ATtiny48/88 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf),
section 25, and the AVRe columns of the
[AVR Instruction Set Manual DS40002198A](https://ww1.microchip.com/downloads/en/DeviceDoc/AVR-Instruction-Set-Manual-DS40002198A.pdf).

## Explicit instruction costs

tests35/avr_cycles.py defines an explicit cycle class for every operation
executed by this test backend. An unknown operation fails instead of falling
through to an assumed one-cycle cost. CPU.step cross-checks the inherited
timing layer against this independent classification. The archived compact
backend is retained unchanged.

| Instructions | ATtiny88 clocks |
| --- | ---: |
| Register/immediate ALU, MOV/MOVW, IN/OUT, bit transfer and flag instructions | 1 |
| RJMP/IJMP, ADIW/SBIW, SRAM loads/stores, PUSH/POP, SBI/CBI | 2 |
| RCALL/ICALL, LPM | 3 |
| RET/RETI, SPM instruction execution | 4 |
| Conditional branch | 1 untaken, 2 taken |
| CPSE, SBIC/SBIS, SBRC/SBRS | 1 without skip, 2 skipping one word, 3 skipping two words |

The table does not claim that every instruction is implemented by this
firmware-oriented backend. Unsupported semantics also fail explicitly.
ATtiny88 does not implement the absolute CALL/JMP or ELPM instructions.
Flash erase/program stalls are additional hardware behavior, separate from
the four-cycle SPM opcode; page-program transaction tests model that boundary.

BRBS/BRBC with offset zero still take two clocks when their condition is true.
The taken and untaken final PCs are identical, so comparing final PC to target
cannot determine this case's duration. The current model uses the prior SREG.

## Verified semantics and regressions

The audit corrected two inherited flag errors in the active test adapter:

- ADC sets Z from its own byte result. It does not chain the prior Z as
  SBC, SBCI and CPC do.
- NEG updates H from bit 3 of the result OR bit 3 of the original operand.

These changes modify tests, not firmware bytes. The ASR and zero-offset branch
corrections were already present and remain covered independently.

```sh
python3 -m tests35.test_avr_cycles
python3 -m tests35.test_avr_model
```

The fixed instruction/skip test executes 268 hand-encoded cases, including
fractional start phases. The clock guard compares the final time with start
plus the integer cost, avoiding cancellation from subtracting two doubles.
It also walks
every linked code instruction, excluding the known descriptor bytes, to
require an explicit timing class. At the 1382-byte default checkpoint this is
671 instructions and 49 mnemonics.

The flag/control suite covers 2097152 ASR cases, 20480 conditional branches,
1048576 ADC cases and 65536 NEG cases. Operand arithmetic and signed-range
checks supply independent expected flags; they are not copied from the model's
bitwise implementation. The ADC cases include both prior Z values and preserve
T/I. Existing emitted TX and sequential WRITE4/READ regressions also pass with
the corrected adapter.

## GPIO access phase

Cycle duration and peripheral access time are separate contracts. Datasheet
Figure 10-4 shows the input latch closing at the falling clock edge, PINxn
updating at the next rising edge and the IN result register updating one clock
later. The Python model reads that instruction-start PIN value, representing
external input sampled one half-clock earlier, and records output writes at
instruction completion. The synchronizer therefore has the documented
half-to-one-and-a-half-clock propagation delay.

An emulator exposing its IN hook after advancing one clock must retain the
instruction-start PIN value; it must not silently sample a newer PIN value.
The PCINT pipeline and write-one-to-clear ordering require separate device
fixtures. Neither instruction agreement between two emulators nor these
digital fixtures establishes analog USB compliance or a measured board clock.
