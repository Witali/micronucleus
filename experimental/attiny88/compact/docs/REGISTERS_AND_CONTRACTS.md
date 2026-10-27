# Pass26 registers and invariants

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
