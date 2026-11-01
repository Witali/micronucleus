/* ACK-only physical reader and qualified framing publication.
 * Entry: PIDbit0 is proved zero, R18=0x20, Y points at the RX buffer,
 * and R16 is replaced with the known current J line below. No ACK-owned
 * state changes before numeric PID, bounded tail and EOP qualification.
 *
 * Each middle cell reads at offsets 0 and 2 and compares the preceding cell's
 * SECOND observation with this cell's FIRST. A permitted 210 ns erasure cannot
 * span their 8/9-clock separation. Three register roles rotate, so outside-pin
 * noise is masked from the XOR without a MOV or an expected-line register.
 * The six-cell loop is ACK-specific: eleven clocks per taken cell, ten for
 * its final fallthrough. It is not a general DATA sampling schedule.
 */
#if PCIF2 != USB_PLUS_BIT
#error ACK delay-slot mask requires PCIF2 to match the USB D+ bit
#endif
usb_rx_ack_entry:
    ldi r16, (1 << USB_MINUS_BIT)
usb_rx_ack_loop_0:
    in r17, _SFR_IO_ADDR(PIND)
    eor r16, r17
    in r19, _SFR_IO_ADDR(PIND)
    or r17, r19
    andi r17, USB_LINE_MASK
    breq usb_rx_ack_loop_bad
    andi r16, USB_LINE_MASK
    subi r16, 1
    ror r18
    rjmp usb_rx_ack_loop_1
usb_rx_ack_loop_bad:
    rjmp usb_rx_ignore_packet
usb_rx_ack_loop_1:
    in r16, _SFR_IO_ADDR(PIND)
    eor r19, r16
    in r17, _SFR_IO_ADDR(PIND)
    or r16, r17
    andi r16, USB_LINE_MASK
    breq usb_rx_ack_loop_bad
    andi r19, USB_LINE_MASK
    subi r19, 1
    ror r18
    rjmp usb_rx_ack_loop_2
usb_rx_ack_loop_2:
    in r19, _SFR_IO_ADDR(PIND)
    eor r17, r19
    in r16, _SFR_IO_ADDR(PIND)
    or r19, r16
    andi r19, USB_LINE_MASK
    breq usb_rx_ack_loop_bad
    andi r17, USB_LINE_MASK
    subi r17, 1
    ror r18
    brcc usb_rx_ack_loop_0
/* Bit7 of a numeric ACK is one. Keep its sampled line and defer its final
 * ROR until EOP, funding the first tail poll six clocks after this read. */
usb_rx_ack_bit7:
    in r17, _SFR_IO_ADDR(PIND)
    ldi r23, 1
    in r19, _SFR_IO_ADDR(PIND)
    or r17, r19
    andi r17, USB_LINE_MASK
    breq usb_rx_ack_loop_bad
usb_rx_ack_dense_loop:
    /* A legal opposite interval can shrink to 2.746 clocks between SE1
     * crossover observations. Two-clock polls cannot miss that real zero.
     * The shared jump reaches full captures at low+3/+5/+7. Their four-clock
     * span excludes 210 ns excursions; the last capture fits a 670 ns EOP.
     * Starting at bit7+6, 23 polls cover the latest legal EOP at +49.94.
     * The next seven-one ending cannot arrive before the bounded timeout. */
    .rept 23
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp usb_rx_ack_dense_qualify
    .endr
    rjmp usb_rx_ignore_packet
usb_rx_ack_dense_qualify:
    in r16, _SFR_IO_ADDR(PIND)
    /* Bit7's fused nonzero line must be K. T preserves this check while
     * OR/ANDI classify EOP; no empty delay slot or extra comparison is needed. */
    bst r17, USB_MINUS_BIT
    in r19, _SFR_IO_ADDR(PIND)
    /* K's D+ bit is the PCIF2 W1C mask. This useful one-cycle work clears
     * the completed EOP edge without moving the final full-port capture. */
    out _SFR_IO_ADDR(PCIFR), r17
    in r21, _SFR_IO_ADDR(PIND)
    or r16, r19
    or r16, r21
    andi r16, USB_LINE_MASK
    brne usb_rx_ack_dense_bad
    brts usb_rx_ack_dense_bad
    /* Six middle bits are retained at bits 2..7. With PIDbit0 proved zero and
     * the final one proved by the K check, 0xa4 uniquely identifies the ACK PID.
     * Publish that verified constant instead of an extra SEC/ROR pair. */
    cpi r18, 0xa4
    brne usb_rx_ack_dense_bad
    ldi r18, USB_PID_ACK
    st Y+, r18
    in r21, _SFR_IO_ADDR(PIND)
usb_rx_ack_framing_valid:
    /* Complete PID/count are published; the shared ACK handler still
     * requires live eligibility and recovery J before address/SPM effects. */
    rjmp usb_rx_check_ack
usb_rx_ack_dense_bad:
    rjmp usb_rx_ignore_packet
