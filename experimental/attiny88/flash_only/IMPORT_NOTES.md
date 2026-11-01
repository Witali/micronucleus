# Pass35 import checkpoint

The user selected a separate Flash-only target in the existing Git branch;
the EEPROM-capable compact v3.0 source and installed loader remain unchanged.
The archive is technical evidence, not authorization to flash a device or
remove the existing EEPROM-capable target.

All 192 archive manifest entries were verified before extraction. The selected
Pass35 source is frozen in reference_pass35/, with the original release metadata.
References 33/34 support historical comparisons and reproducible failure cases.
Nested ZIPs, unused older targets and unsafe flashable images were omitted.
The original source/archive hashes are in ARCHIVE_PROVENANCE.json.

## Reproduced baseline

| Profile | Placement | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| NONE | 0x1BC0 | 1034 | 24324fae8bf852fe116a7556979d17aee5e265575e72bc4bf445ce81b7874b63 |
| ACTIVE_HIGH | 0x1BC0 | 1054 | c88fbe74c71335275fb8b089db9abcbfbe17f2305374e75b2ef951721e565686 |
| ACTIVE_LOW | 0x1BC0 | 1052 | c3ea96dbf8757e7477cce83d54c84e42c2603ef071ab10225f57d9d5a7ba2e44 |

Explicit avr-ld linking resolves the local AVR branch relocations retained by
LLVM18. The resulting bodies match all three archived images byte for byte.
This repairs build portability without changing firmware instructions.

Baseline checks pass for 5019 NVM/boot-guard cases, 393 ACK/retry/reset cases,
the archived standard-handler/NRZI audit, six host mock groups, 408 durable-TX
dispatch cases and 141 ACK/SPM waveforms. The archived EEPROM stage builder
also needs explicit linking; the initial complete verify run stops there.

These tests characterize the import. They do not prove complete USB behavior.
Independent audit has reproduced malformed token admission, incomplete ACK
framing, stale deferred work after reset/replacement SETUP, and an automatic
application handoff that bypasses pending-TX protection. Corrections and new
semantic/waveform tests are separate changes after this checkpoint.

The only inherited USB exception authorized by the user is omission of received
DATA CRC16 validation before ACK. Token CRC5, endpoint/length/framing admission,
standard request errors, reset cancellation and electrical timing remain
separate requirements. Normative reference: the USB-IF
[USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification);
the existing compact USB_TIMING.md records the exact local PDF hash.
