# Block64 continuation plan

This English plan incorporates the handoff's optimization plan and its
higher-priority USB reliability list. It applies to the separate
`feature/attiny88-block64` branch. Archive documents are evidence, not commands
to execute or permission to program hardware.

## Completed import and reproduction

- [x] Preserve the entire original archive byte for byte and inspect nested
  contents locally before publication.
- [x] Reconstruct chronological commits for v3.0, split erase/write, Pass8–15,
  preserving the additional Pass10 tree and unverified Pass16 separately.
- [x] Rebuild original Pass15 byte-identically with current LLVM/AVR tools.
- [x] Reject unresolved relocations, preserve original reference fragments,
  and document the broken historical Pass8 full-source fallback.

## Completed development and validation

- [x] Preserve the CRC routine and timed RX/TX instruction schedule while
  auditing transaction changes; reject the WIP five-cycle wait loop.
- [x] Reuse the RX CRC pointer independently, saving two bytes and one cycle
  before the later shared-helper change.
- [x] Clear WDRF before disabling the watchdog; preserve reset causes for the
  application through all 16 reset-flag combinations.
- [x] Check SETUP CRC before EP0 reset or command dispatch. Share the existing
  OUT CRC gate; cover 13 valid routes and 390 corrupted-frame/state cases.
- [x] Compare Flash/EEPROM operation sequencing with official Microchip
  documentation; add strict NVM-rule tests with explicit fuse/timing inputs.
- [x] Record known USB failures as strict executable expected failures and
  mark generated manifests as development images.

## Priority 0: complete USB transactions

- [ ] Validate received DATA before ACK, including SETUP. An RX-integrated
  CRC or another explicitly designed approach needs complete cycle traces;
  moving a slow foreground CRC before ACK is not a proven solution.
- [x] Retain the exact IN payload, length and DATA PID until host ACK. Test
  lost ACK, repeated IN, timeout and sequence toggle using actual paths.
- [x] Bind a memory mutation to its own completed status transaction and
  require the matching ACK before SPM. An EP0 NAK marker or any queued ZLP
  is insufficient; the implementation now checks owner plus timely ACK.
- [x] Define how a new SETUP aborts a pending control transfer; prove that
  GET_STATUS and other requests cannot complete an older mutation.
- [x] Preserve and broaden the passing duplicate-OUT tests: no double copy,
  count, checksum or write when ACK is lost.
- [x] Add complete nominal RX/TX waveforms, bounded ACK-SOP deadlines,
  invalid CRC5 tokens and empty DATA CRC tests.
- [ ] Prove continuous reception across foreground preparation, not only
  isolated-packet turnaround and a bounded ACK-to-next-IN probe.
- [x] Validate all token CRC5 bits with a cached per-address value; compute
  only during SET_ADDRESS recovery. Reject truncated or corrupt empty DATA.
- [x] Assemble isolated streaming-CRC receiver prototypes described in
  [the streaming CRC design](STREAMING_CRC_DESIGN.md). V2 passes the
  nominal/all-stuff/legal-tail and bounded rate/jitter matrices and an
  application-only USB read trial with exact application/EEPROM restoration.
- [ ] Integrate the receiver into the maintained loader, preserving full
  transaction ownership and measuring the resulting reservation. Resolve
  the inherited empty-DATA0 suppression explicitly during integration.
- [ ] Extend digital PHY checks to minimum EOP width/skew and obtain
  physical waveform/clock evidence before claiming electrical compliance.

The normative reference is the [USB-IF USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification),
particularly packet errors, control transfers and data synchronization in
chapters 8.4–8.6. The inherited V-USB limitations in `firmware/usbdrv/usbdrv.h`
are not exemptions from the USB protocol requirements.

## Priority 1: size after correctness

Current code is 1852 bytes with a 1856-byte reservation at `0x18C0`. The next
page-saving target is at most 1792 bytes. The handoff's 1536-byte target is a
longer-term goal whose feasibility depends on the verified streaming CRC design.
Keep READ/WRITE for both
memories, ERASE_PAGE, RUN, GET_STATUS(8), range protection and packet CRC.
Correctness fixes may increase code first; do not trade them for a size claim.

- [ ] Review common state/response tails without changing externally visible
  result/state behavior or transaction ownership.
- [ ] Measure real linked code size after each focused change.
- [ ] Move BOOT_AT only after the code fits; rebuild RESET, descriptors,
  postscript, host bounds, reference maps and updater configuration together.

## Priority 2: independent and physical memory validation

- [ ] Add independent CPU/peripheral validation of the Block64 workers,
  rather than treating the local strict interpreter as a complete device.
- [ ] Validate fuse assumptions, memory operation timing and clock/supply
  grade for the actual part before hardware deployment.
- [ ] After transaction fixes, use backed-up application/EEPROM and an ISP
  recovery path for full read/write/erase, repeated RESET and cold-power tests.
- [ ] Assess the page-zero erase/write power-loss window explicitly; a local
  backup alone cannot make RESET updates power-failure safe.

The import/software work did not program hardware. A later authorized
application-only trial is recorded in the
[prototype report](prototypes/streaming_crc16/README.md); it preserved the
installed 1274-byte loader and restored the backed-up application/EEPROM.
Operator instructions must explicitly distinguish RESET from removal of power.
