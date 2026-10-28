/* EP0 implements the standard requests needed by this single-interface,
 * vendor-specific device. Unsupported requests and recipients stall both
 * directions until a new SETUP. R24 is cached, never reloaded from RX SRAM. */
usb_standard_dispatch:
    rcall usb_service_pending
    cpi r24, 0x80
    breq usb_standard_device_in
    cpi r24, 0x00
    breq usb_standard_device_out
    cpi r24, 0x82
    breq usb_standard_endpoint_in
    cpi r24, 0x81
    brne usb_standard_stall
    /* Bound USB polling through interface and configuration checks. */
    rcall usb_service_pending
/* Interface zero exists only after SET_CONFIGURATION(1). */
    mov r18, r14
    or r18, r15
    brne usb_standard_stall
    ldd r18, Y+CTX_CONFIGURATION
    cpi r18, 1
    brne usb_standard_stall
    tst r25
    breq usb_standard_get_status
    cpi r25, USB_REQ_GET_INTERFACE
    breq usb_standard_scratch_reply
    rjmp usb_reply_stall
usb_standard_scratch_reply:
usb_reply_pointer_trampoline:
legacy_led_on_anchor:
ee_return_one:
    ldi r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 14)
/* Place the shared publisher here so GET_INTERFACE falls through and
 * device-OUT conditional branches remain inside AVR's short-branch span. */
#include "vusb_replies.inc"
usb_standard_endpoint_in:
/* Only endpoint zero exists; either direction of its address is valid. */
    mov r18, r14
    andi r18, 0x7f
    or r18, r15
    brne usb_standard_stall
    tst r25
    brne usb_standard_stall
usb_standard_get_status:
    ldi r24, USB_STATUS_REPLY_BYTES
/* The two-byte zero reply bypasses the one-byte availability entry. */
usb_reply_use_scratch_buffer:
    ldi r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 14)
    rjmp usb_reply_use_flash_pointer
usb_standard_device_in:
    tst r25
    breq usb_standard_get_status
    cpi r25, USB_REQ_GET_DESCRIPTOR
    breq usb_standard_check_get_descriptor
    cpi r25, USB_REQ_GET_CONFIGURATION
    breq usb_standard_get_configuration
usb_standard_stall:
    rjmp usb_reply_stall
usb_standard_check_get_descriptor:
    rcall usb_service_pending
/* Device/configuration descriptor number is zero; strings are not provided. */
    mov r18, r12
    or r18, r14
    or r18, r15
    brne usb_standard_stall
    mov r24, r13
    ldi r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET)
    cpi r24, USB_DESCRIPTOR_DEVICE
    breq desc_ptr
    cpi r24, USB_DESCRIPTOR_CONFIGURATION
    brne usb_standard_stall
    ldi r18, LOW8(BOOT_AT + USB_CONFIGURATION_OFFSET)
desc_ptr:
    ldi r24, USB_DEVICE_DESCRIPTOR_BYTES
    rjmp usb_reply_use_flash_pointer
usb_standard_device_out:
    mov r24, r12
    cpi r25, USB_REQ_SET_ADDRESS
    brne usb_standard_check_configuration
    std Y+CTX_NEW_DEVICE_ADDRESS, r24
    /* Cache the pending address CRC before exposing its status DATA. Each
     * bit services USB; a replacement SETUP aborts this calculation. */
    /* Seed 30 folds the CRC5 final complement into the fixed 11-bit transform;
     * after three shifts R10 is the full endpoint-zero wire byte. */
    ldi r18, 30
    mov r10, r18
    /* Unconsumed address bits shift into the CRC state as the loop runs. */
    eor r10, r24
    ldi r25, 11
.Laddress_crc5_bit:
    rcall usb_service_pending
    lsr r10
    brcc .Laddress_crc5_advance
    ldi r18, 0x14
    eor r10, r18
.Laddress_crc5_advance:
    dec r25
    brne .Laddress_crc5_bit
    lsl r10
    lsl r10
    lsl r10
    rjmp usb_reply_empty
usb_standard_check_configuration:
    cpi r25, USB_REQ_SET_CONFIGURATION
    brne usb_standard_stall
/* This descriptor exposes only configuration 1; zero deconfigures it. */
    cpi r24, 2
    /* USB9.4.7 leaves nonzero upper wValue undefined; use its low byte. */
    brsh usb_standard_stall
    std Y+CTX_CONFIGURATION, r24
    rjmp usb_reply_empty

/* This placement keeps device-OUT dispatch inside its short-branch span. */
usb_standard_get_configuration:
    ldd r18, Y+CTX_CONFIGURATION
    subi r18, LOW8(-(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 16))
    rjmp usb_reply_one_byte_flash
