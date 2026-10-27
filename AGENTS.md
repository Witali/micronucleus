# Documentation language

- Write and maintain all project documentation in English, including README files, plans, guides, and reports.
- Translate imported documentation into English when incorporating it into the project.

# Assembly formatting

- Follow [docs/ASSEMBLY_STYLE.md](docs/ASSEMBLY_STYLE.md) for maintained assembly.
- Keep labels at the left edge; indent instructions, assembler directives and
  macro invocations with four spaces. Keep C preprocessor directives at column one.
- Preserve operands, quoted data, timing comments and instruction order.
- Run `python tools/format_asm.py --check` for the maintained source selection.
- Preserve vendor and pinned reference/history formatting; `.inc` files that are
  Makefiles are not assembly. Generators should emit the same assembly layout.
- Verify emitted bytes and relevant symbols are unchanged after formatting.

# ATtiny88 compact application layout

- Follow [the application layout contract](experimental/attiny88/compact/docs/APPLICATION_LAYOUT.md).
- Applications stay linked at `0x0000`. Patch only their RESET word; preserve
  supplied interrupt-vector/application bytes from `0x0002` onward.
- Keep the four-byte postscript at `BOOT_AT-4`; do not reserve a vector page,
  relocate applications to `0x0040`, or assume unused space beside RESET.
- Derive hardware geometry from a recognized USB profile. A changed boot
  boundary/layout needs a new profile identity; reject unknown profiles before
  vendor memory commands. Offline placement must not override detected geometry.
- Treat original application images and foreign already-patched images as
  different input contracts. Do not guess a foreign image's original entry.
