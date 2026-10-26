# ATtiny88 self-programming and EEPROM contract

The primary reference is the [Microchip ATtiny48/88 datasheet, revision 8008H](https://ww1.microchip.com/downloads/en/DeviceDoc/doc8008.pdf).
Page numbers below are the printed numbers. Register behavior is specific to
ATtiny88; an ATmega with a separate boot section is not an equivalent device.

## Clock and device grade

The operator confirms that the board uses a 16 MHz external oscillator.
This implementation and the cycle-to-time model use 16 MHz; the frequency
was not independently measured during this work. The clock source does not
establish operation within the selected device's rated limits: the standard
datasheet's speed grade is 12 MHz, while the separate [automotive ATtiny88
datasheet, section 21.4.3](https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-9157-Automotive-Microcontrollers-ATtiny88_Datasheet.pdf)
permits a 16 MHz external clock at 4.5–5.5 V. Microchip distinguishes those
ordering grades on the [ATtiny88 product page](https://www.microchip.com/en-us/product/ATtiny88).
The connected board's ordering grade and supply voltage were not verified
in this software work. USB instruction timing at 16 MHz and compliance with
a particular part's operating limits are separate claims.

## Programming sequence

| Datasheet requirement | Block64 implementation and validation |
| --- | --- |
| SPM requires programmed SELFPRGEN; there is no separate hardware boot section (§20.1, p.188) | The firmware assumes that fuse is programmed. Software bounds protect the loader; the RESET word is not hardware locked. |
| SPMCSR must be followed promptly by SPM (§19, pp.183–187) | `block_spm_command` uses adjacent OUT/SPM. The strict model checks the four-cycle command window. |
| Erase/write pauses the CPU; read-while-write is unavailable (§19.0.1/.3 and §19.2.1) | Workers run outside the USB bit engine. Software USB cannot run during the pause. The existing status-stage/host-ACK interlock remains defective. |
| Erase precedes programming; buffer words load once between clears (§19.0.1–.3) | Host issues separate ERASE_PAGE then WRITE. The worker clears the buffer and loads 32 unique words. Strict tests reject an unsupported write to a non-erased page. |
| EEPE blocks SPMCSR changes; EEPROM programming destroys staged Flash data (§19.1.1 and §19.0.2) | Active operations are serialized. EEPROM workers check readiness, and strict tests exercise the hardware exclusion and buffer lifetime. |
| EEPROM uses EEPE polling and an EEMPE-to-EEPE timed sequence (§5.3 and §5.4.3, pp.21–27) | The worker uses adjacent OUT(EEMPE)/SBI(EEPE). Interrupts remain disabled. Flash CPU stalls and serialized workers prevent simultaneous SPM. |
| WDRF must clear before WDE can clear (§8.5.2, p.50) | Startup now saves MCUSR to GPIOR0 and clears MCUSR before the watchdog timed writes; all 16 reset-flag combinations are tested. |

The host intentionally manages the final four-byte application postscript.
Flash ranges end before BOOT_AT; ordinary application capacity excludes those
four bytes. Page zero is rewritten as a whole, with RESET redirected to the
loader. Losing power during that erase/write can still destroy USB access.

## Timing and model limits

The original cycle report counts instructions only. It excludes EEPROM
peripheral pauses and programming time. For example, the recorded READ64
path is 628 instruction cycles; adding the documented four-cycle pause per
EEPROM read gives 884 CPU cycles for that path, before any USB overhead.
This is calculated behavior, not a physical timing measurement.

The strict NVM tests use declared deterministic busy-duration assumptions.
They do not establish electrical timing, voltage margins, endurance, fuse
contents of a connected device, or power-loss recovery. Unsupported repeated
programming without erase is rejected; a convenient bitwise-AND simulation
is not presented as a guaranteed result for that operation.

The functional test mode remains useful for command logic and historical
instruction-cycle comparisons. Passing those tests alone does not establish
the Flash/EEPROM hardware constraints or USB transaction correctness.
