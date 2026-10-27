# ATtiny88 development history

The separate [October 27 Pass26 handoff](pass26/README.md) preserves its complete
original archive and the single original Git snapshot in the compact branch's
ancestry. [Maintained compact documentation](../../experimental/attiny88/compact/README.md)
describes protocol v5.5, software checks and remaining hardware risks.

The original upstream history is retained. Historical snapshots from the October 25, 2026 handoff are replayed as individual import commits, with English stage summaries. Commit authors and times describe this import; they do not impersonate the earlier agent or reconstruct unavailable Git metadata.

`original-handoff.zip` preserves the complete supplied handoff byte for byte, including all ten original ZIP files, original-language reports, historical generated artifacts, and validation records. These archived records are provenance, not current project instructions. Expanded project documentation is maintained in English.

Complete handoff SHA-256: `32a173304db4b43a42219d2f99b0fd283f26d06c2a001c8c1a06bb05c5ada4fc`.

See `import-map.csv` for source archive hashes and imported destinations; [SELF_UPDATER_PLAN.md](SELF_UPDATER_PLAN.md) for the preserved original design and later implementation. The initial import did not flash a board. The subsequent USB upgrade is documented in [the updater hardware record](../../experimental/attiny88/updater/HARDWARE_TEST.md).

Current documentation:

- [Development timeline](DEVELOPMENT_HISTORY.md)
- [Version matrix](VERSION_MATRIX.csv)
- [Validation performed during import](VALIDATION.md)
- [Selected firmware and build instructions](../../experimental/attiny88/README.md)

All upstream commits remain in the repository. Imported stages use ordinary new commits without rewriting history or inventing historical authors or dates. The compact and rejected range-CRC variants are preserved separately from the selected fast build.
