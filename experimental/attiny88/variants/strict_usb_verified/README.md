# Packet-corrected strict USB candidate

The original 1328-byte strict source remains in `../strict_usb_1328/` as a historical artifact. The first reversible hardware trial found that vendor-IN extension requests did not reach the added command dispatcher. Review also found that SRAM response buffers were passed to an unconditional LPM sender.

This **1344-byte** candidate fixes both defects: route extension requests from the real vendor dispatch and use an explicitly initialized r2 flag to select SRAM LD versus Flash LPM in the response copier. The 44-byte CRC routine and 516-byte low-level USB handler remain byte-identical to the original strict variant. Application capacity is still 6844 bytes at boot address `0x1AC0`.

`../../updater/build_verified.py` reproduces this source/image from the historical source, preserving the original. `../../updater/test_usb_packets.mjs` starts from a complete SETUP packet and checks actual copied TX payloads, covering the gap in the earlier handler-only tests.

Body SHA-256: `850cecac7cd4e106443942982e9f1c409d70abffbaad6f718fc7450903dfeb18`.

Hardware validation is recorded separately. The ISP HEX here is a fresh-device image; use the separately built application updater for USB replacement.
