# ATtiny88 Micronucleus+ memory and USB protocol

The ATtiny88 has 8192 bytes of Flash, 64-byte Flash pages, 512 bytes of SRAM, and 64 EEPROM bytes. The current optimized profiles start at `0x1B00`, exposing application bytes `0x0000..0x1AFB` (6908 bytes) and reserving the four-byte reset postscript at `0x1AFC..0x1AFF`. Earlier fast/strict Pass7 and the pinned verified build start at `0x1AC0`, exposing 6844 application bytes with the postscript at `0x1ABC..0x1ABF`. Historical Fast code ends at `0x1FE7`. A different boot address requires rebuilding descriptors, vectors, and bounds checks; use the selected firmware manifest for host bounds.

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

## EEPROM readiness and write sequencing

The hardware readiness rule comes from the [Microchip ATtiny48/88 datasheet, sections 5.3.4 and 5.4.4](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf): `EECR.EEPE` is one during a write and hardware clears it when the operation completes. The optimized handler samples this bit with `SBIC`, returning exactly `0x00` when ready or `0x01` when busy. Other EECR bits do not affect the reply. This is a nonblocking snapshot; the host polls again if busy. A write completing just after the sample may produce one final busy reply.

Request `0xF0` is this project's USB vendor extension. Its request number borrows an AVR ISP opcode; it does not make the USB transfer a standard USB request or an ISP transaction. The ready/busy values above are the explicit host contract.

Write status zero means **accepted**, not completed. The host must poll `0xF0` until ready and then read back the byte with `0xA0`. The write handler checks EEPE before touching the EEPROM address/data registers. Interrupts remain disabled, erase-and-write mode is selected, and consecutive `SBI` instructions set EEMPE then EEPE within the required four-cycle window. Flash erase/write stalls the ATtiny88 CPU until completion; page-buffer SPM finishes before another USB SETUP is handled. An unfinished Flash page buffer is separately rejected because an EEPROM write could destroy its staged data.

The opcode model checks all 256 EECR bit combinations and completion immediately after the readiness sample, in addition to EEPROM write/read/erase and invalid/busy-access cases.

## Flash and USB reply integrity

GET_INFO bytes 0–1 encode programmable application capacity. Feature byte 6 includes EEPROM `0x40`, Flash read `0x80`, and retained MCUSR handling `0x20` (`0xE0` combined). GET_INFO byte 7 is the application version, not the USB descriptor's bcdDevice version. Fast/strict bcdDevice is `0x0208`; compact is `0x0209`.

Raw Flash readback includes the bootloader-patched RESET vector. It is not automatically an original application HEX suitable for re-upload. The host utility offers `--skip-reset-vector` when comparing a source application image against physical readback.

USB packet CRC16 is retained. The rejected Pass6 range-CRC requests are documented only inside their variant and archived handoff; they are absent from the selected fast/strict builds. The host should calculate checksums after reading memory.

Changing the V-USB handler requires rechecking instruction boundaries, branch targets, register liveness, W1C flag effects, and cycle traces for synchronization, NRZI, bit stuffing, EOP, and response entry. Those software checks do not replace physical USB measurements.
