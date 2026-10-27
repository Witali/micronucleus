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
