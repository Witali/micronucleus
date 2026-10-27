/* Asynchronous EEPROM worker. WRITE4 queues R10..R13 and R2=4.
 * Each service call starts at most one byte and never waits on EEPE. The
 * shared cursor advances only after starting that byte; READ8/SELECT are
 * rejected until queue and hardware busy state have both cleared.
 */
ee_write:
/* Shared WRITE4 dispatch has staged four bytes in R10..R13. R4 is the
 * physical EEPROM byte address; R9 remains the persistent USB DATA PID. */
    mov r18, r4
    cpi r18, EEPROM_BYTES - EEPROM_WRITE_BLOCK_BYTES + 1
    brsh ee_bad_addr
/* Ready WRITE4 has R2=0 and request R25=3. The accepted CPI bound leaves
 * C=1, so ADC forms four without a separate immediate-load register. */
    adc r2, r25
    rjmp usb_reply_empty

/* Reuses the AVR register file as a four-byte queue (address 0x0A..0x0D).
 * Never spin on EEPE: advance one byte between USB poll windows. */
ee_write_step:
/* An empty queue skips the EEPE test and services USB. A ready EEPROM skips
 * that jump and starts one byte; a busy EEPROM services USB without writing. */
    cpse r2, r1
    sbic _SFR_IO_ADDR(EECR), EEPE
    rjmp usb_service_pending
    out _SFR_IO_ADDR(EEARL), r4
    out _SFR_IO_ADDR(EEDR), r10
    mov r10, r11
    mov r11, r12
    mov r12, r13
/* Only the bootloader touches EECR and keeps EEPM=00, EERIE=0;
 * the timed pair of SBIs performs erase/write without extra OUT EECR=0. */
    sbi _SFR_IO_ADDR(EECR), EEMPE
    sbi _SFR_IO_ADDR(EECR), EEPE
    inc r4
    dec r2
ee_write_step_done:
/* The main module places usb_service_pending immediately after this include.
 * Fall through without adding a return frame; its SETUP abort pops one frame. */
