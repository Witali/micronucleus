/* Standard EP0 GET_STATUS, SET_ADDRESS, descriptors, configuration and
 * interface requests. Descriptor pointers share one 256-byte Flash window.
 * Helpers in vusb_ep0.inc read Flash and clamp to the host's wLength.
 */
usb_standard_dispatch:
/* R24 caches wValue and survives every cooperative PHY service. */
    ldd r24, Y+CTX_SETUP_VALUE_LOW
    cpse r25, r1
    rjmp usb_standard_check_set_address
    ldi r24, USB_STATUS_REPLY_BYTES
    rjmp usb_reply_use_scratch_buffer
usb_standard_check_set_address:
    cpi r25, USB_REQ_SET_ADDRESS
    brbc SREG_Z, usb_standard_check_get_descriptor
    lsl r24
    std Y+CTX_NEW_DEVICE_ADDRESS, r24
    rjmp usb_reply_empty
usb_standard_check_get_descriptor:
    rcall usb_service_pending
    cpi r25, USB_REQ_GET_DESCRIPTOR
    brbc SREG_Z, usb_standard_check_configuration
    ldd r24, Y+CTX_SETUP_VALUE_HIGH
    ldi r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET)
    cpi r24, USB_DESCRIPTOR_DEVICE
    breq desc_ptr
    cpi r24, USB_DESCRIPTOR_CONFIGURATION
    brne ee_std_empty
    ldi r18, LOW8(BOOT_AT + USB_CONFIGURATION_OFFSET)
desc_ptr:
    ldi r19, HIGH8(BOOT_AT + USB_CONFIGURATION_OFFSET)
    ldi r24, USB_DEVICE_DESCRIPTOR_BYTES
    rjmp usb_reply_set_pointer
usb_standard_check_configuration:
    cpi r25, USB_REQ_GET_CONFIGURATION
    brbs SREG_Z, usb_standard_get_configuration
    cpi r25, USB_REQ_SET_CONFIGURATION
    brbc SREG_Z, usb_standard_check_get_interface
/* Configuration is always 0 or 1. Compare the complete wValue word;
 * LDD preserves the borrow from CPI before the high-byte CPC. */
    cpi r24, 2
    ldd r18, Y+CTX_SETUP_VALUE_HIGH
    cpc r18, r1
    brsh ee_std_empty
    std Y+CTX_CONFIGURATION, r24
    rjmp usb_reply_empty
usb_standard_get_configuration:
/* Device descriptor byte16 is zero; adjacent byte17 is one. Add their
 * low address to the strictly validated configuration without a second LDI. */
    ldd r18, Y+CTX_CONFIGURATION
    subi r18, LOW8(-(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 16))
    ldi r24, 1
    rjmp usb_reply_use_flash_pointer
usb_standard_check_get_interface:
    cpi r25, USB_REQ_GET_INTERFACE
    brne ee_std_empty
usb_standard_scratch_reply:
usb_reply_pointer_trampoline:
legacy_led_on_anchor:
ee_return_one:
    ldi r24, 1
    rjmp usb_reply_use_scratch_buffer
ee_std_empty:
ee_empty:
/* Standard rejects and EEPROM bounds share the same empty-reply tail. */
ee_bad_addr:
    rjmp usb_reply_empty
