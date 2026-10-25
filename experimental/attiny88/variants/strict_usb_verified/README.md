# Packet-corrected strict USB candidate

The original 1328-byte strict source remains in `../strict_usb_1328/` as a historical artifact. The first reversible hardware trial found that vendor-IN extension requests did not reach the added command dispatcher. Review also found that SRAM response buffers were passed to an unconditional LPM sender.

This **1344-byte** candidate fixes both defects: route extension requests from the real vendor dispatch and use an explicitly initialized r2 flag to select SRAM LD versus Flash LPM in the response copier. The 44-byte CRC routine and 516-byte low-level USB handler remain byte-identical to the original strict variant. Application capacity is still 6844 bytes at boot address `0x1AC0`.

`../../updater/build_verified.py` reproduces this source/image from the historical source, preserving the original. `../../updater/test_usb_packets.mjs` starts from a complete SETUP packet and checks actual copied TX payloads, covering the gap in the earlier handler-only tests.

The first permanent installation also exposed a watchdog-reset startup defect: WDRF was still set during watchdog disable. Move the existing MCUSR-to-GPIOR0 save and MCUSR clear from application exit to startup before that timed sequence. This adds no bytes, preserves the reported reset flags for applications, and handles POR, external, brownout and watchdog reset flags in the model.

GET_CONFIGURATION also uses the shared SRAM reply helper, instead of a second pointer path that bypassed the RAM flag.

Body SHA-256: `ec49d723147b6cb4eb1fc4ee24b947d46f5dc5274c4a26168c60857ca4b416fc`.

Hardware validation is recorded separately. The ISP HEX here is a fresh-device image; use the separately built application updater for USB replacement.
