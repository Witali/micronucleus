# Corrected composed USB receiver

This no-LED experiment combines the compact NRZI/SYNC sampler, strict packet
and token validation, repaired final-byte/EOP reception, and the shared active
EP0/Flash/reset implementation. It adds no decode or CRC lookup tables.

The body is **1766 bytes at 0x1900**, SHA256
`9459888f75d3c98fb636cabb910ae401f69f858bc68dfc4d1eb1eb02a89a2f4e`.
The 1792-byte region contains 28 Flash pages and twenty-six spare bytes. The existing
four-byte application postscript lies at 0x18FC..0x18FF, leaving 6396 application
bytes linked at zero. The 1280-byte objective remains 486 bytes away.

This is an unqualified control checkpoint. A historical 54-group run belongs
to the preceding image; newer mandatory gates expose ordinary receive errors.
The [November 3 record](../../docs/USB_SIZE_2026_11_03.md) gives current size
and exact-image verification scope. A strict near-endpoint crossover witness
still exposes ordinary receive rejection.
The [receive/EOP work record](../../docs/USB_RX_EOP_2026_11_09.md) gives the
new shared rejection path's emitted-graph proof and selected checks.
The [current audit](../../docs/USB_AUDIT_2026_11_01.md) records the reproducible
210 ns case and ongoing repair. Centered crossover tests alone are insufficient.

The image advertises noncanonical identity 0xFFFF. The host rejects that profile;
this directory does not create a release identity or hardware installation path.

```sh
python3 build.py --where variants/combined_rx --boot 0x1900 --require-fit
python3 verify_receiver.py --exhaustive
```

Run these commands from the Flash-only directory. The verifier executes the
maintained protocol oracles against one linked image and fails if any group
fails. It rejects execution outside physical 8 KiB Flash. Results are written
to `build/variants/combined_rx/receiver-verification.json`. `sh verify.sh` adds
independent legacy, host, EEPROM, packaging and execution-geometry checks.

The receive repairs preserve final-byte fractional timing, resume verified
mandatory transitions after short crossover zeros, and qualify short EOP with
additional observations. Maximum-size packets defer their final numeric CRC
store until EOP is qualified. A shifted mask rejects seven final unstuffed ones;
its bounded 10/10/12-clock loop must not be replaced by an unqualified constant
period. Final publication shares a five-clock tail without changing parser entry
or GPIO/sample timing. Main functions and sensitive schedules are commented in
[vusb_phy.inc](vusb_phy.inc).

Only incoming numeric DATA CRC16 validation and storage remain waived. Both CRC
symbol positions, PID/payload/count, mandatory stuffing, legal dribble, token
CRC5/address/endpoint, retry/ACK ownership and response deadlines remain checked.
No public command byte or application layout contract changes. Permanent EEPROM
commands and LED are absent from this target.

The [November audit](../../docs/USB_AUDIT_2026_11_01.md) records exact test
provenance, independent MicroMusic execution and rejected smaller controls.
The [Pass40 record](../../docs/PASS40_IMPORT.md) preserves imported optimizations
and intermediate size checkpoints. Older 1494/1518-byte bodies had known receive
failures; their sizes and results do not qualify this corrected image.
The [October audit](../../docs/USB_AUDIT_2026_10_30.md) and
[historical comparison](../../docs/HISTORICAL_USB_RX.md) retain those findings.

Digital AVR/GPIO execution is not a physical electrical USB test. This image has
not been installed on the board.
