# ATtiny88 self-updater design — not implemented

The proposed updater would let a board running a working Micronucleus bootloader replace that bootloader over USB. A temporary application would contain the updater and the replacement image. Upstream `firmware/upgrade.c` targets ATtiny85 and is a design reference, not a ready ATtiny88 implementation.

## Proposed sequence

1. Generate a special application HEX containing the updater, complete replacement image, length, and checksum. Everything must fit below the bootloader, accounting for the four-byte application postscript at `0x1ABC..0x1ABF` for the proposed `0x1AC0` layout.
2. Upload and launch it through the existing working Micronucleus bootloader. The updater must execute from application pages that it never erases while replacing the bootloader.
3. Disable V-USB and interrupts. Validate the embedded image checksum and all destination pages before erasing anything.
4. Design a temporary RESET vector that enters the updater after an unexpected reset instead of entering a partially written bootloader. Updating the first Flash page is itself a vulnerable operation and needs fault-injection testing and ISP recovery access.
5. Process each 64-byte page: align its address, prepare the page buffer, perform the required SPM erase/fill/write sequence, wait for completion, and verify with LPM. Confirm the exact device-specific sequence and status flags in the ATtiny88 datasheet.
6. Verify the entire replacement image, vectors, and destination layout by byte comparison or checksum.
7. Update and verify the final RESET vector only after the new bootloader passes verification, then restart it.
8. Define write-failure handling and ISP recovery instructions. Without a second Flash bank, independent nonvolatile storage, or hardware protection, recovery from every power-loss scenario cannot be guaranteed.

## ATtiny88 checks still required

- Confirm self-programming enablement, clock configuration, watchdog/BOD settings, supply voltage, and actual 16 MHz clock source for the specific board.
- Check that SPM can execute from the intended application addresses, and verify page restrictions and the ATtiny88-specific programming sequence.
- Verify the complete RESET-to-updater-to-new-bootloader path, including the vector modifications performed by the existing host uploader.
- Handle the old and new bootloader locations and postscripts explicitly; do not copy ATtiny85 upgrade logic unchanged.
- Test reset and power-loss fault scenarios with an external ISP recovery path.
- Implement a complete assembly updater, image/HEX generator, and tests as a separate future task.

## Status and provenance

This is a translation of the design in the October 25, 2026 handoff. That work discussed the updater but produced no ATtiny88 updater source or HEX. Importing this plan does not implement or validate self-updating, and does not authorize flashing a board.

See [the history index](README.md) for provenance and [upstream upgrade.c](../../firmware/upgrade.c) for the ATtiny85 reference. The unmodified handoff ZIP retains the original design.
