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
| Off | 1344 | 1314 | 1344 | 6844 |
| Active high | 1364 | 1332 | 1344 | 6844 |
| Active low | 1362 | 1330 | 1344 | 6844 |

All three candidates start at `0x1AC0`. The enabled-LED builds previously
needed 1408 reserved bytes at `0x1A80`, leaving 6780 application bytes. They
now recover one 64-byte page for the application. The no-LED candidate saves
30 code bytes; its page reservation and application capacity stay the same.
For other ports, the shared DDRD exit optimization does not apply. Tested
custom active-high PB3 with mask `0x80` uses 1330 bytes; active-low PA3 with
mask `0x03` uses 1332 bytes. Both start at `0x1AC0`. Single-bit PD0 masks
use 1328 bytes active high or 1326 active low. A single-bit mask automatically
selects an eight-byte LED tick instead of the generic twelve-byte tick;
the default mask `0x4C` and its behavior remain unchanged.

The latest four changes reduce the previous 1326/1344/1342-byte candidates
by another 12 bytes, plus four bytes where a single-bit LED mask is selected.
All profiles retain Flash programming/readback and all EEPROM commands.
The next application-capacity threshold is a 1280-byte reservation; smaller
code within the current 1344-byte reservation does not itself free a page.

| Focused change | Code bytes saved | Preserved condition |
| --- | ---: | --- |
| Erase loop reuses SUBI/SBC's zero flag | 2 | LDI/OUT/SPM preserve SREG; the next dispatcher overwrites other arithmetic flags |
| Device-info/configuration replies share pointer/status tails | 6 | Same lengths, pointers, payloads and SRAM/Flash selection |
| EEPROM ready/busy tails share code; accepted status reuses a proven zero | 4 | Address/index/page-buffer guards and the consecutive EEMPE/EEPE sequence remain |
| Inline the sole CRC invocation | 4 | Remove RCALL/RET without changing CRC arithmetic or output |
| Startup falls directly into main | 2 | Explicit stack initialization and SRAM clearing remain |
| Port-D LED exit shares the existing DDRD release | 2 with LED | LED is off and released before application entry; other-port LEDs retain explicit release |
| Initialize the CRC pointer directly in X | 2 | Remove only the obsolete MOVW; the remaining 40 arithmetic/store bytes match the deployed routine |
| Reuse the expired disconnect counter to clear R4:R5 | 2 | The last SBIW proves R24:R25 zero; MOVW runs after USB release, preserving disconnect duration |
| Three PCIFR clears use SBI instead of LDI/OUT | 6 | Two cycles in either form; only PCIF2 is affected; removed R17 values are dead |
| Token publication uses STD Z+20 instead of STS | 2 | Two cycles in either form; control-flow analysis proves Z=0x0100 |
| Single-bit LED masks use paired skips | 4 with a single-bit mask | All eight masks and both polarities preserve GPIO levels for every counter value |

The USB engine shrinks from 516 to 508 bytes through exactly four audited
substitutions. Every other opcode/operand and logical branch target must match
the deployed engine. The five-millisecond polling interval,
SE0/reset detection, pending-edge service latency, receive sample points,
transmit NRZI/stuffing and EOP timing retain the deployed implementation.
The CRC call and pointer-copy removals shorten preparation by eight CPU cycles; this
does not change the bit engine or on-wire bit periods. Watchdog reset handling,
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
The remaining 40-byte CRC arithmetic/store core must match byte for byte;
the original MOVW prefix and RET suffix are omitted. Page
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
branch condition flag and branch target. The shared `test_led_config.py` and
`test_led_config.mjs` cover 21 profiles, including every single-bit mask in
both polarities, twelve/eight-byte tick selection, all 256 counter values
under four GPIO patterns and 11 rejected configurations. Pinned deployed
artifacts remain unchanged.

`test_optimized_timing.py` compares each board mode with the deployed strict
body: 600 TX waveforms with identical PORTD/DDRD levels and cycle timestamps,
500 RX synchronization contexts, 15 PID/handshake cases, complete idle/reset
poll intervals and all 15 phases of poll-to-handler arrival. Build-time
comparison independently enforces the exact USB rewrite whitelist and
unchanged CRC arithmetic/store bytes.

`test_optimized_erase.py` runs each board mode with simavr's independent CPU
and native SPM, using the existing ATmega88 substrate restricted to tiny88
RAM and 64-byte NORWW pages. All 107 descending application-reservation pages
erase correctly, every SPM preserves SREG, loader bytes remain intact and
invalid page writes are rejected. This check uses no Flash-controller shim.

From the updater directory:

```sh
node test_optimized.mjs build/optimized-off/firmware.json build/optimized-on/firmware.json build/optimized-active-low/firmware.json
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
MicroMusic additionally checks five interrupted-operation restarts. Each
updater ends at `0x0816` and embeds 1344 bytes, including padding where needed.
The existing updater's first-page power-failure limitation still applies.

Body SHA-256 values:

```text
51c2451b2d3162e036e09aaf448c5a529905ca035ee8f64170332c3644f6c856  optimized-off/bootloader.bin
55d2ed00465d5f034edab2652be982feb1206a3b305b3a76938aeb0f0607df0c  optimized-on/bootloader.bin
0a1ee51b469a2844f28ef5b23d5de0861e3fb0e1223c958b8924682082b8bdca  optimized-active-low/bootloader.bin
```

These are instruction/model results. No physical board was programmed or
hardware-validated during this optimization task. The default verified
builder and released updater still target the previously tested image;
`build_optimized.py` explicitly selects this new candidate.
