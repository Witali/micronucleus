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
    mov r25, r6
    cp r24, r25
    cpc r1, r7
    brlo usb_reply_store_length
    mov r24, r25
    /* This source satisfies wLength: an exact final full packet needs no
     * extra ZLP. All accepted read request types leave R11 bit5 available. */
    ldi r18, (1 << USB_REPLY_EXACT_LENGTH_BIT)
    or r11, r18
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
