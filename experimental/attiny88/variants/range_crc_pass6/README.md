# Preserve the rejected memory-range CRC experiment

Historical experiment only; excluded from the selected fast bootloader. It reuses USB CRC code for Flash/EEPROM ranges, increasing size and introducing potentially excessive USB response latency. The selected design reads memory and computes verification checks on the host.

Imported from `Micronucleus_Tiny88_CRC_Shared_Pass6_2026-10-25.zip` (October 25, 2026). This is an English summary of the historical stage; the unmodified original reports and all intermediate files are preserved in `docs/attiny88-history/original-handoff.zip`.

Recorded bootloader body: **1554 bytes**; boot address: **0x19C0**. All images are experimental. Software tests do not establish electrical USB compatibility. No hardware flashing is part of this import.
