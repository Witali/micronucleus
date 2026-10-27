# Eight-button local-layer verification

Offline validation on 2026-10-27 passed with AVR-GCC 7.3.0:

- Both firmware modes fit the previous/current loader bounds.
- Actual report descriptors match the expected input/output/feature sizes;
  interrupt reports fit eight bytes including the Report ID.
- RESET/INT0 targets are valid and all compact 3.0 profiles preserve vectors.
- Native C tests cover debounce/media repeat, held keyboard keys, shared
  modifiers, duplicate keys, layer changes while keys are held, rollover,
  endpoint queues/overflow, idle timing and injected/automatic tests.
- EEPROM tests cover every interrupted-save boundary, CRC/default fallback,
  readback completion and keeping the final eight EEPROM bytes unchanged.
- Control tests cover a seven-packet configuration, no partial application,
  aborted/oversized transfers, Mute feedback and selecting a local layer.
- Seven Python tests cover all layers/button 8, modifiers, launcher usages,
  status validation, legacy mapping decode and feedback/test packets.

The single CRC-checked record fits the MCU's 64-byte EEPROM. Interrupted
writes fall back to defaults instead of applying mixed settings. This differs
from the earlier three-button, two-slot settings format.

The expanded Tkinter window was opened and visually inspected on Windows. Its
read-only compatibility path loaded the connected three-button firmware and
correctly disabled saving/testing until an upgrade.

GPIO-only build: 5506 Flash bytes, 308 static SRAM bytes. Automatic-test build:
5630 Flash bytes, 309 static SRAM bytes.

Physical checks of the expanded firmware, button wiring and layer LEDs remain
pending. The earlier three-button hardware evidence is a separate scope.
