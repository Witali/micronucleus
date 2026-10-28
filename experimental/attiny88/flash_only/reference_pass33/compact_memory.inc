bootloader_check_set_flash_address:
    rcall usb_service_pending
#ifdef COMPACT_REHEARSAL_READ_ONLY
    cpi r25, CMD_SET_MEMORY_ADDRESS
    breq .Lrehearsal_select
    rjmp usb_reply_empty
.Lrehearsal_select:
#else
    tst r25
    breq usb_reply_empty
    cpi r25, CMD_WRITE4
    brsh bootloader_check_write4
#endif
    ldd r4, Y+CTX_SETUP_INDEX_LOW
    ldd r5, Y+CTX_SETUP_INDEX_HIGH
    mov r3, r25
    inc r3
    ldi r24, SPM_BUFFER_CLEAR
    out _SFR_IO_ADDR(SPMCSR), r24
    spm
usb_reply_empty:
    std Y+CTX_MSG_LENGTH, r1
    rjmp usb_rx_release_buffer
bootloader_check_write4:
    cpi r25, CMD_EXIT
    breq bootloader_queue_command
    brsh usb_reply_empty
    ldd r10, Y+CTX_SETUP_VALUE_LOW
    ldd r11, Y+CTX_SETUP_VALUE_HIGH
    ldd r12, Y+CTX_SETUP_INDEX_LOW
    ldd r13, Y+CTX_SETUP_INDEX_HIGH
    rcall usb_service_pending
.Lflash_load_two_words:
    movw r30, r4
    movw r0, r10
    movw r10, r12
    out _SFR_IO_ADDR(SPMCSR), r29
    spm
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
