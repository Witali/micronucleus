/* EP0 packet preparation and outgoing CRC. Placed directly after deferred
 * command clearing so the ordinary idle/SPM paths enter without a trampoline.
 * Vendor/shared reply helpers are in vusb_requests.inc.
 */
usb_rx_release_buffer:
usb_tx_prepare_pending_reply:
/* CRC state is dead until this preparation starts and survives PHY service. */
    eor r0, r0
    ldi r25, 0x00
    rcall usb_service_pending
    ldd r24, Y+CTX_TX_LENGTH
    sbrs r24, USB_HANDSHAKE_FLAG_BIT
    rjmp bootloader_check_idle_timeout
    ldd r24, Y+CTX_MSG_LENGTH
    cpi r24, USB_NO_MESSAGE
    brbs SREG_Z, bootloader_check_idle_timeout
/* Count and complemented CRC stay in PHY-preserved R24/R0/R25.
 * Publish the next message remainder while TX_LENGTH still advertises NAK. */
    mov r23, r24
    cpi r24, (USB_EP0_PAYLOAD_BYTES + 1)
    brbs SREG_C, usb_tx_prepare_data_packet
    ldi r24, USB_EP0_PAYLOAD_BYTES
usb_tx_prepare_data_packet:
    sub r23, r24
    cpi r24, USB_EP0_PAYLOAD_BYTES
    sbci r23, 0
    std Y+CTX_MSG_LENGTH, r23
/* SETUP initialized R9 to DATA0; first prepared response is DATA1. */
    ldi r18, USB_DATA_PID_TOGGLE
    eor r9, r18
    std Y+CTX_TX_PID, r9
/* Copy Flash/EEPROM into the TX buffer while computing USB CRC16.
 * R24 packs remaining bytes in its low five bits and the bit phase above them;
 * adding 32 wraps after eight shifts, then DEC consumes one payload byte.
 * R0:R25 hold the complemented CRC representation used by the original PHY.
 */
usb_tx_initialize_payload_crc:
    ldi r26, LOW8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
    ldi r27, HIGH8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
usb_tx_copy_flash_payload:
    rcall usb_service_pending
    movw r30, r14
    cp r1, r24
    breq usb_crc16_payload_complete
    sbrc r15, 7
    rjmp usb_tx_eeprom_byte
    lpm r18, Z+
    rjmp usb_tx_store_byte
usb_tx_eeprom_byte:
    out _SFR_IO_ADDR(EEARL), r30
    sbi _SFR_IO_ADDR(EECR), EERE
    in r18, _SFR_IO_ADDR(EEDR)
    inc r30
usb_tx_store_byte:
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
