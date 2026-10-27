# Pass26 import validation, October 27, 2026

The complete offline suite passed in Ubuntu/WSL with Python 3.12.3,
Clang/LLVM 18.1.3 and GNU AVR binutils 2.26.20160125. The full successful
output is retained in `VALIDATION_LLVM18.log`. No USB or ISP hardware was used.

## Builder adaptation

The supplied package used LLVM 17 and extracted an assembled object directly.
LLVM 18 emits unresolved PC-relative AVR relocations, so `check_build.py` now
assembles a `.reloc.o`, links it with `avr-ld -m avr25 -Ttext=0`, and passes the
fully linked ELF through the existing `.o` API to the opcode tests and objcopy.
The relocation rejection remains in place after linking.

The linker text region is explicitly 64 KiB for measurement and historical
comparison objects: the inherited TX test builds LED Pass22 at `0x1B00`, where
that reference extends eight bytes past the physical 8-KiB limit. This reference
is not a release image. `build_release26.py` separately asserts each expected
body size and the physical `8192 - BOOT_AT` bound before emitting release files.
All supplied assembly and include files remain byte-identical.

## Results

`sh verify.sh` passed all three profiles: no LED 1206 bytes at `0x1B40`, active
high 1220 bytes at `0x1B00`, active low 1218 bytes at `0x1B00`; PHY 492 bytes in
each. The suite passed 13824 standard-request cases, 675 actual-opcode TX/CRC
comparisons, NVM simulations in every profile, 780 combined select/erase cases,
219 cursor/busy cases, arithmetic/SYNC models and all host transport/planner
and profile scenarios. Python compileall passed.

All eleven files under `firmware/`, including manifest and checksum list, match
the supplied archive byte for byte after rebuilding. `sha256sum -c SHA256SUMS.txt`
passed all ten entries. The original archive's 62 manifest entries were checked
before import; the maintained tree has its own updated `MANIFEST_SHA256.txt`.
Host `--help` and `py_compile` passed without device access. The separate
Pass24-to-Pass25 PHY audit also passed all three profiles.

The no-LED measurement at `BOOT_AT=0x1C00` reproduced 1202 bytes, 178 bytes over
the 1024-byte target. This is a size measurement, not a fitting release.

The original bundle was verified, contains exactly one root snapshot, and its
unmodified commit is an ancestor of this branch alongside the existing master
history. The complete ZIP and historical diffs/checkpoints remain preserved.
Local checks inspected archive files, bundled tree/metadata and staged content
for credentials/private data without sending them to an external service.

These results do not close the electrical USB, early ACK/CRC, retry, EEPROM
streaming or RESET-page power-loss risks in `VERIFICATION_AND_RISKS.md`.
