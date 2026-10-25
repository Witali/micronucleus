# Packet-corrected strict USB candidate

The original 1328-byte strict source remains in `../strict_usb_1328/` as a historical artifact. The first reversible hardware trial found that vendor-IN extension requests did not reach the added command dispatcher. Review also found that SRAM response buffers were passed to an unconditional LPM sender.

This **1344-byte** candidate fixes both defects: route extension requests from the real vendor dispatch and use an explicitly initialized r2 flag to select SRAM LD versus Flash LPM in the response copier. The 44-byte CRC routine and 516-byte low-level USB handler remain byte-identical to the original strict variant. Application capacity is still 6844 bytes at boot address `0x1AC0`.

`../../updater/build_verified.py` reproduces this source/image from the historical source, preserving the original. `../../updater/test_usb_packets.mjs` starts from a complete SETUP packet and checks actual copied TX payloads, covering the gap in the earlier handler-only tests.

The first permanent installation also exposed a watchdog-reset startup defect: WDRF was still set during watchdog disable. Move the existing MCUSR-to-GPIOR0 save and MCUSR clear from application exit to startup before that timed sequence. This adds no bytes, preserves the reported reset flags for applications, and handles POR, external, brownout and watchdog reset flags in the model.

GET_CONFIGURATION also uses the shared SRAM reply helper, instead of a second pointer path that bypassed the RAM flag.

Body SHA-256: `ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc`.

Hardware validation is recorded separately. The ISP HEX here is a fresh-device image; use the separately built application updater for USB replacement.

## Optional bootloader LED

[`led_config.h`](led_config.h) controls the assembly loader at compile time.
The names `NONE`, `ACTIVE_HIGH` and `ACTIVE_LOW` follow upstream Micronucleus.
Defaults reproduce the tested no-LED image exactly; configuration overrides
do not modify the historical sources or the pinned binary/HEX above.

| Macro | Default | Meaning |
| --- | --- | --- |
| `LED_MODE` | `NONE` (0) | No LED code; `ACTIVE_HIGH` (1) drives high/low; `ACTIVE_LOW` (2) switches between low and input |
| `LED_DDR_IO` | `0x0A` | DDRD I/O address |
| `LED_PORT_IO` | `0x0B` | PORTD I/O address |
| `LED_PIN` | `0` | Bit number, PD0 on this board |
| `LED_BLINK_MASK` | `0x4C` | LED is on when `(idle_counter_low & mask) == 0` |

The mask selects the idle-counter blink pattern. It is not a delay in
milliseconds: traffic and time spent in the main loop affect the rate. The
LED initializes off, updates while the loader waits, then turns off and
releases its pin before entering the application. The application's own LED
behavior is independent.

Single-bit masks (`0x01`, `0x02`, through `0x80`) automatically use an
eight-byte LED tick, saving four bytes compared with the generic twelve-byte
tick. Both LED polarities are supported. Other masks, including the default
`0x4C`, keep their existing code and behavior. This shared macro also applies
to the separate size-optimized variant.

Build from `experimental/attiny88/updater` with the documented LLVM/AVR tools:

```sh
python3 build_verified.py --led off
python3 build_verified.py --led on
python3 build_verified.py --led active-low

# Equivalent macro interface, with a different mask:
python3 build_verified.py -D LED_MODE=ACTIVE_HIGH -D LED_BLINK_MASK=0x80 \
    --output-dir build/led-custom

# Example of an alternate port: PB3. Use I/O addresses, not SRAM addresses.
python3 build_verified.py --led on -D LED_DDR_IO=4 -D LED_PORT_IO=5 -D LED_PIN=3 \
    --output-dir build/led-pb3
```

Each output directory contains `bootloader.bin`, `firmware.json` (resolved
macros, addresses, symbols and hash), and `isp-fresh.hex` for a fresh ISP
installation. No command here flashes a board. The ISP image is not an
application to upload over USB. Without arguments the original no-LED
artifacts are reproduced and the manifest goes to `updater/build/verified`.
With `--led`, outputs go to `updater/build/led-off`, `led-on`, or
`led-active-low`; `--output-dir` selects another location.

| Mode | Code bytes | Boot address | Reserved Flash | Application bytes |
| --- | ---: | ---: | ---: | ---: |
| `NONE` | 1344 | `0x1AC0` | 1344 | 6844 |
| `ACTIVE_HIGH` | 1364 | `0x1A80` | 1408 | 6780 |
| `ACTIVE_LOW` | 1362 | `0x1A80` | 1408 | 6780 |

The builder chooses a whole-page reservation, adjusts the reported capacity
and reset/postscript addresses, and verifies that the CRC and low-level USB
engine remain byte-identical. It rejects LED use of USB PD1/PD2, clock PB6,
RESET PC6, invalid DDR/PORT pairs, nonexistent Port A bits and invalid masks.
For another pin, check its availability in the actual package and board wiring.

Software validation:

```sh
python3 test_led_config.py
node test_led_config.mjs
node test_usb_packets.mjs build/verified/firmware.json
node test_usb_packets.mjs build/led-on/firmware.json
node test_usb_packets.mjs build/led-active-low/firmware.json
node test_usb_packets.mjs build/led-custom-high/firmware.json
node test_usb_packets.mjs build/led-custom-low/firmware.json
```

The build check covers 21 profiles, including all eight single-bit masks in
both polarities, and 11 invalid configurations. The CPU
check executes initialization, all 256 counter values with four register
patterns, and exit for every profile, including GPIO isolation. Packet tests
use each manifest's actual address/capacity and check Flash/EEPROM replies,
bounds and reset flags. The LED variants have software validation only; the
earlier hardware record applies to the pinned no-LED image.
