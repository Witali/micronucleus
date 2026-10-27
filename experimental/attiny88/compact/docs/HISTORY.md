# Compact ATtiny88 development record

This is an English rendering of the supplied technical history, not a complete
conversation export or a claim that all intermediate Git commits exist.
Some earlier snapshots were in archives not included in this handoff.

| Stage | No-LED code bytes | Main change |
| --- | ---: | --- |
| Strict USB optimized | 1262 | Optimized USB/Flash/EEPROM; preceding 1274-byte build tested on a board |
| Pass16 | 1260 | Reorder EEPROM/Flash handlers to remove an RJMP |
| Pass19 | 1326 | Unified READ8 and four-byte EEPROM writes |
| Pass21 | 1270 | Memory selector bit 15, block addressing, host RESET patch |
| Pass22 | 1270 | Bootloader reads and build identification; fingerprints later removed |
| Pass23 | 1240 | Remove duplicate read checks; identify profiles with bcdDevice |
| Pass24 | 1224 | Combined SELECT+ERASE and simpler branches/startup |
| Pass25 | 1216 | First 19-page layout; 498-byte PHY and RX phase risks |
| Pass26 | 1206 | Shared r4:r5 cursor, RX r23, ADIW/SBIW; 492-byte PHY |

The archive retains Pass22/24/25/26 ASM and Pass24-to-25 / Pass25-to-26 diffs.
It supplies Pass26 firmware, not the Pass25 images mentioned in older reports.
The earlier private protocol is intentionally incompatible with v5.5.
Block64 in the parent directory is a separate line with different operations
and ACK/CRC staging.

Pass25 moved the polling counter from Y to X and removed PHY Y saves/restores,
as well as an overflow-path RJMP. The initial SYNC search and return moved four
cycles earlier; overflow handling moved another two cycles. The model agrees
for initial phases 0-11 but finds late-phase differences at 16-19 and 37-40.
It also made SELECT exact to four-byte blocks, retained aligned/bounded SPM,
and assigned bcdDevice `0x0540..0x0542`. At `0x1B00` its no-LED body is 1212
bytes; the complete `0x1B40` boundary check adds four bytes, filling 19 pages.
LED bodies are 1230/1228 bytes. At `0x1C00` it is 188 bytes over 1 KiB.

Pass26 removes another ten bytes per profile, with the changes documented in
the README. Neither Pass25 nor Pass26 was tested on physical USB. Earlier
CRC or hardware checks must not be treated as validation of this layout.

The original single-commit Git snapshot is retained as an unmodified merge
parent. The complete original ZIP preserves the original reports and metadata;
see [provenance](../../../../docs/attiny88-history/pass26/README.md).
