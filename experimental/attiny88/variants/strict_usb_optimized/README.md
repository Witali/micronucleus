# Strict USB size-optimization candidate

This separate development variant starts from the named/constant-based source
and restores the hardware-verified strict USB engine and packet/reset fixes.
Its initial no-LED build reproduces the deployed 1344-byte image exactly:
`ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc`.
The pinned deployed image and historical variants remain unchanged.

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
