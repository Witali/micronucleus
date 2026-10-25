# Micronucleus+ ATtiny88 — CRC extension (experimental)

Device: ATtiny88, external 16 MHz, Micronucleus+ with bcdDevice `0x0210`.
Previous requests `0x00–0x04` (Micronucleus), EEPROM `0xA0/0xC0/0xF0`, Flash read `0xB0` remain supported. The usual Micronucleus CLI still uploads applications; this firmware is flashed initially through ISP.

**CRC uses the existing V-USB bit-shift/XOR kernel** in `usb_crc16_append` (`L1aa0..L1aae`). Its 44-byte machine-code body is unchanged. Reflective polynomial `0xA001` (normal polynomial `0x8005`), init `0xFFFF`, refin/refout=true, xorout `0xFFFF`. Reference check: ASCII `123456789` → `0xB4C8`.

All extended requests use `bmRequestType=0xC0` (vendor, device, IN). On-wire integer fields are 16-bit USB little-endian. Addresses are byte addresses; intervals are **[start, end)** (start inclusive, end exclusive). Zero-length and backwards ranges are rejected.

| bRequest | wValue | wIndex | wLength | Return |
|---|---|---|---|---|
| `0xD0` | Flash start | Flash end-exclusive | 1 | `[status]`: 0 accepted, 2 bad range |
| `0xD1` | EEPROM start | EEPROM end-exclusive | 1 | `[status]`: 0 accepted, 1 EEPROM busy, 2 bad range |
| `0xD2` | bytes to process, 1..16 | 0 | 3 | `[status, crc_low, crc_high]` |

`D2.status`: 0 = in progress, 1 = complete, 2 = no job / invalid step, 3 = EEPROM busy. On every successful step the CRC in the reply is the **intermediate value**, or the final CRC when status=1. Additional D2 calls after completion return the same result. Only one CRC job exists at a time; D0/D1 replaces the preceding job. Starting any new upload or EEPROM write during a CRC job is not supported, because the memory may change while being checked.

Limits: Flash `0 <= start < end <= 0x19BC` (6588 application bytes; excludes four reserved reset bytes and bootloader), EEPROM `0 <= start < end <= 0x0040` (64 bytes). The current CRC state persists in SRAM across requests. The host should request chunks of 1–16 bytes; the Python CLI hides these steps.

## Sample host commands

```bash
python3 host/micronucleus_plus.py flash-crc 0x0000 0x1000 --chunk 8
python3 host/micronucleus_plus.py eeprom-crc 0x00 0x40 --chunk 8

# Compatibility mode: no firmware CRC request; read memory and calculate on PC
python3 host/micronucleus_plus.py flash-crc 0x0000 0x1000 --local
python3 host/micronucleus_plus.py eeprom-crc 0x00 0x40 --local
```

## USB timing warning

The physical USB RX/TX engine and its own CRC machine code are **byte-for-byte identical** to the previous Fast Pass 5. However, D2 adds time to the non-bit-level USB SETUP handler: measured with an AVR instruction-cycle simulator, **about 159 cycles (9.94 µs) for 1 byte; 774 (48.38 µs) for 8 bytes; 1488 (93 µs) for 16 bytes** on example data at 16 MHz. The exact count depends on the bit pattern. These delays may cause a host IN token to arrive before the loader resumes polling and **have not been proven USB-spec compliant**. No physical ATtiny88 USB line tests have been conducted. Do not flash to the only board or represent this firmware as hardware-qualified.

The `--local` method on the old firmware avoids all new CRC-related USB turnaround delays, at the expense of additional USB transfers and host-side calculation.
