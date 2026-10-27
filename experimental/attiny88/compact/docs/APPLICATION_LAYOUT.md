# Compact application layout contract

Decision, 2026-10-27: retain the normal application vector page and patch its
RESET on the host. Do not reserve or relocate a complete first Flash page.
This contract applies to `experimental/attiny88/compact`.

## Application image and vector ownership

An ordinary application is linked at byte address `0x0000`. Its source HEX/BIN
contains its own RESET instruction and does not need to know the loader's
address or reserved size. It must fit below the identified profile's postscript.

The host decodes the original application's RESET target from that input file.
It computes the installed loader's RESET redirect from the identified hardware
profile; it does not recover the original application entry from the already
patched RESET on the board.

During image preparation:

1. Replace bytes `0x0000..0x0001` with the RJMP to the loader.
2. Preserve every supplied application byte from `0x0002` through `BOOT_AT-5`,
   including interrupt vectors. Fill unspecified application bytes with `0xFF`.
3. Reserve `BOOT_AT-4..BOOT_AT-1` for the postscript. Its first two bytes hold
   an RJMP to the original application's entry; the final two bytes remain
   `0xFF` on the ATtiny88.
4. Preserve the original input file; these patches belong to the outgoing image.

The loader exits by jumping to the postscript, which then enters the
application. A cleared postscript prevents automatic startup of an incomplete
or absent application. No application-entry slot is placed immediately after
RESET, because that word is the INT0 vector. Nor may space after the vector
table be assumed unused: an ordinary linker may place startup code there.
The [ATtiny48/88 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf),
section 9.1/table 9-1, defines the fixed hardware vector addresses.

An application relocated to `0x0040` with forwarding vectors would require a
different link/layout contract. It is not a supported alternative in this line.
Do not move boot code or metadata into an allegedly free vector slot as a
size optimization.

## Hardware profile and geometry

The v3.0 host reads the standard USB device revision (`bcdDevice`) and looks it
up in its supported profile table. It never guesses geometry from an uploaded
image, a pre-existing RESET target, or the apparent length of a Flash dump.

| Profile | Revision | BOOT_AT | Reserved bytes | Application bytes | Postscript |
| --- | --- | --- | ---: | ---: | --- |
| No LED | `0x0300` | `0x1B80` | 1152 | 7036 | `0x1B7C` |
| LED active-high | `0x0301` | `0x1B40` | 1216 | 6972 | `0x1B3C` |
| LED active-low | `0x0302` | `0x1B40` | 1216 | 6972 | `0x1B3C` |

Reserved bytes are `8192-BOOT_AT`; application bytes are `BOOT_AT-4`. Code size
can vary within the reserved pages without changing geometry. Each supported
revision must have one unambiguous geometry and wire contract. A changed boot
boundary or image format requires a new profile identity understood by the host.
Offline size-measurement builds are not deployable profiles; do not upload a
relocated experimental image under an incompatible ordinary profile identity.

Reject unknown revisions before vendor memory commands. In hardware mode,
an offline `--boot-at` option must not override the detected profile. Reject
images whose supplied bytes reach the reserved postscript or bootloader.

## Foreign images and interrupted uploads

The supported input is an original application image. An image already patched
for another loader may contain a loader redirect instead of its original entry.
It needs an explicit, understood conversion using the old layout/metadata;
never infer the original entry from guessed empty space. Current tooling does
not reliably recognize every foreign patched image or full-device dump. Use
the original HEX/BIN when its provenance/layout is uncertain.

Program the postscript last so an incomplete upload cannot automatically start
the old application. Rewriting the RESET page still has a power-loss window
that can require ISP; this layout does not guarantee recovery from that event.

## Authoritative code and checks

- `host/compact_programmer27.py`: descriptor profiles, hardware geometry and
  protocol3.0 selection.
- `host/compact_programmer.py:pack_application`: shared input RESET decoding and
  outgoing RESET/postscript construction; no v5.5 globals are changed by v3.0.
- `source/micronucleus_t88_compact.S:app_jump`: postscript handoff.
- `tests27/host_protocol.py`: preserved vector bytes, RESET/postscript targets,
  profile rejection, memory bounds and hardware geometry overriding offline options.

Firmware optimizations must preserve this contract. The 1-KiB goal is not
satisfied by silently moving loader work into the application's vector page.
