/* Standard EP0 GET_STATUS, SET_ADDRESS, descriptors, configuration and
 * interface requests. Descriptor pointers share one 256-byte Flash window.
 * Helpers in vusb_ep0.inc choose SRAM/Flash and clamp to the host's wLength.
 */
usb_standard_dispatch:
ldd r18, Y+CTX_SETUP_VALUE_LOW
cpse r25, r1
rjmp usb_standard_check_set_address
ldi r24, USB_STATUS_REPLY_BYTES
rjmp usb_reply_use_scratch_buffer
usb_standard_check_set_address:
cpi r25, USB_REQ_SET_ADDRESS
brbc SREG_Z, usb_standard_check_get_descriptor
std Y+CTX_NEW_DEVICE_ADDRESS, r18
rjmp usb_reply_use_scratch_buffer
usb_standard_check_get_descriptor:
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
std Y+CTX_CONFIGURATION, r18
rjmp usb_reply_use_scratch_buffer
/* Reply directly from the configuration byte; never overwrite zero reply
 * bytes16/17, since GET_STATUS and GET_INTERFACE reuse them after any packet. */
usb_standard_get_configuration:
ldi r18, LOW8(USB_CONTEXT_BASE + CTX_CONFIGURATION)
ldi r24, 1
rjmp usb_reply_use_sram_pointer
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
