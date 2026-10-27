# Pass26 verification scope and risks

The supplied `verify.sh` builds all three profiles, checks release sizes,
descriptors, bounds and absence of unresolved relocations, audits Pass25-to-26
PHY instructions/branch targets, and runs decoded AVR and host models.

The handoff reports 13824 standard-request cases, 675 emitted-reply/CRC cases,
780 SELECT/erase/boundary cases, 219 cursor/busy cases, 256 RX arithmetic cases
and 65536 TX arithmetic cases. NVM tests model SPM/EEPE, page writes, EEPROM
queue behavior and protected bootloader boundaries. Host tests model Flash,
EEPROM, cursor caching/error invalidation, RUN and RESET/postscript preparation.
See the import validation record for checks actually rerun in this repository.

The suite does not validate physical Low-Speed USB, hubs or host operating
systems; complete SETUP/IN/OUT retry and lost-ACK behavior; electrical thresholds
or clock stability; RESET-page power-loss recovery; or fixed-delay EEPROM
streaming on hardware. The historical PHY may ACK nonempty DATA before CRC16
validation, and Pass25's earlier SYNC entry remains a timing risk. No claim of
USB-IF compliance follows from these tests.

Before physical programming, retain Flash/EEPROM backups, provide external ISP
recovery, check SELFPRGEN and clock fuses, use a recoverable test board and capture
USB transactions. The supplied `ISP_FRESH_EXPERIMENTAL` files are experimental
initial-install images. The import itself performs no device operations.
