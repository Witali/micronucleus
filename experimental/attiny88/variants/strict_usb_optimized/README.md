# Strict USB size-optimization candidate

This separate development variant starts from the named/constant-based source
and restores the hardware-verified strict USB engine and packet/reset fixes.
Its initial no-LED build reproduces the deployed 1344-byte image exactly:
`ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc`.
The pinned deployed image and historical variants remain unchanged.

## Results

Compared with `build_verified.py`, using the board's default PD0 LED wiring:

| LED mode | Before: code bytes | Candidate: code bytes | Candidate reserved bytes | Candidate application bytes |
| --- | ---: | ---: | ---: | ---: |
| Off | 1344 | 1326 | 1344 | 6844 |
| Active high | 1364 | 1344 | 1344 | 6844 |
| Active low | 1362 | 1342 | 1344 | 6844 |

All three candidates start at `0x1AC0`. The enabled-LED builds previously
needed 1408 reserved bytes at `0x1A80`, leaving 6780 application bytes. They
now recover one 64-byte page for the application. The no-LED candidate saves
18 code bytes; its page reservation and application capacity stay the same.
For other ports, the shared DDRD exit optimization does not apply. Tested
custom active-high PB3 uses 1346 bytes at `0x1A80`; active-low PA3 uses 1344
bytes at `0x1AC0`.

| Focused change | Code bytes saved | Preserved condition |
| --- | ---: | --- |
| Erase loop reuses SUBI/SBC's zero flag | 2 | LDI/OUT/SPM preserve SREG; the next dispatcher overwrites other arithmetic flags |
| Device-info/configuration replies share pointer/status tails | 6 | Same lengths, pointers, payloads and SRAM/Flash selection |
| EEPROM ready/busy tails share code; accepted status reuses a proven zero | 4 | Address/index/page-buffer guards and the consecutive EEMPE/EEPE sequence remain |
| Inline the sole CRC invocation | 4 | All 42 computation bytes remain identical; remove only RCALL/RET |
| Startup falls directly into main | 2 | Explicit stack initialization and SRAM clearing remain |
| Port-D LED exit shares the existing DDRD release | 2 with LED | LED is off and released before application entry; other-port LEDs retain explicit release |

The 516-byte USB engine is unchanged. The five-millisecond polling interval,
SE0/reset detection, pending-edge service latency, receive sample points,
transmit NRZI/stuffing and EOP timing retain the deployed implementation.
The CRC call removal shortens main-loop preparation by seven CPU cycles; it
does not change the bit engine or on-wire bit periods. Watchdog reset handling,
RESET-word protection and Flash/EEPROM range checks are retained.

From `experimental/attiny88/updater`:

```sh
python3 build_optimized.py --led off
python3 build_optimized.py --led on
python3 build_optimized.py --led active-low
node test_usb_packets.mjs build/optimized-off/firmware.json
```

The builder uses the same official Microchip C header, semantic labels and LED
macros as the maintained sources. `-D` supports `LED_PIN`, `LED_DDR_IO`,
`LED_PORT_IO` and `LED_BLINK_MASK`; `--output-dir` keeps custom builds separate.
Outputs contain the body, firmware manifest and fresh-device ISP HEX.
No build command programs a physical device.

For each build, the 516-byte receive/transmit engine must match the deployed
strict image byte for byte. The 42-byte CRC computation must also match; its
call/return arrangement may be optimized outside the bus bit engine. Page
reservation and reported application capacity derive from the resulting
size. Changes to code paths are recorded as focused commits and must pass
model checks before considering physical installation.

## Validation, October 25, 2026

`test_optimized.mjs` executes the actual candidate opcodes with the read-only
MicroMusic ATtiny88 CPU and an explicit local NVM shim. Each of five profiles
(three board modes plus two custom ports/masks) passes:

- 3072 standard-request comparisons against the deployed image, including
  directions and short/long lengths; descriptor transfers spanning packets
  and independent USB CRC-16 checks.
- Actual Flash page-buffer fill, all application-page writes/readback/erase,
  forced RESET-vector protection and invalid page-write rejection.
- Pattern write/read/erase through every EEPROM address, invalid addresses,
  high-index rejection, busy status and rejection during partial Flash fill.
- Entry through the reset trampoline with nonzero registers/SRAM, explicit
  stack initialization, 1024 LED ticks, GPIO isolation and application exit.

The existing packet test also passes its 18 complete SETUP-to-TX cases and
five reset-flag/watchdog cases for all five profiles.

`test_optimized_timing.py` compares each board mode with the deployed strict
body: 600 TX waveforms with identical PORTD/DDRD levels and cycle timestamps,
500 RX synchronization contexts, 15 PID/handshake cases, complete idle/reset
poll intervals and all 15 phases of poll-to-handler arrival. Build-time
comparison independently requires exact USB-engine and CRC-core bytes.

`test_optimized_erase.py` runs each board mode with simavr's independent CPU
and native SPM, using the existing ATmega88 substrate restricted to tiny88
RAM and 64-byte NORWW pages. All 107 descending application-reservation pages
erase correctly, every SPM preserves SREG, loader bytes remain intact and
invalid page writes are rejected. This check uses no Flash-controller shim.

From the updater directory:

```sh
node test_optimized.mjs build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
python3 test_optimized_timing.py build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
python3 test_optimized_erase.py /path/to/simavr-source build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json

python3 build.py --firmware-manifest build/optimized-on/firmware.json --output-dir build/updater-optimized-on
node test_micromusic.mjs build/updater-optimized-on
python3 test_simavr.py /path/to/simavr-source --build-dir build/updater-optimized-on
```

USB updater applications for all three board modes also pass byte-exact
installation and fuse/CRC/readback failure checks in MicroMusic and simavr.
MicroMusic additionally checks five interrupted-operation restarts. Each
updater ends at `0x0816` and embeds 1344 bytes, including padding where needed.
The existing updater's first-page power-failure limitation still applies.

Body SHA-256 values:

```text
177a380bfd516491226f060e582a617680b7bf0dabde33dbe9c1db5ccaa4a931  optimized-off/bootloader.bin
35c0ef9aa5d2193938b9a31ffe4beefb58b3c997e09dbf1e39794d02409d4718  optimized-on/bootloader.bin
5df6fb2fdd49e9570e4b720ae80836194ce8409defbe28aa894ddcbf96a8e075  optimized-active-low/bootloader.bin
```

These are instruction/model results. No physical board was programmed or
hardware-validated during this optimization task. The default verified
builder and released updater still target the previously tested image;
`build_optimized.py` explicitly selects this new candidate.
