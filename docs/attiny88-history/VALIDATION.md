# Import validation — October 25, 2026

These checks were rerun during import into the fork. They are separate from the test claims preserved inside the original handoff.

Environment: Ubuntu 24.04 in WSL, Clang/LLVM 18.1.3, GNU AVR binutils 2.26, and Python 3. The selected assembly sources, host utility, and original test logic were imported unchanged. Build scripts now resolve LLVM AVR relocations with `avr-ld` before binary extraction.

| Check | Observed result |
| --- | --- |
| Complete handoff SHA-256 | Matches `32a173304db4b43a42219d2f99b0fd283f26d06c2a001c8c1a06bb05c5ada4fc` |
| Archive integrity | Outer ZIP and all ten original nested ZIPs pass CRC checks; import-map SHA-256 values match |
| Historical assembly rebuilds | All eleven bodies reproduce the archived bytes exactly |
| Selected Fast Pass7 build | 1320 bytes, `0x1AC0..0x1FE7`, expected SHA-256 |
| Strict USB build | 1328 bytes; original 44-byte CRC and 516-byte handler match exactly; archived HEX reproduced |
| Compact Pass4 and CRC Pass6 builders | 1344 and 1554 bytes respectively; firmware bytes unchanged |
| Unit tests | All 44 pass (108.265 seconds on this environment) |
| Receive synchronization | 500 scenarios match modeled cycles, SREG, and registers except the intentional Z-base change |
| USB transmit traces | 600 modeled traces match PORTD/DDRD levels and cycle timestamps, including stuffing and EOP |
| Response entry | Seven sampled paths match modeled entry cycles and SRAM effects |
| Dispatcher differential execution | All 1200 cases pass: 237 exit paths, 963 polling paths, zero reported errors |
| Repeated-code scan | 339 non-USB instructions examined; no profitable exact straight-line block of at least four instructions |
| Host CLI | `--help` succeeds without USB libraries or hardware |
| Documentation language | Expanded project documentation contains no Cyrillic text; original-language evidence remains inside the unmodified ZIP |

The original handoff's long verification run had been stopped by a time limit after unit tests. This import completed the separate timing and differential scripts in addition to the unit suite. See the commands in [the experimental README](../../experimental/attiny88/README.md).

No physical board was flashed or tested with the imported images. These are software model and reproducibility checks, not proof of electrical USB compatibility, EEPROM resilience during interrupted writes, clock tolerance, or safe self-updating. The connected board's earlier successful stock Micronucleus 2.2 query does not validate these experimental builds.

No ATtiny88 self-updater implementation was supplied or added. Its [design plan](SELF_UPDATER_PLAN.md) remains future work.
