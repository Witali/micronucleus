usb_rx_release_buffer:
usb_tx_prepare_pending_reply:
    eor r0, r0
    ldi r25, 0x00
    rcall usb_service_pending
    ldd r24, Y+CTX_TX_LENGTH
    sbrs r24, USB_HANDSHAKE_FLAG_BIT
    rjmp bootloader_check_idle_timeout
    ldd r24, Y+CTX_MSG_LENGTH
    cpi r24, USB_NO_MESSAGE
    brbs SREG_Z, bootloader_check_idle_timeout
    mov r23, r24
    subi r23, USB_EP0_PAYLOAD_BYTES
    brsh usb_tx_prepare_data_packet
    ldi r23, USB_NO_MESSAGE
    rjmp .Ltx_store_remainder
usb_tx_prepare_data_packet:
    ldi r24, USB_EP0_PAYLOAD_BYTES
.Ltx_store_remainder:
    std Y+CTX_MSG_LENGTH, r23
    ldi r18, USB_DATA_PID_TOGGLE
    eor r9, r18
    std Y+CTX_TX_PID, r9
usb_tx_initialize_payload_crc:
    ldi r26, LOW8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
    ldi r27, HIGH8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
usb_tx_copy_flash_payload:
    rcall usb_service_pending
    movw r30, r14
    cp r1, r24
    breq usb_crc16_payload_complete
    lpm r18, Z+
    st X+, r18
    movw r14, r30
usb_crc16_mix_byte:
    eor r0, r18
usb_crc16_shift_bit:
    rcall usb_service_pending
    sec
    ror r25
    ror r0
    brbs SREG_C, usb_crc16_advance_bit_count
    eor r0, r29
    eor r25, r21
usb_crc16_advance_bit_count:
    subi r24, LOW8(-CRC_BIT_COUNTER_INCREMENT)
    brbs SREG_C, usb_crc16_shift_bit
usb_crc16_byte_complete:
    dec r24
    rjmp usb_tx_copy_flash_payload
usb_crc16_payload_complete:
usb_tx_append_payload_crc:
usb_crc16_append:
    st X+, r0
    st X+, r25
usb_crc16_core_end:
usb_tx_publish_packet_length:
    rcall usb_service_pending
    std Y+CTX_TX_LENGTH, r26
