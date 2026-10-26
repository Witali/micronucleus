# Archived USB baselines

`Pass8_usb_crc.bin` (44 bytes) and `Pass8_usb_phy.bin` (508 bytes) are extracted
without modifications from `02_CURRENT_PASS15_EXPERIMENTAL/build/reference_pass8.bin`
in the original handoff, using the symbol table in the adjacent archived
`reference_pass8.o`. Boundaries are `usb_crc16_append..USB_handler` and
`USB_handler..main`, respectively. Their hashes are pinned in the release audit.

The historical full Pass8 source refers to an undefined `L1eca` outside these
USB fragments. A current LLVM build exposes this at link time. The audit uses
the original fragments rather than pretending that the full historical source
links successfully, or altering historical instructions to make it link.
The separate previous-1344-byte source still builds and independently checks
the same CRC/PHY fragments in `test_firmware.py`.

SHA-256:

```text
e2ca1be4e1c0ee222eff4eee87df39afe91b36e68feb8b756625efcf2fd142ec  Pass8_usb_crc.bin
f9a6c9bb587fc6123a384c68f8ae897c228e1bf11fd93cc64dcb168df5b0d63a  Pass8_usb_phy.bin
```

These checks prove instruction identity within the stated fragments. They do
not prove USB transaction reliability or electrical compatibility.
