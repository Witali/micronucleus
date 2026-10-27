# Registers and invariants

## Current compact candidate

The active source uses R2 as the remaining asynchronous EEPROM byte count;
R8 is free and is poisoned by regression fixtures. Startup clears the count
and deferred command together with MOVW R2,R24 after the countdown reaches zero.
R3 holds only 0 (idle), 2 (SELECT), 3 (erase), 4 (RUN), or 5 (page commit).
The dispatcher consumes R3 directly; all public opcode/prior-state transitions
are checked before relying on its bit pattern.

R9 holds the DATA PID. R14:R15 is the reply byte cursor, with R15 bit 7 selecting
EEPROM. The PHY and NVM worker preserve these registers. R4:R5 remains the shared
memory cursor; SELECT uses a byte address. Current layout/profile rules are in
[APPLICATION_LAYOUT.md](APPLICATION_LAYOUT.md), and size/timing evidence is in
[PASS29.md](PASS29.md); the preceding checkpoint is [PASS28.md](PASS28.md).

Every external PHY call requires the full Y pointer to equal USB_CONTEXT_BASE.
Entry copies Y into Z; no RX/TX instruction modifies that Z base. Every external
return restores Y with MOVW. Foreground instructions after startup preserve Y,
and both emitted-code and synchronized-execution checks enforce this contract.

Context byte CTX_INPUT_BUFFER_OFFSET (14) is a permanent zero after startup.
The current PHY loads it in useful two-cycle delay slots. No runtime context
writer may repurpose that byte; the emitted-code audit enforces this invariant.
NONE additionally preserves zero non-USB DDRD bits from RESET, allowing atomic
EOP release to use the same zero. LED profiles retain dynamic DDR preservation.

The shared SETUP validator has exactly one caller frame on either entry. Its
accepted path POPs two return-address bytes before capturing fields; the main
length fast path creates that frame with RCALL. Ordinary data PUSH/POP and
RCALL/RET use one physical stack in both current executors. Field capture must
see an empty stack, including when a fresh SETUP replaces a partial reply.

## Archived Pass26 contract

The table, selector encoding and profile addresses below describe the imported
Pass26 checkpoint, not the active Pass28 source or installed compact 3.0 loader.

| Register | Live state / reuse |
| --- | --- |
| `r1` | Zero after startup; must remain zero when consumed |
| `r2` | USB reply source, Flash/SRAM/EEPROM, using bits 0 and 7 |
| `r3` | Deferred Flash/SPM operation after the control exchange |
| `r4:r5` | Persistent byte cursor; r5 bit 7 selects EEPROM; SELECT sets, READ8 +8, WRITE4 +4 |
| `r6:r7` | Idle/poll interval, preserved by the PHY |
| `r8` | Remaining queued EEPROM bytes |
| `r10..r13` | Four-byte EEPROM write queue while active |
| `r23` | PHY RX length; dead after RX and reinitialized for TX/CRC |
| `X = r26:r27` | Main-loop USB poll counter; reply-builder write pointer |
| `Y = r28:r29` | Main USB SRAM context; PHY RX/TX pointer |
| `Z = r30:r31` | Temporary Flash/SPM/USB pointer, including LPM/SPM/LD Z+ |

X/Y/Z are reused across phases, not global user-memory cursors. Reloads can be
removed only after proving liveness and absence of intervening pointer writes.
Saving/restoring pointers through SRAM or the stack can cost more than using
the otherwise free persistent `r4:r5` pair. Consult ASM comments for local lifetimes.

## Memory

- ATtiny88: Flash 8192 bytes, EEPROM 64 bytes, Flash pages 64 bytes.
- SELECT wIndex bit 15 selects EEPROM; lower bits index four-byte blocks.
  Block-to-byte conversion happens only at SELECT.
- READ8 consumes eight bytes; WRITE4 consumes four. USB errors invalidate the
  host cursor and require result verification and reselection.
- EEPROM READ8 while busy may return an empty response without cursor movement.
- SELECT+ERASE is Flash-only, with a page-aligned selector. Actual SPM alignment
  and bootloader-boundary protection must stay on the AVR.
- APP_END is BOOT_AT minus a four-byte postscript. The host prepares RESET.
- No LED uses `0x1B40`; LED profiles use `0x1B00`. bcdDevice `0x0550..0x0552`
  identifies layout. Use `firmware/manifest.json` as the release reference.

## Timing and audit points

At 16 MHz, one 1.5-Mbit/s USB bit is about 10.6667 CPU cycles. Equal instruction
counts alone do not prove equal sampling phase. Pass25 starts SYNC search four
cycles earlier; late phases differ in its model. Pass26 substitutes a two-cycle
pause for PUSH r19, moves the counter to r23 and removes the post-RX POP.
Its audited bit-loop schedule is preserved, with an earlier handler return.

RX ADIW equivalence covers 256 offsets; TX SBIW equivalence covers all 65536
addresses and the required flags. `audit_phy26.py` checks allowed opcode changes
and branch targets. The arithmetic, cursor, NVM and host-stream tests cover
the corresponding instructions/state. None measures an electrical USB signal.
