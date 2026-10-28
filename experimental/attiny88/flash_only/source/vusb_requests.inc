bootloader_handle_vendor_request:
    cpi r25, REQ_UNIFIED_READ
    brne bootloader_check_set_flash_address
memory_read:
memory_read_advance:
    /* READ8 snapshots SELECT's cursor. OUT status later commits its advance. */
    movw r14, r4
    ldi r24, USB_EP0_PAYLOAD_BYTES
    rjmp usb_reply_limit_length
usb_reply_use_scratch_buffer:
    ldi r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 14)
usb_reply_use_flash_pointer:
    ldi r19, HIGH8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 14)
usb_reply_set_pointer:
    movw r14, r18
usb_reply_limit_length:
    rcall usb_service_pending
    cp r24, r6
    cpc r1, r7
    /* Carry marks a source shorter than wLength. SBC preserves that carry
     * while saving the read-only flag: FF needs a terminating ZLP,
     * 00 reaches wLength and suppresses an extra full-packet ZLP. */
    sbc r12, r12
    brlo usb_reply_store_length
    mov r24, r6
usb_reply_store_length:
    /* Poll before publishing: a replacement SETUP abandons this reply. */
    rcall usb_service_pending
    std Y+CTX_MSG_LENGTH, r24
/* The request length is consumed; R6:R7 become the idle counter again. */
    mov r6, r1
    mov r7, r1
    rjmp usb_rx_release_buffer

/* Unsupported control requests fail at Data/Status rather than report a
 * successful zero-length reply. A fresh SETUP resets TX_LENGTH to NAK. */
usb_reply_stall:
    ldi r18, USB_PID_STALL
    std Y+CTX_TX_LENGTH, r18
    ldi r24, USB_NO_MESSAGE
    rjmp usb_reply_store_length
