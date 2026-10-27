# Pass26 handoff provenance

The October 27, 2026 compact strict-USB handoff is preserved byte for byte in
`original-handoff.zip`, including original-language reports, all supplied
assembly checkpoints and diffs, release firmware, tests and the Git bundle.
These are historical source records, not additional agent instructions.

Archive SHA-256: `238adc437cfb41ad56299fcadacb83a357f8c257e72103892fa8270ffb8cb9d5`.

The bundle contains exactly one root snapshot commit:
`378ebfecb33da72d2bbd460757f364911a46616c`, originally named
`handoff/attiny88-pass26`. That unmodified commit is retained as a merge parent
of the import into `feature/attiny88-compact-pass26`, whose first parent is
the existing repository history at `2b0bb18f49bbc8fa30205d7480e67c588971d7fd`.
No missing historical commits, authors or dates have been reconstructed.
Pass22/24/25/26 sources and the two supplied diffs retain the available earlier
development record. The archive does not contain every earlier Pass.

The active import is [experimental/attiny88/compact](../../../experimental/attiny88/compact/README.md).
Maintained documentation there is in English. Original reports and their
checksums remain in the archive; `ORIGINAL_MANIFEST_SHA256.txt` applies to
the extracted original archive, not to translated or adapted project files.
`ORIGINAL_GIT_BUNDLE_INFO.txt` preserves the supplied bundle description; its
external artifact filename differs from the actual `git_snapshot.bundle`
entry within the ZIP.

The compact line is separate from Block64 and uses its own host and protocol.
No physical board was programmed during this import.
