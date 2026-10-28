bootloader_check_set_flash_address:
    /* Vendor writes have IN status; OUT cannot release queued SPM/RUN. */
    mov r11, r1
    rcall usb_service_pending
#ifdef COMPACT_REHEARSAL_READ_ONLY
    cpi r25, CMD_SET_MEMORY_ADDRESS
    breq .Lrehearsal_select
    rjmp usb_reply_empty
.Lrehearsal_select:
#else
    tst r25
    breq usb_reply_stall
    cpi r25, CMD_WRITE4
    brsh bootloader_check_write4
#endif
    movw r4, r14
    ldi r24, SPM_BUFFER_CLEAR
    out _SFR_IO_ADDR(SPMCSR), r24
    spm
    /* SELECT/ERASE map requests 1/2 to deferred markers 2/3. R25 is
     * request-handler scratch; RUN/WRITE4 share the MOV and empty tail. */
    inc r25
bootloader_queue_command:
    mov r3, r25
usb_reply_empty:
    /* Empty and data replies share length publication and idle reset. */
    mov r24, r1
    rjmp usb_reply_store_length
bootloader_check_write4:
    cpi r25, 5
    brsh usb_reply_stall
    cpi r25, CMD_EXIT
    brsh bootloader_queue_command
    /* Load each Flash-buffer word exactly once, after status ACK. */
    ldi r25, (1 << USB_CURSOR_WRITE_PENDING_BIT)
    rjmp bootloader_queue_command
