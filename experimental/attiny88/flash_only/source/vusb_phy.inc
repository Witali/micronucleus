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
    /* A false SOP closes ACK/token eligibility, retaining cached TX data. */
    rjmp usb_rx_ignore_packet
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
    nop
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
/* Mandatory stuffed symbols must be NRZI transitions. These short tails
 * skip history tests that are known false after clearing the six-one run. */
usb_rx_unstuff_bit6:
    andi r17, USB_LINE_MASK
    ori r20, USB_RX_CORRECTION_BIT6_MASK
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    cp r16, r17
    breq usb_rx_reject_stuff
    mov r16, r17
    subi r21, LOW8(-1)
    nop
    in r17, _SFR_IO_ADDR(PIND)
    nop
    andi r17, USB_LINE_MASK
    eor r16, r17
    subi r16, 0x01
    ror r18
    rjmp usb_rx_finish_byte_commit
usb_rx_unstuff_bit7:
/* The correction mask has bit7 clear. XOR before clearing history gives
 * the same decoded final one, saving the old ORI correction instruction. */
    mov r16, r17
    in r17, _SFR_IO_ADDR(PIND)
    andi r17, USB_LINE_MASK
    cp r16, r17
    breq usb_rx_reject_stuff
    eor r20, r18
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    subi r21, USB_RX_UNSTUFF7_LEAP_ADJUST
    rjmp usb_rx_store_byte
usb_rx_reject_stuff:
    rjmp usb_rx_ignore_packet
usb_rx_confirm_byte_eop:
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    st Y+, r20
    breq usb_rx_eop_jump
    /* A recovered crossover supplies a zero bit; the previous byte is
     * already stored and no history check can match after this zero. */
    eor r20, r20
    lsr r18
    rjmp usb_rx_sample_odd_bit
usb_rx_eop_jump:
    rjmp usb_rx_end_packet
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
usb_rx_finish_byte_commit:
    eor r20, r18
usb_rx_store_byte:
    /* Observe the next bit before the two-cycle store, giving a short
     * legal EOP room for a second sample four cycles later. */
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    breq usb_rx_confirm_byte_eop
    st Y+, r20
    eor r17, r16
    /* No correction for the new byte exists yet. Clearing the old byte
     * replaces ANDI plus two shifts; RJMP preserves the next sample. */
    eor r20, r20
    subi r17, 0x01
    ror r18
    cpi r18, USB_STUFF_HISTORY_THRESHOLD
    brbc SREG_C, usb_rx_unstuff_even_bit
    rjmp usb_rx_sample_odd_bit
usb_rx_sample_even_bit:
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
/* A full-byte EOP starts here; receiver-observed SE0 can be only670ns. */
    brbs SREG_Z, usb_rx_eop_jump
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
    rjmp usb_rx_overflow
usb_rx_unstuff_odd_bit:
    ori r20, USB_RX_CORRECTION_BIT5_MASK
    mov r16, r17
    in r17, _SFR_IO_ADDR(PIND)
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    andi r17, USB_LINE_MASK
    brbs SREG_Z, usb_rx_reject_stuff_late
    subi r21, LOW8(-1)
    cp r16, r17
    breq usb_rx_reject_stuff_late
    subi r22, LOW8(-USB_RX_PAIR_COUNTER_INCREMENT)
    brbs SREG_C, usb_rx_unstuff_odd_next_even
    subi r23, 0x01
    in r16, _SFR_IO_ADDR(PIND)
    brbs SREG_C, usb_rx_overflow
    rjmp usb_rx_decode_bit6
usb_rx_unstuff_odd_next_even:
    nop
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    brbs SREG_Z, usb_rx_eop_jump_late
    eor r17, r16
    andi r20, USB_RX_LOW_BITS_MASK
    subi r17, 0x01
    ror r18
    rjmp usb_rx_shift_stuff_mask
usb_rx_unstuff_even_bit:
    ori r20, USB_RX_CORRECTION_BIT6_MASK
    mov r17, r16
    in r16, _SFR_IO_ADDR(PIND)
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    andi r16, USB_LINE_MASK
    brbs SREG_Z, usb_rx_reject_stuff_late
    subi r21, LOW8(-1)
    cp r17, r16
    breq usb_rx_reject_stuff_late
    lsr r20
    lsr r20
    nop
    in r17, _SFR_IO_ADDR(PIND)
    andi r17, USB_LINE_MASK
    eor r16, r17
    subi r16, 0x01
    ror r18
    rjmp usb_rx_advance_bit_pair
usb_rx_reject_stuff_late:
    rjmp usb_rx_ignore_packet
usb_rx_eop_jump_late:
    rjmp usb_rx_end_packet
/* J is the common success case; recovery polling stays off its path. */
usb_rx_eop_not_j:
    dec r21
    brne usb_rx_wait_eop_j
usb_rx_overflow:
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
usb_rx_ignore_packet:
    mov r2, r1
    eor r16, r16
    rjmp usb_rx_store_token
usb_rx_end_packet:
    subi r23, USB_RX_BUFFER_BYTES
    neg r23
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
usb_rx_check_framing:
    /* Pair phase and a non-SE0 final odd sample must finish a full byte. */
    add r22, r23
    subi r22, USB_RX_PAIR_COUNTER_INCREMENT
    brne usb_rx_ignore_packet
    tst r17
    breq usb_rx_ignore_packet
usb_rx_framing_valid:
    /* Observe actual J recovery before responding. A packet followed by
     * sustained reset SE0 must never make this device drive the bus. */
    ldi r21, 3
usb_rx_wait_eop_j:
    in r20, _SFR_IO_ADDR(PIND)
    andi r20, USB_LINE_MASK
    cpi r20, (1 << USB_MINUS_BIT)
    brne usb_rx_eop_not_j
usb_rx_recovered_j:
    ldd r16, Z+(CTX_RX_BUFFER + USB_PACKET_PID_OFFSET)
    cpi r16, USB_PID_ACK
    breq usb_rx_check_ack
    /* A non-ACK packet closes the previous handshake window; a new IN
     * reopens it without losing the cached DATA/PID for retransmission. */
    mov r2, r1
    cpi r16, USB_PID_DATA0
    brbs SREG_Z, usb_rx_handle_data
    cpi r16, USB_PID_DATA1
    brbs SREG_Z, usb_rx_handle_data
    /* Tokens contain PID and sixteen address/endpoint/CRC bits. */
    cpi r23, 3
    brne usb_rx_ignore_packet
    ldd r18, Z+CTX_DEVICE_ADDRESS
    ldd r17, Z+(CTX_RX_BUFFER + USB_PACKET_ADDRESS_OFFSET)
    cpse r17, r18
    rjmp usb_rx_ignore_packet
    /* Cache endpoint-zero CRC5 per address, without a lookup table.
     * The full-byte comparison also rejects endpoint bits 1..3. */
    ldd r17, Z+(CTX_RX_BUFFER + (USB_PACKET_ADDRESS_OFFSET + 1))
    cp r17, r8
    brne usb_rx_ignore_packet
    cpi r16, USB_PID_IN
    brne .Lrx_not_in
usb_rx_handle_in:
    cpi r19, 0x01
    brbc SREG_S, usb_tx_send_nak
    ldd r19, Z+CTX_TX_LENGTH
    sbrc r19, USB_HANDSHAKE_FLAG_BIT
    rjmp usb_tx_send_count_handshake
    mov r2, r19       /* a DATA packet was actually transmitted */
    /* RX and cached DATA stay on the context page, so Y high is already
     * correct. Handshake TX's high zero is restored from Z before RX. */
    ldi r28, LOW8(USB_CONTEXT_BASE + CTX_TX_PID)
    rjmp usb_tx_acquire_bus
usb_tx_send_nak:
    ldi r20, USB_PID_NAK
    rjmp usb_tx_prepare_handshake
.Lrx_not_in:
    cpi r16, USB_PID_SETUP
    brbs SREG_Z, usb_rx_handle_setup_or_out
    cpi r16, USB_PID_OUT
    brbc SREG_Z, usb_rx_ignore_packet
usb_rx_handle_setup_or_out:
    ldi r28, USB_NEXT_DATA_WAIT_COUNT
usb_rx_wait_for_data:
    sbic _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp usb_rx_store_token
    dec r28
    brbc SREG_Z, usb_rx_wait_for_data
/* One final SOP sample includes synchronization latency at the16-bit edge.
 * A timed-out token must not authorize a later unpaired DATA packet. */
usb_rx_data_timeout_check:
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp usb_rx_store_token
usb_rx_data_timeout:
    std Z+CTX_CURRENT_TOKEN, r1
    rjmp usb_handler_packet_done
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
    brne usb_rx_reject_ack
    tst r2
    breq usb_rx_reject_ack
usb_rx_accept_ack:
    mov r2, r1
    ldi r19, USB_PID_NAK
    std Z+CTX_TX_LENGTH, r19
    /* SET_ADDRESS becomes effective only after ACK of status DATA1. */
    ldd r17, Z+CTX_NEW_DEVICE_ADDRESS
    std Z+CTX_DEVICE_ADDRESS, r17
    mov r8, r10
    rjmp usb_handler_packet_done
usb_rx_reject_ack:
    rjmp usb_rx_ignore_packet
usb_rx_handle_data:
    ldd r18, Z+CTX_CURRENT_TOKEN
    cpi r18, USB_PID_SETUP
    breq usb_rx_setup_data
/* OUT/rejected packets consume authorization now. Accepted SETUP clears it
 * in a useful two-cycle TX-EOP slot, saving two ACK turnaround cycles. */
    std Z+CTX_CURRENT_TOKEN, r1
    cpi r18, USB_PID_OUT
    brne usb_handler_packet_done
    cpi r23, USB_RX_PACKET_OVERHEAD
    brlo usb_handler_packet_done
/* Protocol STALL persists for both directions until the next SETUP. */
    ldd r19, Z+CTX_TX_LENGTH
    cpi r19, USB_PID_STALL
    breq usb_tx_send_count_handshake
/* OUT is status only for an accepted control read. A write's required IN
 * status ACK must never be replaced by an unrelated OUT transaction. */
    sbrs r11, 7
    rjmp usb_rx_protocol_stall
/* Status uses DATA1. ACK an old toggle without accepting it again. */
    cpi r16, USB_PID_DATA1
    brne usb_tx_send_ack
    /* USB8.5.3.1 permits any payload length for a read status inquiry. */
/* A valid OUT status also confirms the final IN when its ACK was lost. */
    ldi r19, USB_PID_NAK
    std Z+CTX_TX_LENGTH, r19
    ldi r19, USB_NO_MESSAGE
    std Z+CTX_MSG_LENGTH, r19
    rjmp usb_tx_send_ack
usb_rx_protocol_stall:
/* A protocol error terminates the write without allowing STALL's handshake
 * marker to release a queued erase, page commit or application handoff. */
    mov r3, r1
    ldi r19, USB_PID_STALL
    std Z+CTX_TX_LENGTH, r19
    ldi r20, USB_NO_MESSAGE
    std Z+CTX_MSG_LENGTH, r20
    rjmp usb_tx_send_count_handshake
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
usb_rx_setup_reject:
    std Z+CTX_CURRENT_TOKEN, r1
    rjmp usb_handler_packet_done
usb_rx_setup_data:
    cpi r16, USB_PID_DATA0
    brne usb_rx_setup_reject
    cpi r23, (USB_SETUP_BYTES + USB_RX_PACKET_OVERHEAD)
    brne usb_rx_setup_reject
/* A new SETUP always replaces the old one, even if RX_LENGTH was nonzero.
 * Shadow parameters in PHY-preserved registers before ACK. Ignored packets
 * may overwrite raw RX bytes, but can never change the accepted request. */
    ldd r12, Z+CTX_SETUP_VALUE_LOW
    ldd r13, Z+CTX_SETUP_VALUE_HIGH
    ldd r14, Z+CTX_SETUP_INDEX_LOW
    ldd r15, Z+CTX_SETUP_INDEX_HIGH
    ldd r6, Z+CTX_SETUP_LENGTH_LOW
    ldd r7, Z+CTX_SETUP_LENGTH_HIGH
    std Z+CTX_RX_LENGTH, r23
    std Z+CTX_RX_TOKEN, r18
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
    /* Consume the token during the required four-cycle TX-EOP alignment.
     * Z still holds the context base; STD costs the same two cycles as RJMP. */
    std Z+CTX_CURRENT_TOKEN, r1
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
usb_tx_bus_released:
/* A missing ACK ends this transaction after16..18bit times, while the
 * immutable TX packet remains available for a later IN retry. Keep the
 * timer inside the PHY so foreground SPM/RUN cannot overlap a legal ACK. */
    tst r2
    breq usb_return_context
    ldi r28, USB_ACK_WAIT_COUNT
usb_tx_wait_ack_sop:
    sbic _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp usb_rx_wait_for_j
    dec r28
    brne usb_tx_wait_ack_sop
    mov r2, r1
usb_return_context:
    movw r28, r30
usb_return_polynomial:
    ldi r21, HIGH8(CRC16_POLYNOMIAL)
usb_handler_return:
    ret
