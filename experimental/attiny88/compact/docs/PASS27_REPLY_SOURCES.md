# Pass27 descriptor-backed reply sources

Standard replies now use the existing Flash device descriptor. GET_STATUS and
GET_INTERFACE read its zero string-index bytes 14/15. GET_CONFIGURATION selects
the adjacent zero/one bytes 16/17. SET_CONFIGURATION compares the complete
16-bit wValue and accepts only 0 or 1; every malformed value preserves the
previous configuration. Startup clears that state, so all reachable values
remain valid descriptor selectors.

The persistent reply pointer in R14:R15 carries the EEPROM flag in R15 bit7.
READ8 retains that tag, while the EEPROM TX reader addresses EEARL with ZL.
The generic SRAM copy path and separate R2 memory-source state are removed.
Flash and EEPROM payload staging, CRC16, packet lengths and cursor increments
keep their existing behavior. R2 is free and tests poison it to detect accidental
dependence on the removed source encoding.

This saves eight linked bytes including strict configuration validation:
1102 bytes at `BOOT_AT=0x1C00`, or 1106/1124/1122 bytes in the fitting
off/active-high/active-low profiles. All PHY bytes remain unchanged.

Run `sh verify27.sh` from the compact directory. Its actual-opcode checks retain
all standard request combinations, descriptor wLength 0..256, repeated setters,
multi-packet payload/PID/CRC checks and complete Flash/EEPROM behavior. They also
test all 65536 configuration words from both valid prior states per profile.
Impossible injected configuration states are replaced by this reachable-state
invariant and explicit exhaustive malformed-request rejection tests.
