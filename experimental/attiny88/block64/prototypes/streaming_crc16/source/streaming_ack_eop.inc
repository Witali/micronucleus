/* Opt-in publication during the fixed SE0 delay after the ACK PID bits.
 * Replace the complete LDI R21,4 / L1cc2: DEC / BRBC loop with this include.
 * The following PORTD/DDRD release instructions must remain unchanged.
 *
 * Entry: Z=0x0100, R27=0 or 1. When pending, R24=preceding token and
 * R25=complete packet count; CRC, token and free-buffer gates already
 * passed before selecting ACK. TX preserves all four registers.
 *
 * Both paths consume exactly twelve clocks, matching the replaced delay:
 *   pending:  TST1 + BREQ1 + STD2 + STD2 + CLR1 + LDI1 + NOP2 + RJMP2
 *   ordinary: TST1 + BREQ2 + LDI1 + RJMP6 + NOP2
 * R21=0 and Z/N/V/S match the old final DEC on either path. C/H remain
 * unchanged. The pending path clears R27 before the bus is released.
 *
 * Publication occurs during EOP, before the return to J; it must not be
 * described as publication after a completed ACK. This variant avoids
 * adding work to the post-TX return/re-entry path. The original timed
 * loop had no external entry; L1cc2 remains an alias for build references.
 */
L1cc2:
stream_eop_publication_check:
    tst     r27
    breq    stream_eop_publication_delay_only
stream_eop_publication_commit:
    std     Z+18, r25
    std     Z+13, r24
    clr     r27
    ldi     r21, 0
    nop
    nop
    rjmp    stream_eop_publication_done
stream_eop_publication_delay_only:
    ldi     r21, 0
    rjmp    .+0
    rjmp    .+0
    rjmp    .+0
    nop
    nop
stream_eop_publication_done:
