# ATtiny88 development timeline

This English timeline summarizes the supplied October 25, 2026 handoff. The original handoff contains a reconstructed conversation history and ten development archives, not an exported Git repository or a verbatim chat transcript. All source snapshots were based on upstream commit `4dd1b49f39cd9d6fc736a720777ed62f4564e0e2`, which is retained in this fork's full history.

| Stage | Body bytes | Boot address | Application bytes | Main change |
| --- | ---: | --- | ---: | --- |
| Upstream reference / optimization kit | 1350 | `0x1A40` | 6716 | Pinned HEX/BIN, audit tooling, optional LED and MCUSR patches |
| Initial assembly rewrite | 1254 | `0x1B00` | 6908 | Readable assembly reconstruction and size reduction |
| Instruction audit | 1256 | `0x1B00` | 6908 | Align Z to the page before SPM Page Write |
| Assembly Pass2 | 1230 | `0x1B00` | 6908 | Compact I/O, control flow, and shared reply-pointer setup |
| V-USB Pass3 | 1216 | `0x1B40` | 6972 | Indexed SRAM and cycle-matched USB substitutions |
| Flash/EEPROM extension | 1402 | `0x1A80` | 6780 | Eight-byte Flash reads, EEPROM access, Python host |
| Fast Pass4 | 1356 | `0x1A80` | 6780 | Reduce extension size without slowing Flash reads |
| Compact Pass4 alternative | 1344 | `0x1AC0` | 6844 | One-byte Flash reads to save another page |
| Selected Fast Pass5 | 1344 | `0x1AC0` | 6844 | Eight-byte reads restored within 21 pages |
| Rejected CRC Pass6 alternative | 1554 | `0x19C0` | 6588 | Memory-range CRC reusing the USB routine |
| Selected Fast Pass7 | 1320 | `0x1AC0` | 6844 | Watchdog, comparisons, dispatch, PCIFR and SRAM optimizations |
| Strict USB Pass7 alternative | 1328 | `0x1AC0` | 6844 | Preserve the original USB handler bytes |

Code savings only increase application capacity when they free complete 64-byte Flash pages. Pass7 saves 24 body bytes relative to Pass5 but does not free another application page. Reaching 1280 code bytes would be the next page boundary; no such version is included.

## Decisions preserved

- Keep fast Flash reads and EEPROM support in the selected development line.
- Preserve standard USB packet CRC. Exclude the separate memory-range CRC experiment because of size and potentially excessive USB response latency (reported approximately 48 microseconds per eight bytes or 93 microseconds per sixteen bytes).
- Calculate verification checks on the host after memory readback.
- Treat cycle counts, flags, registers, W1C semantics, page alignment, and Flash/EEPROM bounds as essential parts of an optimization audit.
- Prefer the strict USB variant for initial hardware trials. Software models alone cannot establish physical USB reliability.
- Preserve the self-updater design as a separate future task. No ATtiny88 updater implementation was supplied.

## Import structure

Historical source changes were replayed in order in `experimental/attiny88`, with compact and CRC alternatives retained under `variants/`. Stage summaries were translated into English. The complete original handoff, including original-language reports, intermediate binaries, and caches, is preserved unchanged as `original-handoff.zip`; generated object files and Python caches were not expanded into tracked source directories.

The subsequent integration changes are separate commits: resolve AVR relocations before extracting bytes, provide a strict-variant builder, and verify the entire archival chain. They do not change the imported assembly instructions or the archived firmware bytes.

See [import-map.csv](import-map.csv) for archive hashes, [SELF_UPDATER_PLAN.md](SELF_UPDATER_PLAN.md) for the proposed next step, and [VALIDATION.md](VALIDATION.md) for checks actually rerun during this import.
