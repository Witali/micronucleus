/* Parse staged SETUP before deferred work. Token reception overwrites
 * RX bytes 22..24, so capture bmRequestType/bRequest before any service. */
usb_control_process_received_packet:
/* Y is restored by external PHY return, or retained on poll timeout. */
    ldd r18, Y+CTX_RX_LENGTH
    ldd r19, Y+CTX_RX_TOKEN
    std Y+CTX_RX_LENGTH, r1
    cpi r18, (USB_SETUP_BYTES + USB_RX_PACKET_OVERHEAD)
    brne bootloader_check_pending_command
    cpi r19, USB_PID_SETUP
    brne bootloader_check_pending_command
/* The cooperative helper enters here only after proving exact SETUP
 * length/token, restoring Y, releasing RX_LENGTH and discarding its call. */
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
