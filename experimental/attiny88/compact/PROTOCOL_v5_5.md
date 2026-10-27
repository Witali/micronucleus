# Micronucleus+ compact protocol v5.5 (Pass26)

Experimental vendor control requests on EP0, ATtiny88 at 16 MHz, USB Low-Speed.
Private-protocol compatibility with older clients is intentionally dropped.
The host identifies profiles through the standard USB `bcdDevice` field.

## Addressing and requests

SELECT and SELECT+ERASE take a 16-bit four-byte-block selector in `wIndex`.
Bit 15 selects EEPROM (1) or Flash (0); the remaining bits are the block index.
The first byte address is `(selector & 0x7fff) * 4`. On the AVR, `r4:r5` holds
the shared byte cursor, with bit 15 retaining the EEPROM flag.

| bRequest | wValue | wIndex | Data | Action |
| --- | --- | --- | --- | --- |
| `0x01 SELECT` | Ignored | Block selector | None | Set shared cursor |
| `0x02 SELECT+ERASE` | Ignored | Page-aligned Flash block selector | None | Select and queue a 64-byte page erase |
| `0x03 WRITE4` | Bytes 0-1, little endian | Bytes 2-3, little endian | None | Stage four bytes; cursor +4 |
| `0xB0 READ8` | Ignored | Ignored | Eight bytes IN | Read at cursor; cursor +8 |
| `0x04 RUN` | Ignored | Ignored | None | Run the application |

USB Low-Speed DATA payloads are at most eight bytes. READ8 is one control-IN
transfer; WRITE4 carries its four bytes in the eight-byte SETUP itself.
In v5.4, READ8 instead took a selector in `wValue`; see `PROTOCOL_v5_4.md`.

SELECT `0x0020` sets Flash byte address `0x0080`. Three READ8 operations return
`0x0080..0x0087`, `0x0088..0x008f`, then `0x0090..0x0097` without intervening
SELECT. SELECT `0x8002` sets EEPROM byte address 8; the host must stop at byte 64.

For a Flash page, send SELECT+ERASE with a selector divisible by 16, wait for
SPM, then send sixteen WRITE4 operations. After another SPM wait, SELECT the
page again and verify with eight READ8 operations.

## EEPROM and error state

WRITE4 queues four EEPROM bytes in `r10..r13`. Byte writes run asynchronously
between USB polling periods. The next WRITE4 must wait for the previous queue.
The normal host path verifies blocks. Experimental `program_eeprom_stream()`
uses one SELECT for EEPROM, waits at least 50 ms after each block and rereads
the complete EEPROM. This fixed delay is not a validated READY signal; the
streaming mode is disabled by default and needs hardware validation.

Flash and EEPROM share one cursor. The host must prevent reads during unfinished
writes, since reads can change the write position. EEPROM READ8 while its queue
or EEPE is busy returns an empty reply without advancing the cursor. A short
reply invalidates the host cursor cache and requires reselection.

After a USB error, timeout or lost ACK, do not blindly repeat WRITE4. Reestablish
the address with SELECT and verify Flash/EEPROM. The protocol does not provide
transactional commit tied to a confirmed ACK. Reselect after changing memory,
seeking backwards or recovering from an error.

## Geometry, protection and standard USB

Flash is 8192 bytes, EEPROM 64 bytes, and Flash pages 64 bytes. The AVR retains
its erase/write bootloader-boundary check before SPM. Flash reads may include
the bootloader. The host prepares the application RESET vector and four-byte
postscript; application capacity is `BOOT_AT - 4`. Power failure during RESET
page erase may require external ISP recovery.

| bcdDevice | LED | BOOT_AT | Code bytes | Application bytes |
| --- | --- | --- | ---: | ---: |
| `0x0550` | Off | `0x1B40` | 1206 | 6972 |
| `0x0551` | Active high | `0x1B00` | 1220 | 6908 |
| `0x0552` | Active low | `0x1B00` | 1218 | 6908 |

GET_DESCRIPTOR, SET_ADDRESS, GET_STATUS, GET_CONFIGURATION, SET_CONFIGURATION
and GET_INTERFACE remain supported. Unknown profiles are rejected by the host
before private commands. Tested PHY substitutions preserve the audited cycle
schedules, but physical USB has not been validated. The inherited PHY may ACK
nonempty DATA before CRC16 validation.
