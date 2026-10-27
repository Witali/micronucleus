/* Asynchronous EEPROM worker. WRITE4 queues R10..R13 and R8=4.
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
ldi r18, EEPROM_WRITE_BLOCK_BYTES
mov r8, r18
rjmp usb_reply_empty

/* Reuses the AVR register file as a four-byte queue (address 0x0A..0x0D).
 * Never spin on EEPE: advance one byte between USB poll windows. */
ee_write_step:
/* Empty queue skips the EEPE test and returns. Otherwise an idle EEPE test
 * skips RET and starts one byte; a busy EEPROM returns without side effects. */
cpse r8, r1
sbic _SFR_IO_ADDR(EECR), EEPE
ret
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
dec r8
ee_write_step_done:
ret

/* R24 is scratch at all three call sites; Z=1 means EEPROM fully idle.
 * Treat any nonzero EECR bit conservatively as busy. Normally only EEPE
 * persists here; delaying on a transient EERE/EEMPE is safe and needs no mask. */
ee_check_busy:
in r24, _SFR_IO_ADDR(EECR)
or r24, r8
ret
