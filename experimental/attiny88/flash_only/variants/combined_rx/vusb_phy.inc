USB_handler:
    /* This cooperative handler is not reentrant. GPIOR2 is private to its
     * caller's live request byte; chained packets do not reenter here. */
    out _SFR_IO_ADDR(GPIOR2), r24
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
    ldi r18, 0x00
    ldi r20, USB_RX_INITIAL_STUFF_MASK
    /* Authorization cannot change while PHY owns the receive. Use the
     * existing eight-cycle delay to preload it before timing-critical RX. */
    ldd r24, Z+CTX_CURRENT_TOKEN
    rjmp .+0
    rjmp .+0
    nop
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    bst r16, USB_MINUS_BIT
    bld r18, 7
    ldd r19, Z+CTX_TX_LENGTH
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
    rjmp usb_rx_store_decoded_byte
usb_rx_reject_stuff:
    rjmp usb_rx_ignore_packet
usb_rx_confirm_raw_byte_eop:
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
usb_rx_store_byte:
    /* This byte boundary keeps its original data observation while the
     * regular pair samples run one clock earlier. */
    eor r20, r18
usb_rx_store_decoded_byte:
    /* Bit7 stuffing clears history bit7; odd5 keeps only its last two bits.
     * Both therefore prove that this tail's next history test cannot stuff.
     * CPI plus taken BRCS has the same three clocks as the removed NOP/RJMP. */
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    breq usb_rx_confirm_raw_byte_eop
    st Y+, r20
    eor r17, r16
    /* No correction for the new byte exists yet. Clearing the old byte
     * replaces ANDI plus two shifts; RJMP preserves the next sample. */
    eor r20, r20
    subi r17, 0x01
    ror r18
    cpi r18, USB_STUFF_HISTORY_THRESHOLD
    /* A six-one history falls through the stuffer. The normal two-cycle
     * branch replaces the old one-cycle branch plus first-pair NOP. */
    brbs SREG_C, usb_rx_sample_odd_bit
usb_rx_unstuff_even_bit:
    /* Use the dead opposite register to observe the mandatory symbol two
     * cycles earlier. The normal continuation keeps every later sample. */
    in r17, _SFR_IO_ADDR(PIND)
    andi r17, USB_LINE_MASK
    brbs SREG_Z, usb_rx_dribble_even_end
    /* Balance the skipped normal-odd EOP check after probing EOF early.
     * The new-byte caller falls through one cycle earlier and needs this
     * same cleanup cycle to keep its following data sample unchanged. */
    andi r20, USB_RX_LOW_BITS_MASK
    cp r16, r17
    breq usb_rx_reject_stuff_late
    mov r16, r17
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    subi r21, LOW8(-1)
    /* Supported PIDs cannot stuff in their first byte; later bytes start
     * with no correction. Thus ORI40,LSR,LSR is10 on supported traffic.
     * Invalid first-byte seeds are covered by the PID-admission tests.
     * The two saved cycles fund the shared odd sample. */
    ldi r20, 0x10
    rjmp usb_rx_sample_odd_bit
usb_rx_sample_even_bit:
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
/* A full-byte EOP starts here; receiver-observed SE0 can be only670ns. */
    brbs SREG_Z, usb_rx_normal_even_eop
    eor r17, r16
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
    brbs SREG_Z, usb_rx_normal_odd_eop
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
/* Initial safety probe: two normal partial-EOP observations must span
 * at least four clocks. Recovery/short-EOP timing is measured separately. */
usb_rx_normal_even_eop:
usb_rx_normal_odd_eop:
    /* Both producers preserve R17 as their phase marker and use the same
     * opposite-register confirmation exactly four clocks after first SE0. */
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    brne usb_rx_reject_stuff_late
usb_rx_eop_jump_late:
    rjmp usb_rx_end_packet
usb_rx_dribble_even_end:
    /* Two SE0 samples four cycles apart exclude a <=210ns crossover.
     * The first sample moved earlier, so670ns receiver EOP still fits.
     * Its opposite register already has the required zero phase marker. */
    in r17, _SFR_IO_ADDR(PIND)
    andi r17, USB_LINE_MASK
    brne usb_rx_reject_stuff_late
    /* The qualified EOP interrupts a six-one run. Encode that proof in
     * the existing FF framing class; the committed byte count still
     * comes from Y, so this does not manufacture another packet byte. */
    ldi r22, LOW8(USB_CONTEXT_BASE + CTX_RX_BUFFER + USB_RX_PAIR_COUNTER_INCREMENT - 1)
    sub r22, r28
    rjmp usb_rx_end_packet
usb_rx_reject_stuff_late:
    rjmp usb_rx_ignore_packet
usb_rx_dribble_odd_end:
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    brne usb_rx_reject_stuff_late
    subi r22, LOW8(-USB_RX_PAIR_COUNTER_INCREMENT)
    rjmp usb_rx_end_packet
usb_rx_unstuff_odd_bit:
    /* The first observation qualifies EOF. A distinct normal-phase sample
     * validates the mandatory transition even at permitted source jitter. */
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    brbs SREG_Z, usb_rx_dribble_odd_end
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    /* EOF may start between the early and normal-phase observations.
     * Reuse the four-cycle SE0 qualification before any cursor advance. */
    brbs SREG_Z, usb_rx_dribble_odd_end
    cp r17, r16
    breq usb_rx_reject_stuff_late
    mov r17, r16
    subi r22, LOW8(-USB_RX_PAIR_COUNTER_INCREMENT)
    brbs SREG_C, usb_rx_unstuff_odd_next_even
    /* Carry clear selects odd position5. No history mutation or correction
     * is needed: only bits6/7 remain, and both stuffing tests are bypassed.
     * Preserve an initial-PID seed in R20 rather than assuming it is zero. */
    subi r23, 1
    in r16, _SFR_IO_ADDR(PIND)
    brbs SREG_C, usb_rx_odd_overflow_local
    andi r16, USB_LINE_MASK
    eor r17, r16
    /* The old +1 stuffer fraction and -1 bit6 adjustment cancel. */
    tst r21
    brbc SREG_N, usb_rx_odd5_shift_bit6
    subi r21, LOW8(-USB_RX_LEAP_PERIOD)
    nop
usb_rx_odd5_shift_bit6:
    subi r17, 1
    ror r18
    rjmp .+0
    nop
    in r17, _SFR_IO_ADDR(PIND)
    andi r17, USB_LINE_MASK
    eor r16, r17
    subi r16, 1
    ror r18
    eor r20, r18
    /* Preserve the decoded byte before retaining only the two bits after
     * this stuffed symbol in history for the following byte. */
    andi r18, 0xc0
    rjmp usb_rx_store_decoded_byte
usb_rx_odd_overflow_local:
    rjmp usb_rx_overflow
usb_rx_unstuff_odd_next_even:
    /* This is the first stuff in this byte at position1 or3: R20=0.
     * Retire the correction after the next-even sample, preserving its
     * phase while funding a separate normal-sample EOF branch. */
    andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
    in r16, _SFR_IO_ADDR(PIND)
    andi r16, USB_LINE_MASK
    brbs SREG_Z, usb_rx_eop_jump_late
    eor r17, r16
    subi r17, 1
    ror r18
    ldi r20, 0x08
    subi r21, LOW8(-1)
    rjmp usb_rx_sample_odd_bit
usb_rx_overflow:
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
usb_rx_ignore_packet:
    mov r2, r1
    eor r16, r16
    rjmp usb_rx_store_token
/* Residual85/170/255 means2/4/6 decoded bits after the last committed
 * byte. R17=SE0 identifies an odd position, before that bit was decoded. */
usb_rx_check_dribble:
    /* Reachable residues are55/AA/FF; FF proves a six-one ending. */
    brbs SREG_C, usb_rx_framing_valid
    ldi r20, 0xc0
    brbc SREG_N, usb_rx_dribble_mask_ready
    ldi r20, 0xf0
usb_rx_dribble_mask_ready:
    tst r17
    brne usb_rx_dribble_compare
    asr r20
usb_rx_dribble_compare:
    cp r18, r20
    brsh usb_rx_framing_valid
    rjmp usb_rx_ignore_packet
usb_rx_dribble_one:
    tst r18
    brmi usb_rx_framing_valid
    rjmp usb_rx_ignore_packet
usb_rx_ack_candidate:
    cpi r16, USB_PID_ACK
    brne usb_rx_reject_ack
usb_rx_check_ack:
    cpi r23, 1
    brne usb_rx_reject_ack
    tst r2
    breq usb_rx_reject_ack
    andi r21, USB_LINE_MASK
    cpi r21, (1 << USB_MINUS_BIT)
    breq usb_rx_accept_ack
usb_rx_secondary_j:
    /* An eligible ACK without captured J uses bounded live observations
     * before it may release the pending packet or commit any state. */
    ldi r21, 3
usb_rx_secondary_wait_j:
    in r20, _SFR_IO_ADDR(PIND)
    andi r20, USB_LINE_MASK
    cpi r20, (1 << USB_MINUS_BIT)
    breq usb_rx_accept_ack
usb_rx_secondary_not_j:
    dec r21
    brne usb_rx_secondary_wait_j
usb_rx_reject_ack:
    rjmp usb_rx_ignore_packet
usb_rx_accept_ack:
    mov r2, r1
    ldi r19, USB_PID_NAK
    std Z+CTX_TX_LENGTH, r19
    /* No ACK state or hardware-buffer write occurs before complete
     * framing, eligibility and observed recovery J have all passed. */
    sbrc r3, USB_CURSOR_WRITE_PENDING_BIT
    rjmp flash_buffer_ack_write4
    ldd r17, Z+CTX_NEW_DEVICE_ADDRESS
    std Z+CTX_DEVICE_ADDRESS, r17
    mov r8, r10
    rjmp usb_handler_packet_done
usb_rx_eop_not_j:
    dec r21
    brne usb_rx_wait_eop_j
    rjmp usb_rx_ignore_packet
usb_rx_end_packet:
    mov r23, r28
    subi r23, LOW8(USB_CONTEXT_BASE + CTX_RX_BUFFER)
    /* Four also supplies the PCIF2 W1C mask. Framing captures early J for
     * eligible ACK; token/DATA later reload their bounded live-J count. */
    ldi r21, (1 << PCIF2)
    out _SFR_IO_ADDR(PCIFR), r21
    ldd r16, Z+(CTX_RX_BUFFER + USB_PACKET_PID_OFFSET)
    /* Keep the established two-clock even-PID versus one-clock odd-PID
     * entry credit. The common classifier later replaces the old DATA jump. */
    brbs 6, usb_rx_check_framing
usb_rx_check_framing:
    /* Pair phase and a non-SE0 final odd sample must finish a full byte. */
    add r22, r23
    subi r22, USB_RX_PAIR_COUNTER_INCREMENT
    /* R21's fractional clock state is dead after EOP. Capture recovery
     * while framing is classified, before the next minimum-gap SYNC.
     * Only a validated eligible ACK can consume this earlier J evidence. */
    in r21, _SFR_IO_ADDR(PIND)
    brne usb_rx_check_dribble
    tst r17
    breq usb_rx_dribble_one
usb_rx_framing_valid:
    /* Initial T is the received PID bit0 complement. Only even PIDs can
     * be an ACK; token and DATA classes share live-J recovery below. */
    brbs 6, usb_rx_ack_candidate
    /* Both token and DATA packets must see live recovery J. Keep a real
     * bounded count here: R21 held an earlier PIN sample for eligible ACK. */
    ldi r21, 4
usb_rx_wait_eop_j:
    in r20, _SFR_IO_ADDR(PIND)
    andi r20, USB_LINE_MASK
    cpi r20, (1 << USB_MINUS_BIT)
    brne usb_rx_eop_not_j
usb_rx_data_live_j:
usb_rx_recovered_j:
    /* The early broad DATA class is followed by exact PID validation in
     * its context owner before ACK, STALL, publication or cursor effects. */
    sbrc r16, 1
    rjmp usb_rx_handle_data
    mov r2, r1
    /* Tokens contain PID and sixteen address/endpoint/CRC bits. */
    /* Treat length, address/endpoint and CRC5 as one virtual compare.
     * CPC preserves a cleared Z, so no later field can cancel a mismatch. */
    cpi r23, 3
    ldd r18, Z+CTX_DEVICE_ADDRESS
    ldd r17, Z+(CTX_RX_BUFFER + USB_PACKET_ADDRESS_OFFSET)
    cpc r17, r18
    /* Cache endpoint-zero CRC5 per address, without a lookup table.
     * The full-byte comparison also rejects endpoint bits 1..3. */
    ldd r17, Z+(CTX_RX_BUFFER + (USB_PACKET_ADDRESS_OFFSET + 1))
    cpc r17, r8
    brne .Lmask_ignore_late
    cpi r16, USB_PID_IN
    brne .Lrx_not_in
usb_rx_handle_in:
    sbrc r19, USB_HANDSHAKE_FLAG_BIT
    rjmp usb_tx_send_count_handshake
    mov r2, r19       /* a DATA packet was actually transmitted */
    /* RX and cached DATA stay on the context page, so Y high is already
     * correct. Handshake TX's high zero is restored from Z before RX. */
    ldi r28, LOW8(USB_CONTEXT_BASE + CTX_TX_PID)
    rjmp usb_tx_acquire_bus
.Lmask_ignore_late:
    rjmp usb_rx_ignore_packet
.Lrx_not_in:
    cpi r16, USB_PID_SETUP
    brbs SREG_Z, usb_rx_handle_setup_or_out
    cpi r16, USB_PID_OUT
    brbc SREG_Z, .Lmask_ignore_late
usb_rx_handle_setup_or_out:
    ldi r28, USB_NEXT_DATA_WAIT_COUNT
    /* Six-one EOP helpers reach the parser two clocks earlier than the
     * ordinary route. Only that saturated FF class needs this credit.
     * PHY owns the wait until publishing this token or clearing timeout,
     * so stale SRAM authorization is never consumed in either branch. */
    cpi r22, 0xff
    brne usb_rx_six_one_credit_done
    std Z+CTX_CURRENT_TOKEN, r1
    nop
usb_rx_six_one_credit_done:
    inc r22
    andi r22, 2
usb_rx_phase_delay_one:
    breq usb_rx_phase_delay_two
usb_rx_phase_delay_two:
    breq usb_rx_wait_for_data
    dec r28
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
usb_tx_send_count_handshake:
    mov r20, r19
    rjmp usb_tx_prepare_handshake
usb_rx_setup_reject:
    /* Authorized SETUP/OUT already closed R2 at its valid token. An
     * unpaired or rejected DATA must also close an earlier IN window. */
    mov r2, r1
    std Z+CTX_CURRENT_TOKEN, r1
    rjmp usb_handler_packet_done
usb_rx_setup_data:
    cpi r16, USB_PID_DATA0
    brne usb_rx_setup_reject
    cpi r23, (USB_SETUP_BYTES + USB_RX_PACKET_OVERHEAD)
    brne usb_rx_setup_reject
/* A new SETUP replaces the old transfer. Retire its reply now, then shadow
 * all six accepted parameters after transmitting ACK and before any later
 * receive or foreground code can overwrite the protected RX bytes. */
    /* Only validated DATA0/SETUP installs this unique pending state.
     * NAK retires the previous reply before another IN can see it. */
    ldi r19, USB_PID_NAK
    std Z+CTX_TX_LENGTH, r19
    mov r3, r23
    ldi r20, USB_PID_ACK
    rjmp usb_tx_prepare_handshake
usb_rx_handle_data:
    /* Only validated OUT is negative in the private token context. */
    tst r24
    brmi usb_rx_out_data
    cpi r24, USB_PID_SETUP
    breq usb_rx_setup_data
    rjmp usb_rx_setup_reject
usb_rx_out_data:
    /* Validate each legal DATA toggle before sharing the status guards. */
    cpi r16, USB_PID_DATA1
    breq usb_rx_out_status
    cpi r16, USB_PID_DATA0
    brne usb_rx_setup_reject
usb_rx_out_status:
    cpi r23, USB_RX_PACKET_OVERHEAD
    brlo usb_rx_setup_reject
/* R19 was loaded from TX_LENGTH during fixed-time RX and remains live.
 * Foreground code cannot run between that load and this status check. */
    cpi r19, USB_PID_STALL
    breq usb_tx_send_count_handshake
/* OUT is status only for an accepted control read. A write's required IN
 * status ACK must never be replaced by an unrelated OUT transaction. */
    sbrc r11, 7
    rjmp usb_rx_out_read_status
usb_rx_protocol_stall:
    /* PHY owns the response until post-handshake retirement. Negative R3
     * records the validated OUT; literal STALL distinguishes it from ACK. */
    mov r3, r24
    ldi r20, USB_PID_STALL
    rjmp usb_tx_prepare_handshake
usb_rx_out_read_status:
    /* DATA0 is acknowledged without accepting the completed status again.
     * DATA1 alone installs the validated OUT marker for post-ACK retirement.
     * USB8.5.3.1 permits any payload length for a read status inquiry. */
    sbrc r16, 3
    mov r3, r24
usb_tx_send_ack:
    ldi r20, USB_PID_ACK
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
    rjmp usb_tx_begin_se0
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
usb_tx_begin_se0:
    out _SFR_IO_ADDR(PORTD), r16
    /* SE0 remains in USB Low-Speed timing window for DATA and handshake. */
    rjmp .+0
usb_tx_finish_eop:
    ori r16, (1 << USB_MINUS_BIT)
    /* TX kept R21 at the line mask, already equal to the six-count delay.
     * Reusing it removes LDI and makes SE0 21 clocks (1.3125us at 16 MHz),
     * closer to two nominal low-speed bits and within USB Table 7-10. */
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
    breq usb_tx_finish_handshake
    ldi r28, USB_ACK_WAIT_COUNT
usb_tx_wait_ack_sop:
    sbic _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp usb_rx_wait_for_j
    dec r28
    brne usb_tx_wait_ack_sop
    mov r2, r1
usb_return_context:
    in r24, _SFR_IO_ADDR(GPIOR2)
    movw r28, r30
usb_return_polynomial:
    ldi r21, HIGH8(CRC16_POLYNOMIAL)
usb_handler_return:
    ret

usb_tx_finish_handshake:
    tst r3
    brmi usb_tx_commit_read_status
    /* TX has finished and no receive/poll has occurred. The six accepted
     * SETUP parameters are still in RX SRAM; publish their register shadow
     * before returning to any caller or allowing another packet receive.
     * Only the accepted SETUP marker owns bit3 among deferred commands. */
    sbrs r3, USB_SETUP_PENDING_BIT
    rjmp usb_return_context
    ldd r12, Z+CTX_SETUP_VALUE_LOW
    ldd r13, Z+CTX_SETUP_VALUE_HIGH
    ldd r14, Z+CTX_SETUP_INDEX_LOW
    ldd r15, Z+CTX_SETUP_INDEX_HIGH
    ldd r6, Z+CTX_SETUP_LENGTH_LOW
    ldd r7, Z+CTX_SETUP_LENGTH_HIGH
    rjmp usb_return_context

usb_tx_commit_read_status:
    /* No receive or foreground work can precede this retirement. Both
     * accepted read status and protocol errors own negative R3; only STALL
     * has bit2 among the transmitted ACK/NAK/STALL handshake PIDs. */
    mov r3, r1
    sbrc r20, 2
    rjmp usb_tx_commit_out_state
    sbrc r11, 6
    movw r4, r14
    ldi r20, USB_PID_NAK
usb_tx_commit_out_state:
    std Z+CTX_TX_LENGTH, r20
    /* R24 still holds the validated OUT token, a negative done marker. */
    std Z+CTX_MSG_LENGTH, r24
    rjmp usb_return_context

flash_buffer_ack_write4:
    /* Acknowledged WRITE4 must complete before accepting the next SETUP.
     * Its empty status has no live payload CRC: R0/R1 can stage the words,
     * and R1 is restored to zero before returning to the foreground. */
    mov r3, r1
    movw r22, r30
    movw r30, r4
    /* This loads only hardware-buffer slots. The deferred erase/page-write
     * path retains the Flash boot-region guard before modifying Flash. */
    movw r0, r12
    out _SFR_IO_ADDR(SPMCSR), r29
    spm
    adiw r30, 2
    movw r0, r14
    out _SFR_IO_ADDR(SPMCSR), r29
    spm
    eor r1, r1
    adiw r30, 2
    movw r4, r30
    andi r30, FLASH_PAGE_OFFSET_MASK
    brne .Lack_write4_restore
    ldi r18, SPM_PAGE_WRITE
    mov r3, r18
.Lack_write4_restore:
    movw r30, r22
    rjmp usb_handler_packet_done
