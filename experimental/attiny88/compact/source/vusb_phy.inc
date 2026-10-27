/* Software USB Low-Speed PHY: synchronization, NRZI, stuffing and handshakes.
 * In: RESET-owned stack, interrupts disabled, initialized USB SRAM context.
 * Requires Y=USB_CONTEXT_BASE at external entry. Preserves R0..R15, R24:R25 and X;
 * clobbers R16..R23, Y, Z and SREG. Every external return restores
 * Y=USB_CONTEXT_BASE and R21=HIGH8(CRC16_POLYNOMIAL).
 * RX/TX sample and output instants are cycle contracts, not ordinary delays.
 * Keep all timing changes tied to emitted-opcode audits and hardware caveats.
 */
USB_handler:
/* Both external callers preserve Y=USB_CONTEXT_BASE. MOVW also keeps YL=0
 * for the J-wait counter; INC defines the flags formerly written by EOR. */
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
/* Every external caller and chained RX path preserves YH=1. Handshake
 * TX uses YH=0 but returns through the context restore, never into chained RX.
 * RX stays within 0x0115..0x0122 even on partial packets/overflow. Reuse the
 * polynomial load as delay work: LDI + RCALL + LDI + RET = 9 cycles, 4 bytes
 * at this site. This early R21 value is dead before RX initializes its counter.
 * RCALL needs two temporary stack bytes, as in the prior fixed-base version. */
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
/* Z is already the context base. Two LDIs plus RCALL/LDI/RET take the
 * same ten cycles as the former Z setup, jump and PUSH/POP delay. R21's
 * temporary polynomial value is dead before the RX counter initialization.
 * This call uses two stack bytes, matching the existing found-K delay peak. */
    ldi r18, 0x00
    ldi r20, USB_RX_INITIAL_STUFF_MASK
    rcall usb_return_polynomial
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    bst r16, USB_MINUS_BIT
    bld r18, 7
/* Foreground is paused and RX writes cannot touch RX_LENGTH. Snapshot
 * it in decoder-free R19: this two-cycle LDD replaces the alignment jump,
 * and both DATA and IN reuse it instead of loading the same byte later. */
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
    eor r16, r16
    rjmp usb_rx_store_token
usb_rx_end_packet:
    subi r23, USB_RX_BUFFER_BYTES
    neg r23
/* YL begins at 22 and stays within 22..34; decoded count is 0..11.
 * SUB cannot borrow into YH=1. Its flags are dead before the next PID CPI. */
    sub r28, r23
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
    ldd r16, Y+USB_PACKET_PID_OFFSET
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
/* PCIFR is bit-addressable. Twelve five-cycle idle iterations keep the old
 * ten six-cycle iterations' 59-cycle timeout; a seen flag exits one cycle
 * earlier. R17 is dead before the next receive sample overwrites it. */
    sbic _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp usb_rx_store_token
    dec r28
    brbc SREG_Z, usb_rx_wait_for_data
usb_rx_store_token:
    std Z+CTX_CURRENT_TOKEN, r16
usb_handler_packet_done:
/* The old POP r19 is gone; r23 does not need restoration after RX. */
/* A direct flag test advances the chain by one cycle. YL is a bounded
 * receive pointer/count here; a legal EOP has J well before its wrap. */
    sbic _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp usb_rx_wait_for_j
    rjmp usb_return_context
/* Publish nonempty DATA to the EP0 parser and choose ACK/NAK. Incoming CRC16
 * validation is intentionally omitted under docs/USB_PROTOCOL.md's accepted
 * size/timing exception; outgoing CRC16 remains independently checked.
 */
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
    ldi r16, USB_PID_NAK
    ldd r19, Z+CTX_TX_LENGTH
    sbrc r19, USB_HANDSHAKE_FLAG_BIT
    rjmp usb_tx_send_count_handshake
    std Z+CTX_TX_LENGTH, r16
/* RX and every chained receive retain YH=HIGH8(USB_CONTEXT_BASE).
 * The bounded RX pointer cannot cross a page, so only YL needs changing. */
    ldi r28, LOW8(USB_CONTEXT_BASE + CTX_TX_PID)
    rjmp usb_tx_acquire_bus
usb_tx_stuff_regular_bit:
    eor r16, r21
/* This context byte is cleared at RESET and never written afterwards.
 * One two-cycle LDD performs the old one-cycle LDI plus alignment NOP. */
    ldd r17, Z+CTX_INPUT_BUFFER_OFFSET
    rjmp usb_tx_stuff_regular_delay
usb_tx_stuff_regular_delay:
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
/* Drive the bus and emit SYNC, PID/data and CRC with NRZI/bit stuffing.
 * Y points to either the SRAM packet or the register-file handshake byte.
 */
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
    ldd r17, Z+CTX_NEW_DEVICE_ADDRESS
/* Two cycles in one word; Z flag still means (Y-22)==0. */
    sbiw r28, USB_HANDSHAKE_END_POINTER
    out _SFR_IO_ADDR(PORTD), r16
    brbs SREG_Z, usb_tx_finish_eop
    std Z+CTX_DEVICE_ADDRESS, r17
usb_tx_finish_eop:
    ori r16, (1 << USB_MINUS_BIT)
    ldi r21, USB_EOP_DELAY_LOOPS
usb_tx_eop_delay:
    dec r21
    brbc SREG_Z, usb_tx_eop_delay
    out _SFR_IO_ADDR(PORTD), r16
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
#if LED_MODE == NONE
/* RESET clears DDRD. In the no-LED bootloader, only the USB bits are ever
 * enabled; atomic release therefore writes zero. The existing permanent
 * zero byte replaces IN/ANDI in the same two cycles, without an extra slot.
 * LED builds retain the read/mask because their non-USB DDR bit is live. */
    ldd r17, Z+CTX_INPUT_BUFFER_OFFSET
#else
    in r17, _SFR_IO_ADDR(DDRD)
    andi r17, USB_LINES_CLEAR_MASK
#endif
/* J already has D+ low. After atomic DDR release, clear only the D-
 * pull-up latch with CBI; other PORT bits are preserved. A third two-cycle
 * delay replaces the removed MOV/ANDI work, keeping driven J at 11 cycles.
 * CBI takes one cycle longer than OUT; the shorter MOVW return offsets it. */
    rjmp .+0
    rjmp .+0
    rjmp .+0
    out _SFR_IO_ADDR(DDRD), r17
    cbi _SFR_IO_ADDR(PORTD), USB_MINUS_BIT
/* EOP J has completed. Legal next SOP is at least two bit times
 * after J begins, so return before that window instead of rechecking
 * the pin-change flag here; cooperative foreground polling follows. */
/* Every external PHY return restores foreground context and polynomial.
 * The internal nine-cycle RX initializer enters at the polynomial load below. */
usb_return_context:
/* Z remains the context base throughout RX/TX, including no-K timeout. */
    movw r28, r30
usb_return_polynomial:
    ldi r21, HIGH8(CRC16_POLYNOMIAL)
usb_handler_return:
    ret
