/* Shared SETUP validation and capture. The cooperative PHY path falls
 * through with its original call frame; main RCALLs the token entry only
 * after proving the exact length. Invalid paths RET through that same frame.
 * Both accepted paths discard exactly one frame before tail dispatch. */
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
    ldd r24, Y+CTX_SETUP_REQUEST_TYPE
    ldd r25, Y+CTX_SETUP_REQUEST
    ldd r18, Y+CTX_DEVICE_ADDRESS
    std Y+CTX_NEW_DEVICE_ADDRESS, r18
    ldi r18, USB_PID_DATA0
    mov r9, r18
    ldi r18, USB_PID_NAK
    std Y+CTX_TX_LENGTH, r18
    rcall usb_service_pending
    andi r24, USB_REQUEST_TYPE_MASK
    breq .Lstandard_setup
    rjmp bootloader_handle_vendor_request
.Lstandard_setup:
    rjmp usb_standard_dispatch
