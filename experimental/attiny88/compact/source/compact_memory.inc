/* Vendor SELECT / SELECT+ERASE / WRITE4 / RUN handlers.
 * Y is the USB context, R25 is the request, R4:R5 is the shared byte cursor.
 * Flash buffer loading is immediate; erase/commit/RUN are deferred in R3.
 * EEPROM queueing is rejected until the previous asynchronous operation ends.
 */
bootloader_check_set_flash_address:
/* Reject opcode zero; only SELECT and SELECT+ERASE enter the decoder. */
tst r25
breq usb_reply_empty
/* EEPROM's asynchronous writer must be idle before NVM mode changes. */
rcall ee_check_busy
brne usb_reply_empty
/* Opcodes 1 (select) and 2 (select + erase) share the address decoder;
 * the queued erase runs only after the main USB polling interval. */
cpi r25, CMD_WRITE4
brsh bootloader_check_write4
/* Save the request, but queue erase only after the EEPROM/Flash selector.
 * Invalid EEPROM set-address requests cannot erase a previously selected page. */
mov r18, r25
/* Vendor 1: select page / block. Vendor 2: select and queue page erase.
 * Both carry the new block address in wIndex; only Flash is erasable. */
ldd r24, Y+CTX_SETUP_INDEX_LOW
ldd r25, Y+CTX_SETUP_INDEX_HIGH
sbrc r25, 7
rjmp set_address_eeprom
subi r18, 0xff
mov r3, r18
/* Host validates the block index. The shared erase/commit SPM executor
 * STILL protects all pages >= BOOT_AT, including the loader itself. */
/* Host sends page-aligned Flash block for erase and page programming.
 * Retain the low block bits: direct four-byte addressing is available.
 * SPM erase/commit still internally aligns the physical page and guards BOOT_AT. */
lsl r24
rol r25
lsl r24
rol r25
movw r4, r24
ldi r24, SPM_BUFFER_CLEAR
out _SFR_IO_ADDR(SPMCSR), r24
spm
rjmp usb_reply_empty
set_address_eeprom:
/* 16 blocks of four bytes. Keep bit7 of r5 as the memory selector. */
cpi r25, ADDRESS_EEPROM_FLAG
brne usb_reply_empty
cpi r24, EEPROM_BLOCKS
brsh usb_reply_empty
lsl r24
lsl r24
mov r4, r24
mov r5, r25
usb_reply_empty:
ldi r24, 0x00
rjmp usb_reply_limit_length
bootloader_check_write4:
/* The selector dispatched only opcodes >= WRITE4. Accept RUN explicitly;
 * unknown requests must never become a raw pending SPM operation. */
cpi r25, CMD_EXIT
breq bootloader_queue_command
brsh usb_reply_empty
sbrc r5, 7
rjmp ee_write
ldd r24, Y+CTX_SETUP_VALUE_LOW
ldd r25, Y+CTX_SETUP_VALUE_HIGH
rcall flash_buffer_append_word
ldd r24, Y+CTX_SETUP_INDEX_LOW
ldd r25, Y+CTX_SETUP_INDEX_HIGH
rcall flash_buffer_append_word
andi r30, FLASH_PAGE_OFFSET_MASK
brbc SREG_Z, usb_reply_empty
ldi r25, SPM_PAGE_WRITE
bootloader_queue_command:
mov r3, r25
rjmp usb_reply_empty
