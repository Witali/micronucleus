# Assembly source format

Use a small column-based GNU/AVR style in maintained assembly sources:

- Labels start in column one, without leading whitespace. Prefer one label on
  its own line, including numeric/local labels and labels in assembler macros.
- Instructions, assembler directives and macro invocations have four leading
  spaces. Use spaces rather than tabs; do not indent further for branch depth.
- C preprocessor directives (`#include`, `#define`, `#if`, etc.) start in column
  one. Keep continuation lines intact.
- Keep existing operand spacing and timing comments. For new code, separate the
  mnemonic from operands with spaces and put a space after each operand comma.
- Keep procedure comments next to their labels. Explain register ownership,
  side effects and timing-sensitive sections in English.
- Use LF and a final newline for new files. Formatting must not change the
  instruction order, operands, expressions, quoted data or emitted bytes.

```asm
    .global copy_byte
copy_byte:
    ld r18, Z+
    st X+, r18
    ret

#if LED_MODE != NONE
led_tick:
    LED_TICK
#endif
```

GNU `as` permits whitespace before labels; column-one labels are our readability
convention. See the primary [GNU assembler syntax documentation](https://sourceware.org/binutils/docs/as/Statements.html)
and [AVR-LibC assembler examples](https://www.nongnu.org/avr-libc/user-manual/assembler.html).
There is no assembler-wide requirement to use one specific indentation width.

`python tools/format_asm.py` formats the maintained source directories and the
three first-party firmware assembly files. `python tools/format_asm.py --check`
reports drift without modifying files. Run it with the host Python/Git of the
checkout; a Windows-created Git worktree uses Windows Python/Git.

The formatter changes only leading whitespace. It preserves comments, quoted
data, continuations, disabled `#if 0` reference blocks and operand alignment.
Update its explicit source selection
when adding a new maintained assembly directory. Assembly-emitting generators
should produce the same layout; generated build output is regenerated rather
than bulk edited.

Do not bulk-format V-USB/Microchip vendor sources, archived variants, references,
history/checkpoints or hash-pinned experimental inputs. They retain upstream or
snapshot formatting. `Makefile.inc` is a make fragment and is not assembly.

For a formatting change, compare emitted code/data and relevant symbols before
and after with the same tools/options. For the timing-sensitive USB firmware,
identical machine bytes establish that the instruction schedule did not change;
source appearance alone does not.
