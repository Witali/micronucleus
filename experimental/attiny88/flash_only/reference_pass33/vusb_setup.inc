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
    mov r8, r1          /* a new SETUP cancels unacked previous IN */
    ldi r18, USB_PID_NAK
    std Y+CTX_TX_LENGTH, r18
    rcall usb_service_pending
    andi r24, USB_REQUEST_TYPE_MASK
    brne bootloader_handle_vendor_request
