usb_validate_setup:
    /* Only accepted SETUP (11) owns bit3. Deferred command values
     * 0,2,3,4,5,64 all leave it clear. Reset clears R3 as well. */
    sbrs r3, USB_SETUP_PENDING_BIT
    ret
    pop r18
    pop r18
usb_setup_capture_fields:
/* A new SETUP replaces the old control transfer before its status ACK;
 * never let a later reply unlock a stale erase/commit/RUN command. */
    mov r3, r1
    /* Both RX callers dispatch here before polling again. Capture the raw
     * two-byte header before that poll; the six payload fields are already
     * protected in registers by the PHY. */
    ldd r24, Y+CTX_SETUP_REQUEST_TYPE
    ldd r25, Y+CTX_SETUP_REQUEST
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
