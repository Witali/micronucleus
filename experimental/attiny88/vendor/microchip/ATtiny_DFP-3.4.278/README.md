# Official Microchip ATtiny88 device headers

Source: [Microchip ATtiny_DFP 3.4.278](https://packs.download.microchip.com/Microchip.ATtiny_DFP.3.4.278.atpack),
published in the [official Microchip Packs Repository](https://packs.download.microchip.com/).
Downloaded on October 25, 2026. The package includes ATtiny88 support.

| File | Origin |
| --- | --- |
| `tn88def.inc` | Unmodified `avrasm/inc/tn88def.inc` from the official package |
| `LICENSE.txt` | Unmodified package license notice |
| `LICENSE-APACHE-2.0.txt` | Full license from `https://www.apache.org/licenses/LICENSE-2.0.txt` |
| `include/avr/iotn88.h` | Unmodified `include/avr/iotn88.h` with its own copyright/license notice |

Checksums:

```text
41f09d5825abaa764c9000f4488f8ba3fab152afe6229b359de4a5efe9a21eda  Microchip.ATtiny_DFP.3.4.278.atpack
4c516f34d159f97fb1a253c91dec01d456d05cc4fa80f13c15728a08366bff7d  tn88def.inc
63c792cc9961aca81bfb3602e0d1d3cf01a37f35a449a6b6e2e6c8b41cc1e892  include/avr/iotn88.h
3bf0a101f2b2e44eda3b477f866bd24204c35fa1f841c865933028adf155336a  LICENSE.txt
```

The `.S` file is assembled with C preprocessing and includes `<avr/io.h>`.
`build.py` adds this directory's `include/` before the toolchain include paths,
so AVR-libc's standard device selection loads the pinned Microchip `iotn88.h`.
The generic I/O and CPU macros come from the installed AVR-libc. No device
definitions are converted or recreated by hand. The original `tn88def.inc`
is retained as the official AVRASM reference; the current LLVM/GNU build uses
the C header directly.

Use `_SFR_IO_ADDR(DDRD)` and similar expressions for IN/OUT/SBI/CBI and
`_SFR_MEM_ADDR(WDTCSR)` for LDS/STS. AVR-libc supplies these assembler-safe
address conversions. In the C header `SPM_PAGESIZE`, `FLASHEND`, `RAMSTART`,
`RAMEND` and `E2END` use bytes. In the separate AVRASM reference `PAGESIZE` and
`FLASHEND` use words. The project derives page size from `SPM_PAGESIZE`.

From `experimental/attiny88`, check the original files offline:

```sh
python3 tools/import_microchip_device.py --check

# Optional re-import from the pinned downloaded archive:
python3 tools/import_microchip_device.py --pack /path/to/Microchip.ATtiny_DFP.3.4.278.atpack
```

The importer checks each original file's SHA-256 and validates the complete
archive before re-importing. Downloads retain their original line endings
through `.gitattributes`. The C header retains its embedded redistribution
notice, conditions and disclaimer. The package notice and full Apache 2.0
license are also retained here for the package/reference files.
