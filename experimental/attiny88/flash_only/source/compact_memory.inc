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
    cpi r25, CMD_WRITE2
    brsh bootloader_check_write4
#endif
    ldd r4, Y+CTX_SETUP_INDEX_LOW
    ldd r5, Y+CTX_SETUP_INDEX_HIGH
    ldi r24, SPM_BUFFER_CLEAR
    out _SFR_IO_ADDR(SPMCSR), r24
    spm
    /* SELECT/ERASE map requests 1/2 to deferred markers 2/3. R25 is
     * request-handler scratch; RUN/COMMIT share the MOV and empty tail. */
    inc r25
bootloader_queue_command:
    mov r3, r25
usb_reply_empty:
    std Y+CTX_MSG_LENGTH, r1
    rjmp usb_rx_release_buffer
bootloader_check_write4:
    cpi r25, 6
    brsh usb_reply_empty
    cpi r25, CMD_EXIT
    brsh bootloader_queue_command
    rcall usb_service_pending
    ldd r0, Y+CTX_SETUP_VALUE_LOW
    ldd r1, Y+CTX_SETUP_VALUE_HIGH
    ldd r30, Y+CTX_SETUP_INDEX_LOW
    ldd r31, Y+CTX_SETUP_INDEX_HIGH
    out _SFR_IO_ADDR(SPMCSR), r29
    spm
    eor r1, r1
    rjmp usb_reply_empty
