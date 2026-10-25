# Strict USB size-optimized ATtiny88 bootloader

This separate development variant starts from the named/constant-based source
and restores the hardware-verified strict USB engine and packet/reset fixes.
Its initial no-LED build reproduces the deployed 1344-byte image exactly:
`ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc`.
The pinned deployed image and historical variants remain unchanged.

## Results

Compared with `build_verified.py`, using the board's default PD0 LED wiring:

| LED mode | Verified code bytes | Optimized code bytes | Boot address | Reserved bytes | Application bytes |
| --- | ---: | ---: | --- | ---: | ---: |
| Off | 1344 | 1274 | `0x1B00` | 1280 | 6908 |
| Active high | 1364 | 1296 | `0x1AC0` | 1344 | 6844 |
| Active low | 1362 | 1294 | `0x1AC0` | 1344 | 6844 |

The no-LED build reaches the 20-page target, freeing another 64 application
bytes compared with the previous 1314-byte candidate. It saves 70 code bytes
against the pinned 1344-byte image, with six padding bytes in its reservation.
LED builds retain 21 pages; the original verified LED builds needed 22 pages.
For other ports, the shared DDRD exit optimization does not apply. Tested
custom active-high PB3 with mask `0x80` uses 1294 bytes; active-low PA3 with
mask `0x03` uses 1296 bytes. Both start at `0x1AC0`. Single-bit PD0 masks
use 1292 bytes active high or 1290 active low. A single-bit mask automatically
selects an eight-byte LED tick instead of the generic twelve-byte tick;
the default mask `0x4C` and its behavior remain unchanged.

The latest instruction changes remove 36 bytes from the previous
1314/1332/1330-byte candidates. Moving the no-LED build to `0x1B00` saves
four more bytes because its Flash-write bound needs only a high-byte compare.
All profiles retain Flash programming/readback and all EEPROM commands.
The [current optimization plan](OPTIMIZATION_PLAN.md) records completed work
and the remaining optional LED page target.

| Focused change | Code bytes saved | Preserved condition |
| --- | ---: | --- |
| Erase loop reuses SUBI/SBC's zero flag | 2 | LDI/OUT/SPM preserve SREG; the next dispatcher overwrites other arithmetic flags |
| Device-info/configuration replies share pointer/status tails | 6 | Same lengths, pointers, payloads and SRAM/Flash selection |
| EEPROM ready/busy tails share code; accepted status reuses a proven zero | 4 | Address/index/page-buffer guards and the consecutive EEMPE/EEPE sequence remain |
| Inline the sole CRC invocation | 4 | Remove RCALL/RET without changing CRC arithmetic or output |
| Startup falls directly into main | 2 | Explicit stack initialization and SRAM clearing remain |
| Port-D LED exit shares the existing DDRD release | 2 with LED | LED is off and released before application entry; other-port LEDs retain explicit release |
| Initialize the CRC pointer directly in X | 2 | Removed the obsolete MOVW before the later single-pass merge |
| Reuse the expired disconnect counter to clear R4:R5 | 2 | The last SBIW proves R24:R25 zero; MOVW runs after USB release, preserving disconnect duration |
| Three PCIFR clears use SBI instead of LDI/OUT | 6 | Two cycles in either form; only PCIF2 is affected; removed R17 values are dead |
| Token publication uses STD Z+20 instead of STS | 2 | Two cycles in either form; control-flow analysis proves Z=0x0100 |
| Single-bit LED masks use paired skips | 4 with a single-bit mask | All eight masks and both polarities preserve GPIO levels for every counter value |
| Compare Flash start against APP_LIMIT-length with CP/CPC | 2 | Complete unsigned 16-bit comparison; compile-time no-borrow guard |
| Dispatch only exact-length SETUP packets | 4 | Token and complete 11-byte receive packet required before memory commands |
| Unsupported standard requests share the empty-reply tail | 2 | Same zero-length response; next SETUP resets Flash/SRAM selection |
| Clear SRAM backwards through Y and retain its context pointer | 4 | Same 44 SRAM bytes, explicit stack setup and disconnect duration |
| Merge payload copying with CRC calculation | 24 | Original inverted recurrence, packed byte/bit counter, polynomial low byte from YH, packet length from final XL |
| Place no-LED loader at the zero-low-byte boundary | 4 | Same Flash protection using the shorter high-byte comparison |

The USB engine shrinks from 516 to 508 bytes through exactly four audited
substitutions. Every other opcode/operand and logical branch target must match
the deployed engine. The five-millisecond polling interval,
SE0/reset detection, pending-edge service latency, receive sample points,
transmit NRZI/stuffing and EOP timing retain the deployed implementation.
Reply preparation is at least nine cycles faster than the deployed body in
9196 Flash/SRAM test vectors; bit periods remain unchanged. Watchdog reset handling,
RESET-word protection and Flash/EEPROM range checks are retained.

From `experimental/attiny88/updater`:

```sh
python3 build_optimized.py --led off
python3 build_optimized.py --led on
python3 build_optimized.py --led active-low
python3 build_optimized.py --led on -D LED_BLINK_MASK=0x80 --output-dir build/optimized-one-bit-high
node test_usb_packets.mjs build/optimized-off/firmware.json
```

The builder uses the same official Microchip C header, semantic labels and LED
macros as the maintained sources. `-D` supports `LED_PIN`, `LED_DDR_IO`,
`LED_PORT_IO` and `LED_BLINK_MASK`; `--output-dir` keeps custom builds separate.
Outputs contain the body, firmware manifest and fresh-device ISP HEX.
No build command programs a physical device.

For each build, `tests/usb_engine_audit.py` checks the 508-byte engine against
the deployed 516-byte engine, allowing only the four substitutions above.
It checks branch flags and logical targets, skip behavior, Z initialization
on every path to the token store and R17 liveness after each removed LDI.
ATtiny88 bit-I/O and instruction timing follow the
[Microchip datasheet, register and instruction summaries](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf).
The 16-byte CRC byte/bit recurrence must match the deployed recurrence after
the audited register allocation. The complete preparation/copy/CRC/publication
block is separately pinned by SHA-256. CP R1,R23 supplies carry-in before
each byte; eight additions of 32 return the packed byte count unchanged.
YH is the polynomial low byte, protected by compile-time assertions. Page
reservation and reported application capacity derive from the resulting
size. Changes to code paths are recorded as focused commits and must pass
model checks before considering physical installation.

## Validation, October 25, 2026

`test_optimized.mjs` executes the actual candidate opcodes with the read-only
MicroMusic ATtiny88 CPU and an explicit local NVM shim. Each of seven profiles
(three board modes, two custom ports/masks and two single-bit PD0 profiles) passes:

- 3072 standard-request comparisons against the deployed image, including
  directions and short/long lengths; descriptor transfers spanning packets
  and independent USB CRC-16 checks.
- 1024 receive-length/token combinations, rejecting stale EEPROM-write
  SETUP data unless both the token and complete packet length are valid.
- Actual Flash page-buffer fill, all application-page writes/readback/erase,
  forced RESET-vector protection and invalid page-write rejection.
- Pattern write/read/erase through every EEPROM address, invalid addresses,
  high-index rejection, busy status and rejection during partial Flash fill.
- Entry through the reset trampoline with nonzero registers/SRAM, explicit
  stack initialization, the final disconnect-delay iteration with four
  register patterns, 1024 LED ticks, GPIO isolation and application exit.

The existing packet test also passes its 18 complete SETUP-to-TX cases and
five reset-flag/watchdog cases for all seven profiles.

`test_optimized_usb.py` repeats the machine-code audit for all seven profiles
and verifies rejection of mutations to the PCIFR bit, token displacement,
branch condition flag and branch target, plus two CRC/carry mutations. The shared `test_led_config.py` and
`test_led_config.mjs` cover 21 profiles, including every single-bit mask in
both polarities, twelve/eight-byte tick selection, all 256 counter values
under four GPIO patterns and 11 rejected configurations. Pinned deployed
artifacts remain unchanged.

`test_optimized_timing.py` compares each board mode with the deployed strict
body: 600 TX waveforms with identical PORTD/DDRD levels and cycle timestamps,
500 RX synchronization contexts, 15 PID/handshake cases, complete idle/reset
poll intervals and all 15 phases of poll-to-handler arrival. Build-time
comparison independently enforces the exact USB rewrite whitelist and
audited CRC recurrence/preparation block.

`test_optimized_crc.mjs` executes 9196 independent Flash/SRAM vectors per
profile: empty/short/full replies, all constant byte values, random data,
remaining lengths through 254, packed counter/carry, pointer advancement,
packet lengths and preparation-cycle comparison with the deployed body.
`test_flash_read_bounds.mjs` exhausts 524288 address/length pairs per board
mode, plus invalid lengths/index fields and unchanged accepted pointers.

`test_optimized_erase.py` runs each board mode with simavr's independent CPU
and native SPM, using the existing ATmega88 substrate restricted to tiny88
RAM and 64-byte NORWW pages. All 108 no-LED or 107 LED application-reservation pages
erase correctly, every SPM preserves SREG, loader bytes remain intact and
invalid page writes are rejected. This check uses no Flash-controller shim.

From the updater directory:

```sh
node test_optimized.mjs build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
node test_optimized_crc.mjs build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
node test_flash_read_bounds.mjs build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
python3 test_optimized_usb.py build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
python3 test_optimized_timing.py build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
python3 test_optimized_erase.py /path/to/simavr-source build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
python3 test_led_config.py
node test_led_config.mjs

python3 build.py --firmware-manifest build/optimized-on/firmware.json --output-dir build/updater-optimized-on
node test_micromusic.mjs build/updater-optimized-on
python3 test_simavr.py /path/to/simavr-source --build-dir build/updater-optimized-on
```

USB updater applications for all three board modes also pass byte-exact
installation and fuse/CRC/readback failure checks in MicroMusic and simavr.
MicroMusic additionally checks five interrupted-operation restarts derived
from the selected image's page count. The no-LED updater ends at `0x07D0`
and embeds 1280 bytes; LED updaters end at `0x0816` and embed 1344 bytes.
The existing updater's first-page power-failure limitation still applies.

Body SHA-256 values:

```text
be2035139b301739837b5a214773e0a0421404450b078d40e2bf0c02aafa77c4  optimized-off/bootloader.bin
f7ede77c38f1debb822b5637ed7664bb9a9a60a888a9ee893c6d875e07544a9f  optimized-on/bootloader.bin
55d60847192b31055cd35b6845e4beb71dce62e16273ed871835bedf76ad17f9  optimized-active-low/bootloader.bin
```

The 1274-byte no-LED build was subsequently installed over USB and passed
physical Flash/EEPROM cycles, watchdog and cold-power startup, and original
application/EEPROM preservation. See [the hardware record](HARDWARE_TEST.md).
LED builds have software/model validation. The default verified builder and
released updater stay pinned to the earlier 1344-byte image;
`build_optimized.py` explicitly selects this implementation.
