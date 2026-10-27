# Keyboard hardware smoke test, 2026-10-27

The user authorized uploading the original `hello` example to the connected
MH-Tiny88. The recognized installed loader was compact protocol 3.0,
revision `0x0300`, with `BOOT_AT=0x1B80`.

Before writing, two complete 8192-byte Flash reads and two 64-byte EEPROM reads
matched. The bootloader matched the independently verified permanent installation.
Private memory backups remain outside Git.

The uploaded original application HEX had SHA-256
`ca6c8c70ff5a3530ce985dfbd27f34af69ffd74bb034492aa2ef10378f9767ca`.
Every application page and the complete outgoing application region matched
readback. The bootloader region and all EEPROM bytes remained unchanged.

After the last memory access the loader automatically started the application
on its six-second idle timeout. A later explicit RUN attempt found no loader;
Windows independently reported an active HID input device and HID keyboard
for `16c0:27db`. No second upload was attempted.

The user reported that text was entered and then confirmed that the test worked.
They initially selected that different text appeared, so an exact literal
`hello` match is not established by this record. HID key positions depend on
the host's selected layout and lock state. No screenshot or editor contents
were collected after the user stopped Computer Use with Escape.

Cold restart, repeated-pattern observation, and an independent observation of
the onboard LED were not recorded in this test.
