/* Vendor SELECT / SELECT+ERASE / WRITE4 / RUN handlers.
 * Y is the USB context, R25 is the request, R4:R5 is the shared byte cursor.
 * Flash buffer loading is immediate; erase/commit/RUN are deferred in R3.
 * Entry requires the vendor dispatcher to have checked queue/hardware idle.
 * Busy behavior belongs to that public dispatch path, before READ8 or writes.
 */
bootloader_check_set_flash_address:
    rcall usb_service_pending
#ifdef COMPACT_REHEARSAL_READ_ONLY
/* Application-only hardware trial: SELECT and READ8 are the sole private
 * operations. Never queue erase/write/RUN or start an EEPROM write. */
    cpi r25, CMD_SET_MEMORY_ADDRESS
    breq .Lrehearsal_select
    rjmp usb_reply_empty
.Lrehearsal_select:
#else
/* Reject opcode zero; only SELECT and SELECT+ERASE enter the decoder. */
    tst r25
    breq usb_reply_empty
/* Opcodes 1 (select) and 2 (select + erase) share the address decoder;
 * the queued erase runs only after the main USB polling interval. */
    cpi r25, CMD_WRITE4
    brsh bootloader_check_write4
#endif
/* Protocol v3.0 puts the exact byte cursor in wIndex; bit15 selects EEPROM.
 * The host checks ranges and four-byte/page alignment before SELECT. Malformed
 * EEPROM selectors may alias the physical 64-byte EEPROM; WRITE4 retains its
 * separate low-byte bounds guard, and actual Flash SPM is guarded on the MCU.
 * Both memories clear the inactive Flash page buffer below. The host must not
 * interrupt an incomplete Flash page with an EEPROM operation. Even a malformed
 * EEPROM SELECT+ERASE cannot erase Flash: its cursor high bit makes the final
 * SPM boundary guard reject the queued erase before any page-changing SPM. */
    ldd r4, Y+CTX_SETUP_INDEX_LOW
    ldd r5, Y+CTX_SETUP_INDEX_HIGH
/* R25 remains the request: SELECT1 leaves idle command2; SELECT+ERASE2
 * becomes the actual erase opcode3. No request/address temporary is needed. */
    mov r3, r25
    inc r3
    ldi r24, SPM_BUFFER_CLEAR
    out _SFR_IO_ADDR(SPMCSR), r24
    spm
usb_reply_empty:
/* Publish zero directly; the moved nonempty reply tail must not add latency
 * to the standard/NVM reject paths before cooperative USB service resumes. */
    std Y+CTX_MSG_LENGTH, r1
    rjmp usb_rx_release_buffer
bootloader_check_write4:
/* The selector dispatched only opcodes >= WRITE4. Accept RUN explicitly;
 * unknown requests must never become a raw pending SPM operation. */
    cpi r25, CMD_EXIT
    breq bootloader_queue_command
    brsh usb_reply_empty
/* The busy gate proved the queue inactive. Load SETUP once: Flash consumes
 * two words immediately, while EEPROM keeps these same registers for its
 * asynchronous worker. An invalid EEPROM address may change inactive data
 * registers but never starts a queue, changes its cursor or touches NVM IO. */
    ldd r10, Y+CTX_SETUP_VALUE_LOW
    ldd r11, Y+CTX_SETUP_VALUE_HIGH
    ldd r12, Y+CTX_SETUP_INDEX_LOW
    ldd r13, Y+CTX_SETUP_INDEX_HIGH
    rcall usb_service_pending
    sbrc r5, 7
    rjmp ee_write
/* Every host-selected Flash cursor is four-byte aligned. After ADIW Z,2,
 * bit1 is set after word1 and clear after word2, so it doubles as the loop
 * phase. Each word restores R1 and the persistent cursor before polling. */
.Lflash_load_two_words:
    movw r30, r4
    movw r0, r10
    movw r10, r12
    out _SFR_IO_ADDR(SPMCSR), r29
    spm
/* The word has consumed R1:R0. Publish the cursor and restore the zero
 * register before allowing another packet; the next word reloads its data. */
    eor r1, r1
    adiw r30, AVR_WORD_BYTES
    movw r4, r30
    rcall usb_service_pending
    sbrc r4, 1
    rjmp .Lflash_load_two_words
    mov r30, r4
    andi r30, FLASH_PAGE_OFFSET_MASK
    brbc SREG_Z, usb_reply_empty
    ldi r25, SPM_PAGE_WRITE
bootloader_queue_command:
    mov r3, r25
    rjmp usb_reply_empty
