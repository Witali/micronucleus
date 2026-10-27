# Compact research protocol v5.6

Pass27 selects an exact byte cursor on the host. Use
`host/compact_programmer27.py`; the preserved Pass26 client still uses v5.5
four-byte block selectors and rejects the new descriptor IDs.

| EP0 vendor request | wValue | wIndex | Effect |
| --- | --- | --- | --- |
| `1 SELECT` | Ignored | Byte address, bit 15 selects EEPROM | Set shared byte cursor |
| `2 SELECT+ERASE` | Ignored | Page-aligned Flash byte address | Select and defer page erase |
| `3 WRITE4` | Data bytes 0/1 | Data bytes 2/3 | Write/stage four bytes; cursor +4 |
| `0xB0 READ8` | Ignored | Ignored | Return eight bytes; cursor +8 |
| `4 RUN` | Ignored | Ignored | Defer application handover |

For example, Flash byte address `0x0080` is SELECT wIndex `0x0080` (previously
`0x0020`). EEPROM byte address 8 is `0x8008` (previously `0x8002`). Data in
WRITE4 remains little endian. Standard USB requests retain the same interface.

## Host and MCU responsibilities

The host rejects out-of-range/unaligned selectors, EEPROM erases and Flash writes
crossing the identified bootloader boundary. It completes each Flash page before
switching memories; the low-level transport relies on this sequencing contract.
READ8/WRITE4 share one cursor, so do not read during unfinished writes. Reselect
and verify after an ambiguous USB result. Lost ACKs do not provide transactional
commit semantics.

All vendor operations return an empty reply without moving the cursor or queue
while EEPROM is busy; standard USB remains available. The AVR loads a ready
selected cursor directly, without block multiplication or an
EEPROM SELECT range decoder. Malformed EEPROM selectors can alias physical
EEPROM addresses. Its EEPROM WRITE4 low-byte range guard remains; a rejected
WRITE4 may overwrite inactive payload registers but starts no queue or IO.
The complete 16-bit Flash erase/write boundary guard remains on the AVR before
every page-changing SPM, including malformed EEPROM-tagged erase requests.

Both kinds of SELECT clear the inactive Flash page buffer (CTPB). A pending
EEPROM queue or any nonzero EECR prevents this operation. EEPROM SELECT leaves
an ignored marker; an invalid EEPROM SELECT+ERASE is rejected at the final Flash
boundary because the newly loaded cursor has its high memory flag set. It cannot
erase the previously selected Flash page. This does not preserve an incomplete
Flash page across a memory switch; that was already disallowed by the host flow.

WRITE4 loads its SETUP payload once into `r10..r13`. Flash consumes two words
immediately; EEPROM retains them for asynchronous service. A four-byte-aligned
Flash cursor uses bit 1 after each +2 as the two-word loop phase. `r1` can contain
data between the two SPM loads; it is zero again before any zero consumer, USB
poll, ABI crossing or shared return. The asynchronous EEPROM worker starts at
most one byte per call and returns without waiting on EEPE.

## Current measured research profiles

| bcdDevice | LED | BOOT_AT | Code bytes | App bytes excluding postscript |
| --- | --- | --- | ---: | ---: |
| `0x0560` | Off | `0x1B80` | 1148 | 7036 |
| `0x0561` | Active high | `0x1B40` | 1166 | 6972 |
| `0x0562` | Active low | `0x1B40` | 1164 | 6972 |

These values describe this checkpoint and must be updated with every admitted
candidate build. At the target address `0x1C00`, no LED uses 1144 bytes,
**120 bytes over 1 KiB**. No fitting or hardware-validated release is claimed.
The build command measures the source; it does not program a device.

The new client retains offline HEX preparation and the separate explicit
`--execute --i-have-isp-recovery` gates. Host tests use mocks and check all 2064
valid selectors, invalid aliases, complete Flash/EEPROM flows, cursor recovery,
RESET/postscript handling and profile rejection. The NVM tests execute compiled
opcodes across all Flash page positions/boundaries and all 65536 cursor values
in every LED profile. PHY timing and complete USB transaction admission are
separate gates; see the candidate development record.

## Flash programming quiet intervals

Page erase and page write halt the ATtiny88 CPU. After SELECT+ERASE and after
the final WRITE4 that automatically commits a page, the host must allow the
operation to finish before sending the next request. `program_application`
uses a 15-ms delay after each of those operations, then verifies the page by
reading it back. Low-level transport callers must provide the same scheduling.
The digital foreground service bound excludes the physical SPM halt; it does
not promise a USB response during Flash programming.

The accepted omission of incoming DATA CRC16 validation before ACK is recorded
in [docs/USB_PROTOCOL.md](docs/USB_PROTOCOL.md). Outgoing CRC16 is retained.
