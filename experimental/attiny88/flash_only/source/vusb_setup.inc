usb_validate_setup:
    ldd r18, Y+CTX_RX_LENGTH
    cpi r18, (USB_SETUP_BYTES + USB_RX_PACKET_OVERHEAD)
    brne .Lservice_done
usb_validate_setup_token:
    ldd r18, Y+CTX_RX_TOKEN
    cpi r18, USB_PID_SETUP
    brne .Lservice_done
    pop r18
    pop r18
    std Y+CTX_RX_LENGTH, r1
usb_setup_capture_fields:
/* A new SETUP replaces the old control transfer before its status ACK;
 * never let a later reply unlock a stale erase/commit/RUN command. */
    mov r3, r1
    ldd r24, Y+CTX_SETUP_REQUEST_TYPE
    ldd r25, Y+CTX_SETUP_REQUEST
    /* Invalidate the old reply before an early cooperative poll. */
    ldi r18, USB_PID_NAK
    std Y+CTX_TX_LENGTH, r18
    rcall usb_service_pending
/* With wLength zero USB ignores the direction bit: status is IN. Otherwise
 * preserve the accepted direction so an OUT cannot unlock a write's status. */
    mov r11, r24
    mov r18, r6
    or r18, r7
    brne .Lsetup_has_data_stage
    /* USB9.3.1 ignores D7 with no Data stage. Canonicalize the dispatch:
     * supported standard GET codes are even, supported writes are odd.
     * Vendor routing uses only TYPE; its no-data writes set R11 separately. */
    ori r24, 0x80
    sbrc r25, 0
    andi r24, 0x7f
    mov r11, r1
.Lsetup_has_data_stage:
    ldd r18, Y+CTX_DEVICE_ADDRESS
    std Y+CTX_NEW_DEVICE_ADDRESS, r18
    mov r10, r8
    ldi r18, USB_PID_DATA0
    mov r9, r18
    rcall usb_service_pending
/* Preserve full R24 for standard dispatch. The computer validates vendor
 * request fields; only standard/class/vendor sorting belongs here. */
    sbrc r24, 5
    rjmp usb_reply_stall
    sbrc r24, 6
    rjmp bootloader_handle_vendor_request
