# Hardware smoke test — October 25, 2026

Result: **PASS** for uploading, running, and retaining a small LED application across a USB power cycle on the connected ATtiny88 board.

## Device and build

- USB bootloader: stock Micronucleus **2.2**, VID/PID `16D0:0753`.
- Reported device signature: `0x1E9311` (ATtiny88).
- Reported application capacity: **6650 bytes**.
- Application: `main.c`, nominal CPU clock 16 MHz, onboard active-high LED on PD0.
- AVR-GCC build: **200 Flash bytes**, no static SRAM allocation.
- HEX SHA-256: `7e00c625b23fb4967b0f7fa33fdad3e80baf1c957e2e89fc5661c78e9d51ebc9`.
- Build validation: Intel HEX record lengths/checksums, EOF, and application-only addresses below 1024 bytes passed. The file fits the reported application capacity.

## Observations

1. A read-only `micronucleus --info --timeout 5` query successfully identified the board before upload.
2. `micronucleus --run --timeout 30 build/blink.hex` erased the application, wrote the image, and sent the start command. The uploader returned **exit code 0**.
3. The user observed and confirmed the repeated pattern: **three short flashes, one long flash, then a pause**, over at least three cycles.
4. The user disconnected the USB cable for two seconds and reconnected it. A waiting `micronucleus --info --timeout 60` query again found bootloader **2.2**, signature `0x1E9311`, and 6650 application bytes, with **exit code 0**.
5. After the bootloader window ended, the user confirmed that the same application pattern returned. This verifies nonvolatile application storage and normal startup after a power cycle.

The bootloader was preserved; no fuse or EEPROM write commands were issued. The board was left running this LED sample.

## Scope

The stock 2.2 protocol provides no application Flash readback, so no independent byte-for-byte device-memory verification was performed. Successful upload, observed execution, and observed power-cycle persistence are recorded separately above.

This test did not install or validate the experimental Fast/Strict Micronucleus+ bootloaders, their added Flash/EEPROM protocol, or the proposed self-updater. It establishes that the existing USB upload path and an ordinary application work on the connected board.
