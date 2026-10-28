bootloader_handle_vendor_request:
    cpi r25, REQ_UNIFIED_READ
    brne bootloader_check_set_flash_address
memory_read:
memory_read_advance:
    /* READ8 snapshots SELECT's cursor. OUT status later commits its advance. */
    movw r14, r4
    ldi r24, USB_EP0_PAYLOAD_BYTES
    rjmp usb_reply_limit_length
/* Unsupported control requests fail at Data/Status rather than report a
 * successful zero-length reply. A fresh SETUP resets TX_LENGTH to NAK. */
usb_reply_stall:
    ldi r18, USB_PID_STALL
    std Y+CTX_TX_LENGTH, r18
    ldi r24, USB_NO_MESSAGE
    rjmp usb_reply_store_length
