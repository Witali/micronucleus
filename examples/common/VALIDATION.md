# Example refactoring validation

Validated on 2026-10-27 against the pre-refactoring sources at `04739fb`.
Both baselines and final AVR builds used the same local AVR-GCC 7.3.0 toolchain.

## Firmware artifacts

All four HEX files are byte-for-byte identical before and after refactoring.
The pinned V-USB files also retain their original hashes and license bytes.
Firmware C sources, HID reports and EEPROM storage formats were not changed.

| Application | Flash bytes | Static SRAM bytes | HEX SHA-256 |
| --- | ---: | ---: | --- |
| Blink | 200 | 0 | `7e00c625b23fb4967b0f7fa33fdad3e80baf1c957e2e89fc5661c78e9d51ebc9` |
| Keyboard | 2488 | 85 | `ca6c8c70ff5a3530ce985dfbd27f34af69ffd74bb034492aa2ef10378f9767ca` |
| Media remote | 5506 | 308 | `7aff437db9c8100b15816b4de7487c23fc9b81d1e2f197909ae16acae71da298` |
| Media remote simulation | 5630 | 309 | `709281b37c74689bf028c8b4a84ed986735d2f7c3298bc6f8117c1780ac4ea02` |

## Checks

- All existing keyboard and remote `verify.py` checks passed, including real
  descriptors, interrupt vectors, all compact-loader placements, button/layer
  behavior, interrupted EEPROM saves and multi-packet HID control transfers.
- Two shared HEX-boundary tests passed. The Blink build retains its 1024-byte
  smoke-test bound; both HID examples retain their explicit Flash/SRAM budgets.
- All 23 desktop tests passed on Windows, including the opt-in real Tkinter
  test with a hidden window and simulated device. In the offline Linux suite,
  the same tests passed with only that opt-in Tk test skipped.
- Five session scenarios also passed against the original nested worker.
  Four transport scenarios passed against the original Windows HID class.
- The CLI argument/help output and the ASTs of the CLI workflows are unchanged.
  The extracted Core Audio function has the same AST as its original version.
- Actual Windows Core Audio reads succeeded. The board was not connected, so
  no real HID exchange, upload, physical button or LED check was performed.
- Assembly formatting check passed for all 22 maintained files; Git whitespace
  checks passed.

The separate key-label fix intentionally changes desktop behavior: valid
keyboard usages without a friendly name can be displayed and saved again.
Regression tests cover every permitted usage from `0x04` through `0x73`,
modified keys and modifier-only bindings. No persisted representation changes.

Reproduction commands are in each example's README and the shared
[README](README.md). Previous board results remain recorded in the examples'
hardware reports; they are not evidence of a new hardware run here.
