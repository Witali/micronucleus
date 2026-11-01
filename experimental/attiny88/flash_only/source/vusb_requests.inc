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
/* Shared STALL handler moved beside the standard-request dispatcher.
 * Both vendor and standard paths branch to that single entry. */
