/* Shared EP0 reply publication. Standard Flash replies provide R18, the
 * source pointer's low byte; READ8 enters the limiter with R14:R15 set.
 * A replacement SETUP at either poll abandons the interrupted reply. */
usb_reply_one_byte_flash:
    ldi r24, 1
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
    rcall usb_service_pending
    std Y+CTX_MSG_LENGTH, r24
    /* The request length is consumed; R6:R7 become the idle counter again. */
    mov r6, r1
    mov r7, r1
    rjmp usb_rx_release_buffer
