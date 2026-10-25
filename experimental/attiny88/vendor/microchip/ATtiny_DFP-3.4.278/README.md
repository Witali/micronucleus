# Official Microchip ATtiny88 assembler definitions

Source: [Microchip ATtiny_DFP 3.4.278](https://packs.download.microchip.com/Microchip.ATtiny_DFP.3.4.278.atpack),
published in the [official Microchip Packs Repository](https://packs.download.microchip.com/).
Downloaded on October 25, 2026. The package includes ATtiny88 support.

| File | Origin |
| --- | --- |
| `tn88def.inc` | Unmodified `avrasm/inc/tn88def.inc` from the official package |
| `LICENSE.txt` | Unmodified package license notice |
| `LICENSE-APACHE-2.0.txt` | Full license from `https://www.apache.org/licenses/LICENSE-2.0.txt` |
| `tn88def-gas.inc` | Mechanical GNU/LLVM syntax adaptation of all 585 official `.equ` definitions |

Checksums:

```text
41f09d5825abaa764c9000f4488f8ba3fab152afe6229b359de4a5efe9a21eda  Microchip.ATtiny_DFP.3.4.278.atpack
4c516f34d159f97fb1a253c91dec01d456d05cc4fa80f13c15728a08366bff7d  tn88def.inc
3bf0a101f2b2e44eda3b477f866bd24204c35fa1f841c865933028adf155336a  LICENSE.txt
```

The original uses AVRASM's `.equ NAME = value`, semicolon comments, `.device`,
IDE pragmas and `.def` register aliases. LLVM's AVR assembler uses GNU syntax.
`tools/import_microchip_device.py` converts each equate to `.equ NAME, value`
and omits the assembler/IDE setup and CPU-register aliases. It preserves every
definition name, expression and value, including compatibility aliases. No
register addresses are recreated by hand. Use `r26` through `r31` or the normal
`X`/`Y`/`Z` addressing syntax instead of AVRASM's `.def` aliases.

Low I/O registers such as `DDRD`, `EECR` and `SPMCSR` have I/O-space addresses
for IN/OUT/SBI/CBI. Registers marked MEMORY MAPPED, such as `WDTCSR`, `PCICR`
and `PCMSK2`, have data-space addresses for LDS/STS. `PAGESIZE` and `FLASHEND`
use words; `RAMEND` and `E2END` use byte addresses. These units must be kept
when deriving project constants.

From `experimental/attiny88`, reproduce the adaptation offline:

```sh
python3 tools/import_microchip_device.py
python3 tools/import_microchip_device.py --check

# Optional re-import from the pinned downloaded archive:
python3 tools/import_microchip_device.py --pack /path/to/Microchip.ATtiny_DFP.3.4.278.atpack
```

The importer checks the original's SHA-256 and requires exactly 585 unique
equates. `--check` also compares the generated include byte for byte. The raw
download has its original line endings preserved by `.gitattributes`.
The package notice and full Apache 2.0 license are retained here; the generated
adaptation identifies its Microchip source and does not replace that notice.
