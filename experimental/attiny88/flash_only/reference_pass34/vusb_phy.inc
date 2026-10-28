USB_handler:
    movw r30, r28
usb_rx_wait_for_j:
    inc r28
    sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    brbc SREG_Z, usb_rx_wait_for_j
usb_rx_wait_for_k:
    sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp usb_rx_found_k
    sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp usb_rx_found_k
    sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp usb_rx_found_k
    sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp usb_rx_found_k
    sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp usb_rx_found_k
    sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp usb_rx_found_k
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp usb_return_context
usb_rx_found_k:
    ldi r28, LOW8(USB_CONTEXT_BASE + CTX_RX_BUFFER)
    rcall usb_return_polynomial
    ldi r22, USB_RX_PAIR_COUNTER_INCREMENT
    sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp usb_rx_sync_confirmed
    push r0
    pop r0
    rjmp usb_rx_wait_for_k
usb_rx_sync_confirmed:
usb_rx_delay_complete:
    ldi r18, 0x00
    ldi r20, USB_RX_INITIAL_STUFF_MASK
    rcall usb_return_polynomial
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    bst r16, USB_MINUS_BIT
    bld r18, 7
    ldd r19, Z+CTX_RX_LENGTH
    ldi r21, 0x00
    ldi r23, USB_RX_BUFFER_BYTES
    rjmp usb_rx_sample_odd_bit
usb_rx_unstuff_bit6:
    andi r17, USB_LINE_MASK
    ori r20, USB_RX_CORRECTION_BIT6_MASK
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    mov r16, r17
    subi r21, LOW8(-1)
    rjmp usb_rx_sample_bit7
usb_rx_unstuff_bit7:
    ori r20, USB_RX_CORRECTION_BIT7_MASK
    in r17, _SFR_IO_ADDR(PIND)
    andi r17, USB_LINE_MASK
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    subi r21, USB_RX_UNSTUFF7_LEAP_ADJUST
    rjmp usb_rx_finish_byte
usb_rx_unstuff_even_bit:
    ori r20, USB_RX_CORRECTION_BIT6_MASK
    in r16, _SFR_IO_ADDR(PIND)
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    andi r16, USB_LINE_MASK
    brbs SREG_Z, usb_rx_end_packet
    subi r21, LOW8(-1)
    rjmp usb_rx_unstuff_even_resume_jump
usb_rx_unstuff_even_resume_jump:
    rjmp usb_rx_shift_stuff_mask
usb_rx_unstuff_odd_bit:
    ori r20, USB_RX_CORRECTION_BIT5_MASK
    in r17, _SFR_IO_ADDR(PIND)
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    andi r17, USB_LINE_MASK
    brbs SREG_Z, usb_rx_end_packet
    subi r21, LOW8(-1)
    rjmp usb_rx_unstuff_odd_resume_jump
usb_rx_unstuff_odd_resume_jump:
    rjmp usb_rx_advance_bit_pair
usb_rx_decode_bit6:
    andi r16, USB_LINE_MASK
    eor r17, r16
    subi r21, 0x01
    brbc SREG_N, usb_rx_shift_bit6
    subi r21, LOW8(-USB_RX_LEAP_PERIOD)
    nop
usb_rx_shift_bit6:
    subi r17, 0x01
    ror r18
usb_rx_sample_bit7:
    cpi r18, USB_STUFF_HISTORY_THRESHOLD
    in r17, _SFR_IO_ADDR(PIND)
    brbc SREG_C, usb_rx_unstuff_bit6
    andi r17, USB_LINE_MASK
    eor r16, r17
    subi r16, 0x01
    ror r18
usb_rx_finish_byte:
    cpi r18, USB_STUFF_HISTORY_THRESHOLD
    brbc SREG_C, usb_rx_unstuff_bit7
    eor r20, r18
    st Y+, r20
usb_rx_sample_even_bit:
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    eor r17, r16
    andi r20, USB_RX_LOW_BITS_MASK
    subi r17, 0x01
    ror r18
    cpi r18, USB_STUFF_HISTORY_THRESHOLD
    brbc SREG_C, usb_rx_unstuff_even_bit
usb_rx_shift_stuff_mask:
    lsr r20
    lsr r20
usb_rx_sample_odd_bit:
    in r17, _SFR_IO_ADDR(PIND)
    andi r17, USB_LINE_MASK
    brbs SREG_Z, usb_rx_end_packet
    eor r16, r17
    subi r16, 0x01
    ror r18
    cpi r18, USB_STUFF_HISTORY_THRESHOLD
    brbc SREG_C, usb_rx_unstuff_odd_bit
usb_rx_advance_bit_pair:
    subi r22, LOW8(-USB_RX_PAIR_COUNTER_INCREMENT)
    brbs SREG_C, usb_rx_sample_even_bit
    subi r23, 0x01
    in r16, _SFR_IO_ADDR(PIND)
    brbc SREG_C, usb_rx_decode_bit6
usb_rx_overflow:
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
usb_rx_ignore_packet:
    mov r2, r1
    eor r16, r16
    rjmp usb_rx_store_token
usb_rx_end_packet:
    subi r23, USB_RX_BUFFER_BYTES
    neg r23
    ldi r28, LOW8(USB_CONTEXT_BASE + CTX_RX_BUFFER)
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
    ldd r16, Y+USB_PACKET_PID_OFFSET
    cpi r16, USB_PID_ACK
    breq usb_rx_check_ack
    /* A non-ACK packet closes the previous handshake window; a new IN
     * reopens it without losing the cached DATA/PID for retransmission. */
    mov r2, r1
    cpi r16, USB_PID_DATA0
    brbs SREG_Z, usb_rx_handle_data
    cpi r16, USB_PID_DATA1
    brbs SREG_Z, usb_rx_handle_data
    ldd r18, Z+CTX_DEVICE_ADDRESS
    ldd r17, Y+USB_PACKET_ADDRESS_OFFSET
    add r17, r17
    cpse r17, r18
    rjmp usb_rx_ignore_packet
    cpi r16, USB_PID_IN
    brbs SREG_Z, usb_rx_handle_in
    cpi r16, USB_PID_SETUP
    brbs SREG_Z, usb_rx_handle_setup_or_out
    cpi r16, USB_PID_OUT
    brbc SREG_Z, usb_rx_ignore_packet
usb_rx_handle_setup_or_out:
    ldi r28, USB_NEXT_DATA_WAIT_COUNT
usb_rx_wait_for_data:
    in r17, _SFR_IO_ADDR(PCIFR)
    sbrc r17, PCIF2
    rjmp usb_rx_store_token
    dec r28
    brbc SREG_Z, usb_rx_wait_for_data
usb_rx_store_token:
    std Z+CTX_CURRENT_TOKEN, r16
usb_handler_packet_done:
    in r28, _SFR_IO_ADDR(PCIFR)
    sbrc r28, PCIF2
    rjmp usb_rx_wait_for_j
    rjmp usb_return_context
/* ACK PID has no USB address. Only a one-byte PID packet that follows
 * a transmitted IN DATA is permitted to release the immutable TX packet. */
usb_rx_check_ack:
    cpi r23, 1
    brne usb_rx_ignore_packet
    tst r2
    breq usb_rx_ignore_packet
usb_rx_accept_ack:
    mov r2, r1
    ldi r19, USB_PID_NAK
    std Z+CTX_TX_LENGTH, r19
    /* SET_ADDRESS becomes effective only after ACK of status DATA1. */
    ldd r17, Z+CTX_NEW_DEVICE_ADDRESS
    std Z+CTX_DEVICE_ADDRESS, r17
    rjmp usb_handler_packet_done
usb_rx_handle_data:
    ldd r18, Z+CTX_CURRENT_TOKEN
    and r18, r18
    brbs SREG_Z, usb_handler_packet_done
    and r19, r19
    brbc SREG_Z, usb_tx_send_nak
    cpi r23, (USB_RX_PACKET_OVERHEAD + 1)
    brbs SREG_N, usb_tx_send_ack
    std Z+CTX_RX_LENGTH, r23
    std Z+CTX_RX_TOKEN, r18
    rjmp usb_tx_send_ack
usb_rx_handle_in:
    cpi r19, 0x01
    brbc SREG_S, usb_tx_send_nak
    ldd r19, Z+CTX_TX_LENGTH
    sbrc r19, USB_HANDSHAKE_FLAG_BIT
    rjmp usb_tx_send_count_handshake
    mov r2, r19       /* a DATA packet was actually transmitted */
    ldi r28, LOW8(USB_CONTEXT_BASE + CTX_TX_PID)
    ldi r29, HIGH8(USB_CONTEXT_BASE + CTX_TX_PID)
    rjmp usb_tx_acquire_bus
usb_tx_stuff_regular_bit:
    eor r16, r21
    ldi r17, 0x00
    rjmp usb_tx_stuff_regular_delay
usb_tx_stuff_regular_delay:
    nop
    out _SFR_IO_ADDR(PORTD), r16
    rjmp usb_tx_check_regular_stuffing
usb_tx_stuff_bit6:
    eor r16, r21
    ldi r17, 0x00
    adc r18, r18
    rjmp usb_tx_send_bit6
usb_tx_stuff_bit7:
    ldi r17, 0x00
    rjmp usb_tx_send_bit7
usb_tx_send_nak:
    ldi r20, USB_PID_NAK
    rjmp usb_tx_prepare_handshake
usb_tx_send_ack:
    ldi r19, USB_PID_ACK
usb_tx_send_count_handshake:
    mov r20, r19
usb_tx_prepare_handshake:
    ldi r28, LOW8(USB_HANDSHAKE_REGISTER)
    ldi r29, HIGH8(USB_HANDSHAKE_REGISTER)
    ldi r19, USB_HANDSHAKE_TX_BYTES
usb_tx_acquire_bus:
    in r17, _SFR_IO_ADDR(DDRD)
    ori r17, USB_LINE_MASK
    sbi _SFR_IO_ADDR(PORTD), USB_MINUS_BIT
    in r16, _SFR_IO_ADDR(PORTD)
    out _SFR_IO_ADDR(DDRD), r17
    ldi r21, USB_LINE_MASK
    ldi r18, USB_SYNC_BYTE
usb_tx_begin_byte:
    ldi r22, USB_TX_BIT_COUNTER_SEED
usb_tx_send_regular_bit:
    sbrs r18, 0
    eor r16, r21
    out _SFR_IO_ADDR(PORTD), r16
    ror r18
    ror r17
usb_tx_check_regular_stuffing:
    cpi r17, USB_STUFF_HISTORY_THRESHOLD
    brbc SREG_C, usb_tx_stuff_regular_bit
    lsr r22
    brbc SREG_C, usb_tx_send_regular_bit
    brbc SREG_Z, usb_tx_send_regular_bit
    sbrs r18, 0
    eor r16, r21
usb_tx_send_bit6:
    out _SFR_IO_ADDR(PORTD), r16
    ror r18
    ror r17
    cpi r17, USB_STUFF_HISTORY_THRESHOLD
    brbc SREG_C, usb_tx_stuff_bit6
    ror r18
usb_tx_send_bit7:
    ror r17
    sbrs r17, 7
    eor r16, r21
    nop
    cpi r17, USB_STUFF_HISTORY_THRESHOLD
    out _SFR_IO_ADDR(PORTD), r16
    brbc SREG_C, usb_tx_stuff_bit7
    ld r18, Y+
    dec r19
    brbc SREG_Z, usb_tx_begin_byte
    andi r16, USB_LINES_CLEAR_MASK
    /* Preserve four cycles before SE0; do not commit USB address on EOP. */
    rjmp .+0
    rjmp .+0
    out _SFR_IO_ADDR(PORTD), r16
    /* SE0 remains in USB Low-Speed timing window for DATA and handshake. */
    rjmp .+0
usb_tx_finish_eop:
    ori r16, (1 << USB_MINUS_BIT)
    ldi r21, USB_EOP_DELAY_LOOPS
usb_tx_eop_delay:
    dec r21
    brbc SREG_Z, usb_tx_eop_delay
    out _SFR_IO_ADDR(PORTD), r16
    /* Bit PCIF2 equals the USB D+ DDRD bit. At this point the
       transmitter has set DDRD bits 1 and 2, so OUT writes 1 to
       PCIF2 (W1C) while IN obtains the DDR mask already needed below.
       IN+OUT = 2 cycles, replacing the original 2-cycle SBI +
       1-cycle IN. RCALL/RET = 7 cycles rather than 6 RJMP cycles;
       total J drive/PCIF2-clear timing is therefore unchanged.
       PCIF1 is also cleared; bootloader does not enable PCIE1. */
    in r17, _SFR_IO_ADDR(DDRD)
    out _SFR_IO_ADDR(PCIFR), r17
    andi r17, USB_LINES_CLEAR_MASK
    rcall usb_handler_return
    out _SFR_IO_ADDR(DDRD), r17
    cbi _SFR_IO_ADDR(PORTD), USB_MINUS_BIT
usb_return_context:
    movw r28, r30
usb_return_polynomial:
    ldi r21, HIGH8(CRC16_POLYNOMIAL)
usb_handler_return:
    ret
