# ATtiny88 Micronucleus+ memory and USB protocol

Fast and strict Pass7 use 8192 bytes of Flash, 64-byte Flash pages, 512 bytes of SRAM, and 64 EEPROM bytes. The bootloader starts at `0x1AC0`. Application bytes occupy `0x0000..0x1ABB` (6844 bytes); the four-byte reset postscript is reserved at `0x1ABC..0x1ABF`. Fast code ends at `0x1FE7`; the rest of the final reserved page remains unused. A different boot address requires rebuilding descriptors, vectors, and bounds checks.

The VID/PID pair is `16D0:0753`. Standard Micronucleus 2.x requests 0–4 retain their existing meanings: information, page address, application erase, four-byte Flash data, and application start. The stock CLI handles upload/vector patching; it does not implement the added memory reads and EEPROM operations.

All extension requests use endpoint zero and vendor IN `bmRequestType=0xC0`. The EEPROM request numbers borrow AVR ISP opcode values, but this is a USB vendor protocol, not arbitrary four-byte SPI ISP forwarding.

| Request | Code | wValue | wIndex | wLength | Reply |
| --- | --- | --- | --- | --- | --- |
| GET_INFO | `0x00` | 0 | 0 | 8 | Standard Micronucleus configuration |
| EEPROM read | `0xA0` | Address 0–63 | 0 | 1 | Stored byte; empty for invalid/busy access |
| EEPROM write | `0xC0` | Address 0–63 | Data byte, high byte zero | 1 | 0 accepted, 1 busy, 2 invalid |
| EEPROM readiness | `0xF0` | 0 | 0 | 1 | 0 ready, 1 busy |
| Application Flash read | `0xB0` | Byte address | 0 | 1–8 | Raw application bytes, or an empty reply for an invalid range |

EEPROM writes carry the payload in wIndex and have no USB OUT data stage. Poll readiness and verify readback before considering a write complete. Flash reads must end at or before the application limit, excluding both the postscript and bootloader. The compact historical 2.9 variant limits Flash reads to one byte per request.

GET_INFO bytes 0–1 encode programmable application capacity. Feature byte 6 includes EEPROM `0x40`, Flash read `0x80`, and retained MCUSR handling `0x20` (`0xE0` combined). GET_INFO byte 7 is the application version, not the USB descriptor's bcdDevice version. Fast/strict bcdDevice is `0x0208`; compact is `0x0209`.

Raw Flash readback includes the bootloader-patched RESET vector. It is not automatically an original application HEX suitable for re-upload. The host utility offers `--skip-reset-vector` when comparing a source application image against physical readback.

USB packet CRC16 is retained. The rejected Pass6 range-CRC requests are documented only inside their variant and archived handoff; they are absent from the selected fast/strict builds. The host should calculate checksums after reading memory.

Changing the V-USB handler requires rechecking instruction boundaries, branch targets, register liveness, W1C flag effects, and cycle traces for synchronization, NRZI, bit stuffing, EOP, and response entry. Those software checks do not replace physical USB measurements.
