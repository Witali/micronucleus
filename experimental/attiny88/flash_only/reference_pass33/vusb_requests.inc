bootloader_handle_vendor_request:
    mov r7, r1
    cpi r25, REQ_UNIFIED_READ
    brne bootloader_check_set_flash_address
memory_read:
    movw r18, r4
memory_read_advance:
    ldi r24, USB_EP0_PAYLOAD_BYTES
    add r4, r24
    adc r5, r1
    rjmp usb_reply_set_pointer
usb_reply_use_scratch_buffer:
    ldi r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 14)
usb_reply_use_flash_pointer:
    ldi r19, HIGH8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 14)
usb_reply_set_pointer:
    movw r14, r18
usb_reply_limit_length:
    rcall usb_service_pending
    ldd r25, Y+CTX_SETUP_LENGTH_LOW
    cp r25, r24
    ldd r18, Y+CTX_SETUP_LENGTH_HIGH
    cpc r18, r1
    brsh usb_reply_store_length
    mov r24, r25
usb_reply_store_length:
    std Y+CTX_MSG_LENGTH, r24
    rjmp usb_rx_release_buffer
