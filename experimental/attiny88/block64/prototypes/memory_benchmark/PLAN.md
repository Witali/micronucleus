# Physical memory benchmark plan

Completed on 2026-10-26; see [measurements and restoration](COMPARISON.md).
The steps below retain the reproducible scope and sequencing requirements.

Compare the installed 1274-byte Micronucleus+ 2.8 with the validated V2
receiver and Block64 workers running as a temporary application. The
installed loader is preserved. Application and EEPROM backups remain
private and must be restored and compared exactly after the experiment.

1. Build the separate benchmark application. Permit Flash mutations only
   on eight aligned pages at 0x1800..0x19FF and EEPROM addresses 0..63.
   Deny RUN and all other Flash mutations, including page zero, executable
   code, CRC tables, the old loader and its application postscript.
2. Test compiled range validation and final NVM-trigger address checks.
   Preserve the frozen V2 bit sampler and original NVM sequencing.
3. On RESET, verify the legacy loader, current application, EEPROM, and
   erased scratch pages against the existing private backup.
4. Measure repeated reads of the common 6908-byte Flash range and all
   64 EEPROM bytes. Include native transfer sizes and an equal-size
   control; keep readback verification outside timed intervals.
5. Write each initially erased legacy scratch page once. Do not assume
   repeated un-erased Flash programming is supported. Benchmark bytewise
   EEPROM programming and writing FF, then restore original EEPROM.
6. Load the protected benchmark app through the existing loader. The
   necessary legacy full-application erase can be timed as a host-paced
   upload phase; it is not the same operation as erasing eight pages.
7. Benchmark new scratch-page erase/write and EEPROM blocks, with bounded
   repetition and readback. Record request counts, mandatory host pauses,
   wall time, payload bytes, median/range and throughput.
8. Restore the original application via the old loader, compare two Flash
   and EEPROM copies with the private baseline, and start the application.
9. Save only source, tests and non-sensitive measurements in Git; commit
   completed changes separately and inspect all outgoing content before push.

The [ATtiny48/88 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf)
permits application-region SPM when SELFPRGEN is programmed; software bounds
provide the protection here. Page erase/write stalls the CPU for the
documented 3.7..4.5 ms. The new firmware also waits about 5 ms after its own
status ACK before SPM. Keep the current 18 ms host pause for the initial
benchmark; legacy advertises 7 ms per page. Report those policies separately.
EEPROM completion uses EEPE/status, not a fixed whole-block delay. Writing
FF is an atomic erase/write operation, not an EEPM erase-only benchmark.
