# ATtiny88 Flash-only USB loader

This separate experimental target imports Pass35 from the EEPROM handoff archive.
The EEPROM-capable [compact v3.0](../compact/README.md) remains available unchanged.
No image in this directory has been installed or physically USB-tested.

Vendor protocol v4.1 uses absolute-address WRITE2/READ8 and explicit page commit.
It is incompatible with the v3.0 client. Imported profiles are 0x0450..0x0452 at
0x1BC0; unknown identities must be rejected before memory commands. Applications
stay linked at zero, with RESET-only patching and a four-byte postscript under
the [application contract](../compact/docs/APPLICATION_LAYOUT.md).

The import baseline is 1034 bytes without LED, 1054 active-high and 1052 active-low.
At 0x1C00 the baseline without LED is 1030 bytes, six over 1 KiB. The rejected
1024-byte archive prototype can start Flash SPM before status ACK completes;
its smaller size is not an admission criterion. Active work fixes USB defects
before treating an optimized image as usable.

## Build and software verification

```sh
python3 build.py --boot 0x1BC0 --all-led --require-fit
sh verify.sh
python3 host/flash_only_programmer35.py --help
```

The builder links AVR relocations before opcode tests or BIN export. Generated
output stays in ignored build/ and firmware35/. References 33/34/35 are frozen
audit inputs; unsafe ISP images and nested ZIPs were not imported. Original
archive/source hashes are in ARCHIVE_PROVENANCE.json.

## Scope and open findings

The sole accepted USB exception is received DATA CRC16 validation before ACK.
Outgoing CRC16, token CRC5/endpoint/length admission, retry/ACK ownership,
SET_ADDRESS, reset cancellation and Flash guards require independent checks.
The archive does not close those protocol findings; its tests are a baseline.
Digital models at exactly 16 MHz do not establish electrical USB compliance.

EEPROM is absent from this permanent loader. eeprom_stage/ is an offline planner
for a temporary application and subsequent main-image restoration. USB
re-enumeration alone is insufficient proof of EEPROM success; no automatic
hardware installation is part of this import.
