# Micronucleus+ Compact USB protocol v5.4 (experimental)

**Vendor control EP0.** USB Low-Speed, packets with payload <=8 bytes. SETUP uses eight bytes; READ8 transfers eight data bytes via control-IN. No physical USB test was performed.

| USB bRequest | wValue | wIndex | Payload / response | Action |
|---|---|---|---|---|
| 0x01 SELECT | ignored | 16-bit block selector | zero | Set next write address |
| 0x02 SELECT+ERASE | ignored | 16-bit *page-aligned* Flash block selector | zero | Select and queue erase of the 64-byte Flash page |
| 0x03 WRITE4 | bytes 0–1 little-endian | bytes 2–3 little-endian | zero | Stage four bytes to Flash or queue four EEPROM bytes |
| 0x04 RUN | ignored | ignored | zero | Run user application after pending operations |
| 0xB0 READ8 | 16-bit block selector | ignored | exactly 8 bytes | Read Flash or EEPROM (two adjacent four-byte blocks) |

Bit 15 of selector chooses EEPROM (`1`) versus Flash (`0`); remaining 15 bits represent the index of a 4-byte block. Address of first byte = `(selector & 0x7fff)*4`. Physical ATtiny88 geometry: 8192 B Flash, 64 B EEPROM, 64 B Flash page. The host validates legal ranges and prepares RESET and four-byte postscript before writing.

Compared with v5.3: Flash `SELECT` no longer discards low four bits of the block index; for `SELECT+ERASE`, the PC program explicitly enforces page alignment. The NVM worker still aligns the **actual SPM page address** and blocks all pages whose start is at or above the identified bootloader boundary. This change does NOT permit programming bootloader Flash through USB.

Host-selected variants from USB device descriptor `bcdDevice`: `0x0540` = no LED, `BOOT_AT=0x1B40`, code1216/app6972; `0x0541` = LED active-high, `BOOT_AT=0x1B00`, code1230/app6908; `0x0542` = LED active-low, `BOOT_AT=0x1B00`, code1228/app6908. Unknown versions are rejected without vendor commands.

Never upload `firmware/Pass25_*_ISP_FRESH_EXPERIMENTAL.hex` as a user application: those HEX files contain the bootloader and RESET redirect and require external recovery facilities.
