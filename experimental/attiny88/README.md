# Add ATtiny88 Flash read and EEPROM commands

Add up to eight-byte Flash reads, 64-byte EEPROM read/write/readiness commands, and a PyUSB host utility. Flash writes delegate to the original Micronucleus CLI. The extension is a USB vendor protocol, not raw SPI ISP.

Imported from `Micronucleus_Tiny88_EEPROM_Flash_Read_2026-10-25.zip` (October 25, 2026). This is an English summary of the historical stage; the unmodified original reports and all intermediate files are preserved in `docs/attiny88-history/original-handoff.zip`.

Recorded bootloader body: **1402 bytes**; boot address: **0x1A80**. All images are experimental. Software tests do not establish electrical USB compatibility. No hardware flashing is part of this import.
