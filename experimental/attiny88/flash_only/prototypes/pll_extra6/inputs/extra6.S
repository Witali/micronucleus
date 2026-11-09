/* Debugging candidate; explicit safe rejects mark unfinished cold paths. */
    .text
    .org BOOT_AT
    .global bootloader_start
bootloader_start:
USB_handler:
    rjmp rx_p0_K_r1
rx_p1_J_r2_inline_0_second_zero:
    andi r19, 6
    breq rx_p1_J_r2_inline_0_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r2_inline_0_unfunded
    sec
rx_p1_J_r2_inline_0_shift_recovered_one:
    ror r18
rx_p1_J_r2_inline_0_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r2_inline_0_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r2_inline_0_second_eop:
    ret
rx_p1_J_r2_inline_0_different:
    breq rx_p1_J_r2_inline_0_first_zero
rx_p1_J_r2_inline_0_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r2_inline_0_first_zero:
    andi r19, 6
    breq rx_p1_J_r2_inline_0_first_eop
    andi r17, 6
    breq rx_p1_J_r2_inline_0_first_eop
    rjmp rx_p1_J_r2_inline_0_unfunded
rx_p1_J_r2_inline_0_first_eop:
    ret
rx_p1_J_r2_inline_0_unfunded:
    ret
rx_p0_J_r1_second_zero:
    andi r19, 6
    breq rx_p0_J_r1_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r1_unfunded
    sec
rx_p0_J_r1_shift_recovered_one:
    ror r18
rx_p0_J_r1_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r1_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r1_second_eop:
    ret
rx_p0_J_r1_different:
    breq rx_p0_J_r1_first_zero
rx_p0_J_r1_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r1_first_zero:
    andi r19, 6
    breq rx_p0_J_r1_first_eop
    andi r17, 6
    breq rx_p0_J_r1_first_eop
    rjmp rx_p0_J_r1_unfunded
rx_p0_J_r1_first_eop:
    ret
rx_p0_J_r1_unfunded:
    ret
rx_p0_J_r1:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r1_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r1_second_zero_veneer
rx_p0_J_r1_shift_one:
    asr r18
    nop
rx_p1_J_r2_inline_0:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r2_inline_0_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r2_inline_0_second_zero_veneer
rx_p1_J_r2_inline_0_shift_one:
    asr r18
    rjmp rx_p2_J_r3
rx_p1_J_r2_inline_0_second_zero_veneer:
    rjmp rx_p1_J_r2_inline_0_second_zero
rx_p0_J_r1_second_zero_veneer:
    rjmp rx_p0_J_r1_second_zero
rx_p1_J_r1_second_zero:
    andi r19, 6
    breq rx_p1_J_r1_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r1_unfunded
    sec
rx_p1_J_r1_shift_recovered_one:
    ror r18
rx_p1_J_r1_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r1_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r1_second_eop:
    ret
rx_p1_J_r1_different:
    breq rx_p1_J_r1_first_zero
rx_p1_J_r1_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r1_first_zero:
    andi r19, 6
    breq rx_p1_J_r1_first_eop
    andi r17, 6
    breq rx_p1_J_r1_first_eop
    rjmp rx_p1_J_r1_unfunded
rx_p1_J_r1_first_eop:
    ret
rx_p1_J_r1_unfunded:
    ret
rx_p1_J_r1:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r1_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r1_second_zero_veneer
rx_p1_J_r1_shift_one:
    asr r18
    rjmp rx_p2_J_r2
rx_p1_J_r1_second_zero_veneer:
    rjmp rx_p1_J_r1_second_zero
rx_p2_J_r1_second_zero:
    andi r19, 6
    breq rx_p2_J_r1_second_eop
    cpse r19, r21
    rjmp rx_p2_J_r1_unfunded
    sec
rx_p2_J_r1_shift_recovered_one:
    ror r18
rx_p2_J_r1_shift_future_zero:
    lsr r18
    nop
rx_p2_J_r1_consumed_future_symbol:
    rjmp rx_p1_K_r0
rx_p2_J_r1_second_eop:
    ret
rx_p2_J_r1_different:
    breq rx_p2_J_r1_first_zero
rx_p2_J_r1_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r1_first_zero:
    andi r19, 6
    breq rx_p2_J_r1_first_eop
    andi r17, 6
    breq rx_p2_J_r1_first_eop
    rjmp rx_p2_J_r1_unfunded
rx_p2_J_r1_first_eop:
    ret
rx_p2_J_r1_unfunded:
    ret
rx_p2_J_r1:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r1_different
    andi r17, 6
    in r19, 9
    breq rx_p2_J_r1_second_zero_veneer
rx_p2_J_r1_shift_one:
    asr r18
    rjmp rx_p0_J_r2
rx_p2_J_r1_second_zero_veneer:
    rjmp rx_p2_J_r1_second_zero
rx_p1_K_r2_inline_4_second_zero:
    andi r19, 6
    breq rx_p1_K_r2_inline_4_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r2_inline_4_unfunded
    sec
rx_p1_K_r2_inline_4_shift_recovered_one:
    ror r18
rx_p1_K_r2_inline_4_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r2_inline_4_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r2_inline_4_second_eop:
    ret
rx_p1_K_r2_inline_4_different:
    breq rx_p1_K_r2_inline_4_first_zero
rx_p1_K_r2_inline_4_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r2_inline_4_first_zero:
    andi r19, 6
    breq rx_p1_K_r2_inline_4_first_eop
    andi r17, 6
    breq rx_p1_K_r2_inline_4_first_eop
    rjmp rx_p1_K_r2_inline_4_unfunded
rx_p1_K_r2_inline_4_first_eop:
    ret
rx_p1_K_r2_inline_4_unfunded:
    ret
rx_p0_K_r1_second_zero:
    andi r19, 6
    breq rx_p0_K_r1_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r1_unfunded
    sec
rx_p0_K_r1_shift_recovered_one:
    ror r18
rx_p0_K_r1_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r1_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r1_second_eop:
    ret
rx_p0_K_r1_different:
    breq rx_p0_K_r1_first_zero
rx_p0_K_r1_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r1_first_zero:
    andi r19, 6
    breq rx_p0_K_r1_first_eop
    andi r17, 6
    breq rx_p0_K_r1_first_eop
    rjmp rx_p0_K_r1_unfunded
rx_p0_K_r1_first_eop:
    ret
rx_p0_K_r1_unfunded:
    ret
rx_p0_K_r1:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r1_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r1_second_zero_veneer
rx_p0_K_r1_shift_one:
    asr r18
    nop
rx_p1_K_r2_inline_4:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r2_inline_4_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r2_inline_4_second_zero_veneer
rx_p1_K_r2_inline_4_shift_one:
    asr r18
    rjmp rx_p2_K_r3
rx_p1_K_r2_inline_4_second_zero_veneer:
    rjmp rx_p1_K_r2_inline_4_second_zero
rx_p0_K_r1_second_zero_veneer:
    rjmp rx_p0_K_r1_second_zero
rx_p1_K_r1_second_zero:
    andi r19, 6
    breq rx_p1_K_r1_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r1_unfunded
    sec
rx_p1_K_r1_shift_recovered_one:
    ror r18
rx_p1_K_r1_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r1_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r1_second_eop:
    ret
rx_p1_K_r1_different:
    breq rx_p1_K_r1_first_zero
rx_p1_K_r1_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r1_first_zero:
    andi r19, 6
    breq rx_p1_K_r1_first_eop
    andi r17, 6
    breq rx_p1_K_r1_first_eop
    rjmp rx_p1_K_r1_unfunded
rx_p1_K_r1_first_eop:
    ret
rx_p1_K_r1_unfunded:
    ret
rx_p1_K_r1:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r1_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r1_second_zero_veneer
rx_p1_K_r1_shift_one:
    asr r18
    rjmp rx_p2_K_r2
rx_p1_K_r1_second_zero_veneer:
    rjmp rx_p1_K_r1_second_zero
rx_p2_K_r1_second_zero:
    andi r19, 6
    breq rx_p2_K_r1_second_eop
    cpse r19, r20
    rjmp rx_p2_K_r1_unfunded
    sec
rx_p2_K_r1_shift_recovered_one:
    ror r18
rx_p2_K_r1_shift_future_zero:
    lsr r18
    nop
rx_p2_K_r1_consumed_future_symbol:
    rjmp rx_p1_J_r0
rx_p2_K_r1_second_eop:
    ret
rx_p2_K_r1_different:
    breq rx_p2_K_r1_first_zero
rx_p2_K_r1_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r1_first_zero:
    andi r19, 6
    breq rx_p2_K_r1_first_eop
    andi r17, 6
    breq rx_p2_K_r1_first_eop
    rjmp rx_p2_K_r1_unfunded
rx_p2_K_r1_first_eop:
    ret
rx_p2_K_r1_unfunded:
    ret
rx_p2_K_r1:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r1_different
    andi r17, 6
    in r19, 9
    breq rx_p2_K_r1_second_zero_veneer
rx_p2_K_r1_shift_one:
    asr r18
    rjmp rx_p0_K_r2
rx_p2_K_r1_second_zero_veneer:
    rjmp rx_p2_K_r1_second_zero
rx_p1_J_r3_inline_8_second_zero:
    andi r19, 6
    breq rx_p1_J_r3_inline_8_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r3_inline_8_unfunded
    sec
rx_p1_J_r3_inline_8_shift_recovered_one:
    ror r18
rx_p1_J_r3_inline_8_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r3_inline_8_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r3_inline_8_second_eop:
    ret
rx_p1_J_r3_inline_8_different:
    breq rx_p1_J_r3_inline_8_first_zero
rx_p1_J_r3_inline_8_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r3_inline_8_first_zero:
    andi r19, 6
    breq rx_p1_J_r3_inline_8_first_eop
    andi r17, 6
    breq rx_p1_J_r3_inline_8_first_eop
    rjmp rx_p1_J_r3_inline_8_unfunded
rx_p1_J_r3_inline_8_first_eop:
    ret
rx_p1_J_r3_inline_8_unfunded:
    ret
rx_p0_J_r2_second_zero:
    andi r19, 6
    breq rx_p0_J_r2_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r2_unfunded
    sec
rx_p0_J_r2_shift_recovered_one:
    ror r18
rx_p0_J_r2_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r2_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r2_second_eop:
    ret
rx_p0_J_r2_different:
    breq rx_p0_J_r2_first_zero
rx_p0_J_r2_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r2_first_zero:
    andi r19, 6
    breq rx_p0_J_r2_first_eop
    andi r17, 6
    breq rx_p0_J_r2_first_eop
    rjmp rx_p0_J_r2_unfunded
rx_p0_J_r2_first_eop:
    ret
rx_p0_J_r2_unfunded:
    ret
rx_p0_J_r2:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r2_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r2_second_zero_veneer
rx_p0_J_r2_shift_one:
    asr r18
    nop
rx_p1_J_r3_inline_8:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r3_inline_8_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r3_inline_8_second_zero_veneer
rx_p1_J_r3_inline_8_shift_one:
    asr r18
    rjmp rx_p2_J_r4
rx_p1_J_r3_inline_8_second_zero_veneer:
    rjmp rx_p1_J_r3_inline_8_second_zero
rx_p0_J_r2_second_zero_veneer:
    rjmp rx_p0_J_r2_second_zero
rx_p1_J_r2_second_zero:
    andi r19, 6
    breq rx_p1_J_r2_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r2_unfunded
    sec
rx_p1_J_r2_shift_recovered_one:
    ror r18
rx_p1_J_r2_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r2_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r2_second_eop:
    ret
rx_p1_J_r2_different:
    breq rx_p1_J_r2_first_zero
rx_p1_J_r2_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r2_first_zero:
    andi r19, 6
    breq rx_p1_J_r2_first_eop
    andi r17, 6
    breq rx_p1_J_r2_first_eop
    rjmp rx_p1_J_r2_unfunded
rx_p1_J_r2_first_eop:
    ret
rx_p1_J_r2_unfunded:
    ret
rx_p1_J_r2:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r2_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r2_second_zero_veneer
rx_p1_J_r2_shift_one:
    asr r18
    rjmp rx_p2_J_r3
rx_p1_J_r2_second_zero_veneer:
    rjmp rx_p1_J_r2_second_zero
rx_p2_J_r2_second_zero:
    andi r19, 6
    breq rx_p2_J_r2_second_eop
    cpse r19, r21
    rjmp rx_p2_J_r2_unfunded
    sec
rx_p2_J_r2_shift_recovered_one:
    ror r18
rx_p2_J_r2_shift_future_zero:
    lsr r18
    nop
rx_p2_J_r2_consumed_future_symbol:
    rjmp rx_p1_K_r0
rx_p2_J_r2_second_eop:
    ret
rx_p2_J_r2_different:
    breq rx_p2_J_r2_first_zero
rx_p2_J_r2_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r2_first_zero:
    andi r19, 6
    breq rx_p2_J_r2_first_eop
    andi r17, 6
    breq rx_p2_J_r2_first_eop
    rjmp rx_p2_J_r2_unfunded
rx_p2_J_r2_first_eop:
    ret
rx_p2_J_r2_unfunded:
    ret
rx_p2_J_r2:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r2_different
    andi r17, 6
    in r19, 9
    breq rx_p2_J_r2_second_zero_veneer
rx_p2_J_r2_shift_one:
    asr r18
    rjmp rx_p0_J_r3
rx_p2_J_r2_second_zero_veneer:
    rjmp rx_p2_J_r2_second_zero
rx_p1_K_r3_inline_12_second_zero:
    andi r19, 6
    breq rx_p1_K_r3_inline_12_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r3_inline_12_unfunded
    sec
rx_p1_K_r3_inline_12_shift_recovered_one:
    ror r18
rx_p1_K_r3_inline_12_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r3_inline_12_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r3_inline_12_second_eop:
    ret
rx_p1_K_r3_inline_12_different:
    breq rx_p1_K_r3_inline_12_first_zero
rx_p1_K_r3_inline_12_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r3_inline_12_first_zero:
    andi r19, 6
    breq rx_p1_K_r3_inline_12_first_eop
    andi r17, 6
    breq rx_p1_K_r3_inline_12_first_eop
    rjmp rx_p1_K_r3_inline_12_unfunded
rx_p1_K_r3_inline_12_first_eop:
    ret
rx_p1_K_r3_inline_12_unfunded:
    ret
rx_p0_K_r2_second_zero:
    andi r19, 6
    breq rx_p0_K_r2_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r2_unfunded
    sec
rx_p0_K_r2_shift_recovered_one:
    ror r18
rx_p0_K_r2_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r2_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r2_second_eop:
    ret
rx_p0_K_r2_different:
    breq rx_p0_K_r2_first_zero
rx_p0_K_r2_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r2_first_zero:
    andi r19, 6
    breq rx_p0_K_r2_first_eop
    andi r17, 6
    breq rx_p0_K_r2_first_eop
    rjmp rx_p0_K_r2_unfunded
rx_p0_K_r2_first_eop:
    ret
rx_p0_K_r2_unfunded:
    ret
rx_p0_K_r2:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r2_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r2_second_zero_veneer
rx_p0_K_r2_shift_one:
    asr r18
    nop
rx_p1_K_r3_inline_12:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r3_inline_12_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r3_inline_12_second_zero_veneer
rx_p1_K_r3_inline_12_shift_one:
    asr r18
    rjmp rx_p2_K_r4
rx_p1_K_r3_inline_12_second_zero_veneer:
    rjmp rx_p1_K_r3_inline_12_second_zero
rx_p0_K_r2_second_zero_veneer:
    rjmp rx_p0_K_r2_second_zero
rx_p1_K_r2_second_zero:
    andi r19, 6
    breq rx_p1_K_r2_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r2_unfunded
    sec
rx_p1_K_r2_shift_recovered_one:
    ror r18
rx_p1_K_r2_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r2_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r2_second_eop:
    ret
rx_p1_K_r2_different:
    breq rx_p1_K_r2_first_zero
rx_p1_K_r2_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r2_first_zero:
    andi r19, 6
    breq rx_p1_K_r2_first_eop
    andi r17, 6
    breq rx_p1_K_r2_first_eop
    rjmp rx_p1_K_r2_unfunded
rx_p1_K_r2_first_eop:
    ret
rx_p1_K_r2_unfunded:
    ret
rx_p1_K_r2:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r2_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r2_second_zero_veneer
rx_p1_K_r2_shift_one:
    asr r18
    rjmp rx_p2_K_r3
rx_p1_K_r2_second_zero_veneer:
    rjmp rx_p1_K_r2_second_zero
rx_p2_K_r2_second_zero:
    andi r19, 6
    breq rx_p2_K_r2_second_eop
    cpse r19, r20
    rjmp rx_p2_K_r2_unfunded
    sec
rx_p2_K_r2_shift_recovered_one:
    ror r18
rx_p2_K_r2_shift_future_zero:
    lsr r18
    nop
rx_p2_K_r2_consumed_future_symbol:
    rjmp rx_p1_J_r0
rx_p2_K_r2_second_eop:
    ret
rx_p2_K_r2_different:
    breq rx_p2_K_r2_first_zero
rx_p2_K_r2_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r2_first_zero:
    andi r19, 6
    breq rx_p2_K_r2_first_eop
    andi r17, 6
    breq rx_p2_K_r2_first_eop
    rjmp rx_p2_K_r2_unfunded
rx_p2_K_r2_first_eop:
    ret
rx_p2_K_r2_unfunded:
    ret
rx_p2_K_r2:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r2_different
    andi r17, 6
    in r19, 9
    breq rx_p2_K_r2_second_zero_veneer
rx_p2_K_r2_shift_one:
    asr r18
    rjmp rx_p0_K_r3
rx_p2_K_r2_second_zero_veneer:
    rjmp rx_p2_K_r2_second_zero
rx_p1_J_r4_inline_16_second_zero:
    andi r19, 6
    breq rx_p1_J_r4_inline_16_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r4_inline_16_unfunded
    sec
rx_p1_J_r4_inline_16_shift_recovered_one:
    ror r18
rx_p1_J_r4_inline_16_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r4_inline_16_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r4_inline_16_second_eop:
    ret
rx_p1_J_r4_inline_16_different:
    breq rx_p1_J_r4_inline_16_first_zero
rx_p1_J_r4_inline_16_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r4_inline_16_first_zero:
    andi r19, 6
    breq rx_p1_J_r4_inline_16_first_eop
    andi r17, 6
    breq rx_p1_J_r4_inline_16_first_eop
    rjmp rx_p1_J_r4_inline_16_unfunded
rx_p1_J_r4_inline_16_first_eop:
    ret
rx_p1_J_r4_inline_16_unfunded:
    ret
rx_p0_J_r3_second_zero:
    andi r19, 6
    breq rx_p0_J_r3_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r3_unfunded
    sec
rx_p0_J_r3_shift_recovered_one:
    ror r18
rx_p0_J_r3_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r3_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r3_second_eop:
    ret
rx_p0_J_r3_different:
    breq rx_p0_J_r3_first_zero
rx_p0_J_r3_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r3_first_zero:
    andi r19, 6
    breq rx_p0_J_r3_first_eop
    andi r17, 6
    breq rx_p0_J_r3_first_eop
    rjmp rx_p0_J_r3_unfunded
rx_p0_J_r3_first_eop:
    ret
rx_p0_J_r3_unfunded:
    ret
rx_p0_J_r3:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r3_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r3_second_zero_veneer
rx_p0_J_r3_shift_one:
    asr r18
    nop
rx_p1_J_r4_inline_16:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r4_inline_16_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r4_inline_16_second_zero_veneer
rx_p1_J_r4_inline_16_shift_one:
    asr r18
    rjmp rx_p2_J_r5
rx_p1_J_r4_inline_16_second_zero_veneer:
    rjmp rx_p1_J_r4_inline_16_second_zero
rx_p0_J_r3_second_zero_veneer:
    rjmp rx_p0_J_r3_second_zero
rx_p1_J_r3_second_zero:
    andi r19, 6
    breq rx_p1_J_r3_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r3_unfunded
    sec
rx_p1_J_r3_shift_recovered_one:
    ror r18
rx_p1_J_r3_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r3_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r3_second_eop:
    ret
rx_p1_J_r3_different:
    breq rx_p1_J_r3_first_zero
rx_p1_J_r3_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r3_first_zero:
    andi r19, 6
    breq rx_p1_J_r3_first_eop
    andi r17, 6
    breq rx_p1_J_r3_first_eop
    rjmp rx_p1_J_r3_unfunded
rx_p1_J_r3_first_eop:
    ret
rx_p1_J_r3_unfunded:
    ret
rx_p1_J_r3:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r3_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r3_second_zero_veneer
rx_p1_J_r3_shift_one:
    asr r18
    rjmp rx_p2_J_r4
rx_p1_J_r3_second_zero_veneer:
    rjmp rx_p1_J_r3_second_zero
rx_p2_J_r3_second_zero:
    andi r19, 6
    breq rx_p2_J_r3_second_eop
    cpse r19, r21
    rjmp rx_p2_J_r3_unfunded
    sec
rx_p2_J_r3_shift_recovered_one:
    ror r18
rx_p2_J_r3_shift_future_zero:
    lsr r18
    nop
rx_p2_J_r3_consumed_future_symbol:
    rjmp rx_p1_K_r0
rx_p2_J_r3_second_eop:
    ret
rx_p2_J_r3_different:
    breq rx_p2_J_r3_first_zero
rx_p2_J_r3_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r3_first_zero:
    andi r19, 6
    breq rx_p2_J_r3_first_eop
    andi r17, 6
    breq rx_p2_J_r3_first_eop
    rjmp rx_p2_J_r3_unfunded
rx_p2_J_r3_first_eop:
    ret
rx_p2_J_r3_unfunded:
    ret
rx_p2_J_r3:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r3_different
    andi r17, 6
    in r19, 9
    breq rx_p2_J_r3_second_zero_veneer
rx_p2_J_r3_shift_one:
    asr r18
    rjmp rx_p0_J_r4
rx_p2_J_r3_second_zero_veneer:
    rjmp rx_p2_J_r3_second_zero
rx_p1_K_r4_inline_20_second_zero:
    andi r19, 6
    breq rx_p1_K_r4_inline_20_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r4_inline_20_unfunded
    sec
rx_p1_K_r4_inline_20_shift_recovered_one:
    ror r18
rx_p1_K_r4_inline_20_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r4_inline_20_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r4_inline_20_second_eop:
    ret
rx_p1_K_r4_inline_20_different:
    breq rx_p1_K_r4_inline_20_first_zero
rx_p1_K_r4_inline_20_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r4_inline_20_first_zero:
    andi r19, 6
    breq rx_p1_K_r4_inline_20_first_eop
    andi r17, 6
    breq rx_p1_K_r4_inline_20_first_eop
    rjmp rx_p1_K_r4_inline_20_unfunded
rx_p1_K_r4_inline_20_first_eop:
    ret
rx_p1_K_r4_inline_20_unfunded:
    ret
rx_p0_K_r3_second_zero:
    andi r19, 6
    breq rx_p0_K_r3_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r3_unfunded
    sec
rx_p0_K_r3_shift_recovered_one:
    ror r18
rx_p0_K_r3_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r3_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r3_second_eop:
    ret
rx_p0_K_r3_different:
    breq rx_p0_K_r3_first_zero
rx_p0_K_r3_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r3_first_zero:
    andi r19, 6
    breq rx_p0_K_r3_first_eop
    andi r17, 6
    breq rx_p0_K_r3_first_eop
    rjmp rx_p0_K_r3_unfunded
rx_p0_K_r3_first_eop:
    ret
rx_p0_K_r3_unfunded:
    ret
rx_p0_K_r3:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r3_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r3_second_zero_veneer
rx_p0_K_r3_shift_one:
    asr r18
    nop
rx_p1_K_r4_inline_20:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r4_inline_20_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r4_inline_20_second_zero_veneer
rx_p1_K_r4_inline_20_shift_one:
    asr r18
    rjmp rx_p2_K_r5
rx_p1_K_r4_inline_20_second_zero_veneer:
    rjmp rx_p1_K_r4_inline_20_second_zero
rx_p0_K_r3_second_zero_veneer:
    rjmp rx_p0_K_r3_second_zero
rx_p1_K_r3_second_zero:
    andi r19, 6
    breq rx_p1_K_r3_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r3_unfunded
    sec
rx_p1_K_r3_shift_recovered_one:
    ror r18
rx_p1_K_r3_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r3_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r3_second_eop:
    ret
rx_p1_K_r3_different:
    breq rx_p1_K_r3_first_zero
rx_p1_K_r3_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r3_first_zero:
    andi r19, 6
    breq rx_p1_K_r3_first_eop
    andi r17, 6
    breq rx_p1_K_r3_first_eop
    rjmp rx_p1_K_r3_unfunded
rx_p1_K_r3_first_eop:
    ret
rx_p1_K_r3_unfunded:
    ret
rx_p1_K_r3:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r3_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r3_second_zero_veneer
rx_p1_K_r3_shift_one:
    asr r18
    rjmp rx_p2_K_r4
rx_p1_K_r3_second_zero_veneer:
    rjmp rx_p1_K_r3_second_zero
rx_p2_K_r3_second_zero:
    andi r19, 6
    breq rx_p2_K_r3_second_eop
    cpse r19, r20
    rjmp rx_p2_K_r3_unfunded
    sec
rx_p2_K_r3_shift_recovered_one:
    ror r18
rx_p2_K_r3_shift_future_zero:
    lsr r18
    nop
rx_p2_K_r3_consumed_future_symbol:
    rjmp rx_p1_J_r0
rx_p2_K_r3_second_eop:
    ret
rx_p2_K_r3_different:
    breq rx_p2_K_r3_first_zero
rx_p2_K_r3_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r3_first_zero:
    andi r19, 6
    breq rx_p2_K_r3_first_eop
    andi r17, 6
    breq rx_p2_K_r3_first_eop
    rjmp rx_p2_K_r3_unfunded
rx_p2_K_r3_first_eop:
    ret
rx_p2_K_r3_unfunded:
    ret
rx_p2_K_r3:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r3_different
    andi r17, 6
    in r19, 9
    breq rx_p2_K_r3_second_zero_veneer
rx_p2_K_r3_shift_one:
    asr r18
    rjmp rx_p0_K_r4
rx_p2_K_r3_second_zero_veneer:
    rjmp rx_p2_K_r3_second_zero
rx_p1_J_r1_inline_24_second_zero:
    andi r19, 6
    breq rx_p1_J_r1_inline_24_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r1_inline_24_unfunded
    sec
rx_p1_J_r1_inline_24_shift_recovered_one:
    ror r18
rx_p1_J_r1_inline_24_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r1_inline_24_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r1_inline_24_second_eop:
    ret
rx_p1_J_r1_inline_24_different:
    breq rx_p1_J_r1_inline_24_first_zero
rx_p1_J_r1_inline_24_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r1_inline_24_first_zero:
    andi r19, 6
    breq rx_p1_J_r1_inline_24_first_eop
    andi r17, 6
    breq rx_p1_J_r1_inline_24_first_eop
    rjmp rx_p1_J_r1_inline_24_unfunded
rx_p1_J_r1_inline_24_first_eop:
    ret
rx_p1_J_r1_inline_24_unfunded:
    ret
rx_p0_J_r0_second_zero:
    andi r19, 6
    breq rx_p0_J_r0_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r0_unfunded
    sec
rx_p0_J_r0_shift_recovered_one:
    ror r18
rx_p0_J_r0_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r0_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r0_second_eop:
    ret
rx_p0_J_r0_different:
    breq rx_p0_J_r0_first_zero
rx_p0_J_r0_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r0_first_zero:
    andi r17, 6
    breq rx_p0_J_r0_first_eop
    rjmp rx_p0_J_r0_unfunded
rx_p0_J_r0_first_eop:
    ret
rx_p0_J_r0_unfunded:
    ret
rx_p0_J_r0:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r0_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r0_second_zero_veneer
    sec
rx_p0_J_r0_shift_one:
    ror r18
rx_p1_J_r1_inline_24:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r1_inline_24_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r1_inline_24_second_zero_veneer
rx_p1_J_r1_inline_24_shift_one:
    asr r18
    rjmp rx_p2_J_r2
rx_p1_J_r1_inline_24_second_zero_veneer:
    rjmp rx_p1_J_r1_inline_24_second_zero
rx_p0_J_r0_second_zero_veneer:
    rjmp rx_p0_J_r0_second_zero
rx_p2_J_r1_inline_26_second_zero:
    andi r19, 6
    breq rx_p2_J_r1_inline_26_second_eop
    cpse r19, r21
    rjmp rx_p2_J_r1_inline_26_unfunded
    sec
rx_p2_J_r1_inline_26_shift_recovered_one:
    ror r18
rx_p2_J_r1_inline_26_shift_future_zero:
    lsr r18
    nop
rx_p2_J_r1_inline_26_consumed_future_symbol:
    rjmp rx_p1_K_r0
rx_p2_J_r1_inline_26_second_eop:
    ret
rx_p2_J_r1_inline_26_different:
    breq rx_p2_J_r1_inline_26_first_zero
rx_p2_J_r1_inline_26_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r1_inline_26_first_zero:
    andi r19, 6
    breq rx_p2_J_r1_inline_26_first_eop
    andi r17, 6
    breq rx_p2_J_r1_inline_26_first_eop
    rjmp rx_p2_J_r1_inline_26_unfunded
rx_p2_J_r1_inline_26_first_eop:
    ret
rx_p2_J_r1_inline_26_unfunded:
    ret
rx_p1_K_r2_inline_29_second_zero:
    andi r19, 6
    breq rx_p1_K_r2_inline_29_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r2_inline_29_unfunded
    sec
rx_p1_K_r2_inline_29_shift_recovered_one:
    ror r18
rx_p1_K_r2_inline_29_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r2_inline_29_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r2_inline_29_second_eop:
    ret
rx_p1_K_r2_inline_29_different:
    breq rx_p1_K_r2_inline_29_first_zero
rx_p1_K_r2_inline_29_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r2_inline_29_first_zero:
    andi r19, 6
    breq rx_p1_K_r2_inline_29_first_eop
    andi r17, 6
    breq rx_p1_K_r2_inline_29_first_eop
    rjmp rx_p1_K_r2_inline_29_unfunded
rx_p1_K_r2_inline_29_first_eop:
    ret
rx_p1_K_r2_inline_29_unfunded:
    ret
rx_p0_K_r1_inline_28_second_zero:
    andi r19, 6
    breq rx_p0_K_r1_inline_28_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r1_inline_28_unfunded
    sec
rx_p0_K_r1_inline_28_shift_recovered_one:
    ror r18
rx_p0_K_r1_inline_28_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r1_inline_28_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r1_inline_28_second_eop:
    ret
rx_p0_K_r1_inline_28_different:
    breq rx_p0_K_r1_inline_28_first_zero
rx_p0_K_r1_inline_28_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r1_inline_28_first_zero:
    andi r19, 6
    breq rx_p0_K_r1_inline_28_first_eop
    andi r17, 6
    breq rx_p0_K_r1_inline_28_first_eop
    rjmp rx_p0_K_r1_inline_28_unfunded
rx_p0_K_r1_inline_28_first_eop:
    ret
rx_p0_K_r1_inline_28_unfunded:
    ret
rx_p1_J_r1_inline_31_second_zero:
    andi r19, 6
    breq rx_p1_J_r1_inline_31_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r1_inline_31_unfunded
    sec
rx_p1_J_r1_inline_31_shift_recovered_one:
    ror r18
rx_p1_J_r1_inline_31_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r1_inline_31_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r1_inline_31_second_eop:
    ret
rx_p1_J_r1_inline_31_different:
    breq rx_p1_J_r1_inline_31_first_zero
rx_p1_J_r1_inline_31_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r1_inline_31_first_zero:
    andi r19, 6
    breq rx_p1_J_r1_inline_31_first_eop
    andi r17, 6
    breq rx_p1_J_r1_inline_31_first_eop
    rjmp rx_p1_J_r1_inline_31_unfunded
rx_p1_J_r1_inline_31_first_eop:
    ret
rx_p1_J_r1_inline_31_unfunded:
    ret
rx_p0_J_r0_after_recovered_28_second_zero:
    andi r19, 6
    breq rx_p0_J_r0_after_recovered_28_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r0_after_recovered_28_unfunded
    sec
rx_p0_J_r0_after_recovered_28_shift_recovered_one:
    ror r18
rx_p0_J_r0_after_recovered_28_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r0_after_recovered_28_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r0_after_recovered_28_second_eop:
    ret
rx_p0_J_r0_after_recovered_28_different:
    breq rx_p0_J_r0_after_recovered_28_first_zero
rx_p0_J_r0_after_recovered_28_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r0_after_recovered_28_first_zero:
    andi r17, 6
    breq rx_p0_J_r0_after_recovered_28_first_eop
    rjmp rx_p0_J_r0_after_recovered_28_unfunded
rx_p0_J_r0_after_recovered_28_first_eop:
    ret
rx_p0_J_r0_after_recovered_28_unfunded:
    ret
rx_p2_K_r0_after_recovered_26_second_zero:
    andi r19, 6
    breq rx_p2_K_r0_after_recovered_26_second_eop
    cpse r19, r20
    rjmp rx_p2_K_r0_after_recovered_26_unfunded
    sec
rx_p2_K_r0_after_recovered_26_shift_recovered_one:
    ror r18
rx_p2_K_r0_after_recovered_26_shift_future_zero:
    lsr r18
    nop
rx_p2_K_r0_after_recovered_26_consumed_future_symbol:
    rjmp rx_p1_J_r0
rx_p2_K_r0_after_recovered_26_second_eop:
    ret
rx_p2_K_r0_after_recovered_26_different:
    breq rx_p2_K_r0_after_recovered_26_first_zero
rx_p2_K_r0_after_recovered_26_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r0_after_recovered_26_first_zero:
    andi r17, 6
    breq rx_p2_K_r0_after_recovered_26_first_eop
rx_p2_K_r0_after_recovered_26_shift_recovered_zero:
    lsr r18
rx_p0_J_r0_after_recovered_28:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r0_after_recovered_28_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r0_after_recovered_28_second_zero_veneer
    sec
rx_p0_J_r0_after_recovered_28_shift_one:
    ror r18
rx_p1_J_r1_inline_31:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r1_inline_31_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r1_inline_31_second_zero_veneer
rx_p1_J_r1_inline_31_shift_one:
    asr r18
    rjmp rx_p2_J_r2
rx_p1_J_r1_inline_31_second_zero_veneer:
    rjmp rx_p1_J_r1_inline_31_second_zero
rx_p0_J_r0_after_recovered_28_second_zero_veneer:
    rjmp rx_p0_J_r0_after_recovered_28_second_zero
rx_p2_K_r0_after_recovered_26_first_eop:
    ret
rx_p2_K_r0_after_recovered_26_unfunded:
    ret
rx_p1_J_r0_second_zero:
    andi r19, 6
    breq rx_p1_J_r0_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r0_unfunded
    sec
rx_p1_J_r0_shift_recovered_one:
    ror r18
rx_p1_J_r0_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r0_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r0_second_eop:
    ret
rx_p1_J_r0_different:
    breq rx_p1_J_r0_first_zero
rx_p1_J_r0_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r0_first_zero:
    andi r17, 6
    breq rx_p1_J_r0_first_eop
rx_p1_J_r0_shift_recovered_zero:
    lsr r18
rx_p2_K_r0_after_recovered_26:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r0_after_recovered_26_different
    andi r17, 6
    in r19, 9
    breq rx_p2_K_r0_after_recovered_26_second_zero_veneer
    sec
rx_p2_K_r0_after_recovered_26_shift_one:
    ror r18
    nop
rx_p0_K_r1_inline_28:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r1_inline_28_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r1_inline_28_second_zero_veneer
rx_p0_K_r1_inline_28_shift_one:
    asr r18
    nop
rx_p1_K_r2_inline_29:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r2_inline_29_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r2_inline_29_second_zero_veneer
rx_p1_K_r2_inline_29_shift_one:
    asr r18
    rjmp rx_p2_K_r3
rx_p1_K_r2_inline_29_second_zero_veneer:
    rjmp rx_p1_K_r2_inline_29_second_zero
rx_p0_K_r1_inline_28_second_zero_veneer:
    rjmp rx_p0_K_r1_inline_28_second_zero
rx_p2_K_r0_after_recovered_26_second_zero_veneer:
    rjmp rx_p2_K_r0_after_recovered_26_second_zero
rx_p1_J_r0_first_eop:
    ret
rx_p1_J_r0_unfunded:
    ret
rx_p1_J_r0:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r0_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r0_second_zero_veneer
    sec
rx_p1_J_r0_shift_one:
    ror r18
    nop
rx_p2_J_r1_inline_26:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r1_inline_26_different
    andi r17, 6
    in r19, 9
    breq rx_p2_J_r1_inline_26_second_zero_veneer
rx_p2_J_r1_inline_26_shift_one:
    asr r18
    rjmp rx_p0_J_r2
rx_p2_J_r1_inline_26_second_zero_veneer:
    rjmp rx_p2_J_r1_inline_26_second_zero
rx_p1_J_r0_second_zero_veneer:
    rjmp rx_p1_J_r0_second_zero
rx_p1_J_r2_inline_34_second_zero:
    andi r19, 6
    breq rx_p1_J_r2_inline_34_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r2_inline_34_unfunded
    sec
rx_p1_J_r2_inline_34_shift_recovered_one:
    ror r18
rx_p1_J_r2_inline_34_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r2_inline_34_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r2_inline_34_second_eop:
    ret
rx_p1_J_r2_inline_34_different:
    breq rx_p1_J_r2_inline_34_first_zero
rx_p1_J_r2_inline_34_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r2_inline_34_first_zero:
    andi r19, 6
    breq rx_p1_J_r2_inline_34_first_eop
    andi r17, 6
    breq rx_p1_J_r2_inline_34_first_eop
    rjmp rx_p1_J_r2_inline_34_unfunded
rx_p1_J_r2_inline_34_first_eop:
    ret
rx_p1_J_r2_inline_34_unfunded:
    ret
rx_p0_J_r1_inline_33_second_zero:
    andi r19, 6
    breq rx_p0_J_r1_inline_33_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r1_inline_33_unfunded
    sec
rx_p0_J_r1_inline_33_shift_recovered_one:
    ror r18
rx_p0_J_r1_inline_33_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r1_inline_33_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r1_inline_33_second_eop:
    ret
rx_p0_J_r1_inline_33_different:
    breq rx_p0_J_r1_inline_33_first_zero
rx_p0_J_r1_inline_33_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r1_inline_33_first_zero:
    andi r19, 6
    breq rx_p0_J_r1_inline_33_first_eop
    andi r17, 6
    breq rx_p0_J_r1_inline_33_first_eop
    rjmp rx_p0_J_r1_inline_33_unfunded
rx_p0_J_r1_inline_33_first_eop:
    ret
rx_p0_J_r1_inline_33_unfunded:
    ret
rx_p1_K_r1_inline_36_second_zero:
    andi r19, 6
    breq rx_p1_K_r1_inline_36_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r1_inline_36_unfunded
    sec
rx_p1_K_r1_inline_36_shift_recovered_one:
    ror r18
rx_p1_K_r1_inline_36_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r1_inline_36_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r1_inline_36_second_eop:
    ret
rx_p1_K_r1_inline_36_different:
    breq rx_p1_K_r1_inline_36_first_zero
rx_p1_K_r1_inline_36_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r1_inline_36_first_zero:
    andi r19, 6
    breq rx_p1_K_r1_inline_36_first_eop
    andi r17, 6
    breq rx_p1_K_r1_inline_36_first_eop
    rjmp rx_p1_K_r1_inline_36_unfunded
rx_p1_K_r1_inline_36_first_eop:
    ret
rx_p1_K_r1_inline_36_unfunded:
    ret
rx_p0_K_r0_after_recovered_33_second_zero:
    andi r19, 6
    breq rx_p0_K_r0_after_recovered_33_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r0_after_recovered_33_unfunded
    sec
rx_p0_K_r0_after_recovered_33_shift_recovered_one:
    ror r18
rx_p0_K_r0_after_recovered_33_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r0_after_recovered_33_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r0_after_recovered_33_second_eop:
    ret
rx_p0_K_r0_after_recovered_33_different:
    breq rx_p0_K_r0_after_recovered_33_first_zero
rx_p0_K_r0_after_recovered_33_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r0_after_recovered_33_first_zero:
    andi r17, 6
    breq rx_p0_K_r0_after_recovered_33_first_eop
    rjmp rx_p0_K_r0_after_recovered_33_unfunded
rx_p0_K_r0_after_recovered_33_first_eop:
    ret
rx_p0_K_r0_after_recovered_33_unfunded:
    ret
rx_p2_J_r0_second_zero:
    andi r19, 6
    breq rx_p2_J_r0_second_eop
    cpse r19, r21
    rjmp rx_p2_J_r0_unfunded
    sec
rx_p2_J_r0_shift_recovered_one:
    ror r18
rx_p2_J_r0_shift_future_zero:
    lsr r18
    nop
rx_p2_J_r0_consumed_future_symbol:
    rjmp rx_p1_K_r0
rx_p2_J_r0_second_eop:
    ret
rx_p2_J_r0_different:
    breq rx_p2_J_r0_first_zero
rx_p2_J_r0_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r0_first_zero:
    andi r17, 6
    breq rx_p2_J_r0_first_eop
rx_p2_J_r0_shift_recovered_zero:
    lsr r18
rx_p0_K_r0_after_recovered_33:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r0_after_recovered_33_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r0_after_recovered_33_second_zero_veneer
    sec
rx_p0_K_r0_after_recovered_33_shift_one:
    ror r18
rx_p1_K_r1_inline_36:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r1_inline_36_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r1_inline_36_second_zero_veneer
rx_p1_K_r1_inline_36_shift_one:
    asr r18
    rjmp rx_p2_K_r2
rx_p1_K_r1_inline_36_second_zero_veneer:
    rjmp rx_p1_K_r1_inline_36_second_zero
rx_p0_K_r0_after_recovered_33_second_zero_veneer:
    rjmp rx_p0_K_r0_after_recovered_33_second_zero
rx_p2_J_r0_first_eop:
    ret
rx_p2_J_r0_unfunded:
    ret
rx_p2_J_r0:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r0_different
    andi r17, 6
    in r19, 9
    breq rx_p2_J_r0_second_zero_veneer
    sec
rx_p2_J_r0_shift_one:
    ror r18
    nop
rx_p0_J_r1_inline_33:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r1_inline_33_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r1_inline_33_second_zero_veneer
rx_p0_J_r1_inline_33_shift_one:
    asr r18
    nop
rx_p1_J_r2_inline_34:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r2_inline_34_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r2_inline_34_second_zero_veneer
rx_p1_J_r2_inline_34_shift_one:
    asr r18
    rjmp rx_p2_J_r3
rx_p1_J_r2_inline_34_second_zero_veneer:
    rjmp rx_p1_J_r2_inline_34_second_zero
rx_p0_J_r1_inline_33_second_zero_veneer:
    rjmp rx_p0_J_r1_inline_33_second_zero
rx_p2_J_r0_second_zero_veneer:
    rjmp rx_p2_J_r0_second_zero
rx_p1_K_r1_inline_38_second_zero:
    andi r19, 6
    breq rx_p1_K_r1_inline_38_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r1_inline_38_unfunded
    sec
rx_p1_K_r1_inline_38_shift_recovered_one:
    ror r18
rx_p1_K_r1_inline_38_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r1_inline_38_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r1_inline_38_second_eop:
    ret
rx_p1_K_r1_inline_38_different:
    breq rx_p1_K_r1_inline_38_first_zero
rx_p1_K_r1_inline_38_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r1_inline_38_first_zero:
    andi r19, 6
    breq rx_p1_K_r1_inline_38_first_eop
    andi r17, 6
    breq rx_p1_K_r1_inline_38_first_eop
    rjmp rx_p1_K_r1_inline_38_unfunded
rx_p1_K_r1_inline_38_first_eop:
    ret
rx_p1_K_r1_inline_38_unfunded:
    ret
rx_p0_K_r0_second_zero:
    andi r19, 6
    breq rx_p0_K_r0_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r0_unfunded
    sec
rx_p0_K_r0_shift_recovered_one:
    ror r18
rx_p0_K_r0_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r0_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r0_second_eop:
    ret
rx_p0_K_r0_different:
    breq rx_p0_K_r0_first_zero
rx_p0_K_r0_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r0_first_zero:
    andi r17, 6
    breq rx_p0_K_r0_first_eop
    rjmp rx_p0_K_r0_unfunded
rx_p0_K_r0_first_eop:
    ret
rx_p0_K_r0_unfunded:
    ret
rx_p0_K_r0:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r0_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r0_second_zero_veneer
    sec
rx_p0_K_r0_shift_one:
    ror r18
rx_p1_K_r1_inline_38:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r1_inline_38_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r1_inline_38_second_zero_veneer
rx_p1_K_r1_inline_38_shift_one:
    asr r18
    rjmp rx_p2_K_r2
rx_p1_K_r1_inline_38_second_zero_veneer:
    rjmp rx_p1_K_r1_inline_38_second_zero
rx_p0_K_r0_second_zero_veneer:
    rjmp rx_p0_K_r0_second_zero
rx_p2_K_r1_inline_40_second_zero:
    andi r19, 6
    breq rx_p2_K_r1_inline_40_second_eop
    cpse r19, r20
    rjmp rx_p2_K_r1_inline_40_unfunded
    sec
rx_p2_K_r1_inline_40_shift_recovered_one:
    ror r18
rx_p2_K_r1_inline_40_shift_future_zero:
    lsr r18
    nop
rx_p2_K_r1_inline_40_consumed_future_symbol:
    rjmp rx_p1_J_r0
rx_p2_K_r1_inline_40_second_eop:
    ret
rx_p2_K_r1_inline_40_different:
    breq rx_p2_K_r1_inline_40_first_zero
rx_p2_K_r1_inline_40_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r1_inline_40_first_zero:
    andi r19, 6
    breq rx_p2_K_r1_inline_40_first_eop
    andi r17, 6
    breq rx_p2_K_r1_inline_40_first_eop
    rjmp rx_p2_K_r1_inline_40_unfunded
rx_p2_K_r1_inline_40_first_eop:
    ret
rx_p2_K_r1_inline_40_unfunded:
    ret
rx_p1_J_r2_inline_43_second_zero:
    andi r19, 6
    breq rx_p1_J_r2_inline_43_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r2_inline_43_unfunded
    sec
rx_p1_J_r2_inline_43_shift_recovered_one:
    ror r18
rx_p1_J_r2_inline_43_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r2_inline_43_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r2_inline_43_second_eop:
    ret
rx_p1_J_r2_inline_43_different:
    breq rx_p1_J_r2_inline_43_first_zero
rx_p1_J_r2_inline_43_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r2_inline_43_first_zero:
    andi r19, 6
    breq rx_p1_J_r2_inline_43_first_eop
    andi r17, 6
    breq rx_p1_J_r2_inline_43_first_eop
    rjmp rx_p1_J_r2_inline_43_unfunded
rx_p1_J_r2_inline_43_first_eop:
    ret
rx_p1_J_r2_inline_43_unfunded:
    ret
rx_p0_J_r1_inline_42_second_zero:
    andi r19, 6
    breq rx_p0_J_r1_inline_42_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r1_inline_42_unfunded
    sec
rx_p0_J_r1_inline_42_shift_recovered_one:
    ror r18
rx_p0_J_r1_inline_42_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r1_inline_42_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r1_inline_42_second_eop:
    ret
rx_p0_J_r1_inline_42_different:
    breq rx_p0_J_r1_inline_42_first_zero
rx_p0_J_r1_inline_42_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r1_inline_42_first_zero:
    andi r19, 6
    breq rx_p0_J_r1_inline_42_first_eop
    andi r17, 6
    breq rx_p0_J_r1_inline_42_first_eop
    rjmp rx_p0_J_r1_inline_42_unfunded
rx_p0_J_r1_inline_42_first_eop:
    ret
rx_p0_J_r1_inline_42_unfunded:
    ret
rx_p1_K_r1_inline_45_second_zero:
    andi r19, 6
    breq rx_p1_K_r1_inline_45_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r1_inline_45_unfunded
    sec
rx_p1_K_r1_inline_45_shift_recovered_one:
    ror r18
rx_p1_K_r1_inline_45_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r1_inline_45_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r1_inline_45_second_eop:
    ret
rx_p1_K_r1_inline_45_different:
    breq rx_p1_K_r1_inline_45_first_zero
rx_p1_K_r1_inline_45_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r1_inline_45_first_zero:
    andi r19, 6
    breq rx_p1_K_r1_inline_45_first_eop
    andi r17, 6
    breq rx_p1_K_r1_inline_45_first_eop
    rjmp rx_p1_K_r1_inline_45_unfunded
rx_p1_K_r1_inline_45_first_eop:
    ret
rx_p1_K_r1_inline_45_unfunded:
    ret
rx_p0_K_r0_after_recovered_42_second_zero:
    andi r19, 6
    breq rx_p0_K_r0_after_recovered_42_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r0_after_recovered_42_unfunded
    sec
rx_p0_K_r0_after_recovered_42_shift_recovered_one:
    ror r18
rx_p0_K_r0_after_recovered_42_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r0_after_recovered_42_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r0_after_recovered_42_second_eop:
    ret
rx_p0_K_r0_after_recovered_42_different:
    breq rx_p0_K_r0_after_recovered_42_first_zero
rx_p0_K_r0_after_recovered_42_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r0_after_recovered_42_first_zero:
    andi r17, 6
    breq rx_p0_K_r0_after_recovered_42_first_eop
    rjmp rx_p0_K_r0_after_recovered_42_unfunded
rx_p0_K_r0_after_recovered_42_first_eop:
    ret
rx_p0_K_r0_after_recovered_42_unfunded:
    ret
rx_p2_J_r0_after_recovered_40_second_zero:
    andi r19, 6
    breq rx_p2_J_r0_after_recovered_40_second_eop
    cpse r19, r21
    rjmp rx_p2_J_r0_after_recovered_40_unfunded
    sec
rx_p2_J_r0_after_recovered_40_shift_recovered_one:
    ror r18
rx_p2_J_r0_after_recovered_40_shift_future_zero:
    lsr r18
    nop
rx_p2_J_r0_after_recovered_40_consumed_future_symbol:
    rjmp rx_p1_K_r0
rx_p2_J_r0_after_recovered_40_second_eop:
    ret
rx_p2_J_r0_after_recovered_40_different:
    breq rx_p2_J_r0_after_recovered_40_first_zero
rx_p2_J_r0_after_recovered_40_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r0_after_recovered_40_first_zero:
    andi r17, 6
    breq rx_p2_J_r0_after_recovered_40_first_eop
rx_p2_J_r0_after_recovered_40_shift_recovered_zero:
    lsr r18
rx_p0_K_r0_after_recovered_42:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r0_after_recovered_42_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r0_after_recovered_42_second_zero_veneer
    sec
rx_p0_K_r0_after_recovered_42_shift_one:
    ror r18
rx_p1_K_r1_inline_45:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r1_inline_45_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r1_inline_45_second_zero_veneer
rx_p1_K_r1_inline_45_shift_one:
    asr r18
    rjmp rx_p2_K_r2
rx_p1_K_r1_inline_45_second_zero_veneer:
    rjmp rx_p1_K_r1_inline_45_second_zero
rx_p0_K_r0_after_recovered_42_second_zero_veneer:
    rjmp rx_p0_K_r0_after_recovered_42_second_zero
rx_p2_J_r0_after_recovered_40_first_eop:
    ret
rx_p2_J_r0_after_recovered_40_unfunded:
    ret
rx_p1_K_r0_second_zero:
    andi r19, 6
    breq rx_p1_K_r0_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r0_unfunded
    sec
rx_p1_K_r0_shift_recovered_one:
    ror r18
rx_p1_K_r0_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r0_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r0_second_eop:
    ret
rx_p1_K_r0_different:
    breq rx_p1_K_r0_first_zero
rx_p1_K_r0_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r0_first_zero:
    andi r17, 6
    breq rx_p1_K_r0_first_eop
rx_p1_K_r0_shift_recovered_zero:
    lsr r18
rx_p2_J_r0_after_recovered_40:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r0_after_recovered_40_different
    andi r17, 6
    in r19, 9
    breq rx_p2_J_r0_after_recovered_40_second_zero_veneer
    sec
rx_p2_J_r0_after_recovered_40_shift_one:
    ror r18
    nop
rx_p0_J_r1_inline_42:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r1_inline_42_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r1_inline_42_second_zero_veneer
rx_p0_J_r1_inline_42_shift_one:
    asr r18
    nop
rx_p1_J_r2_inline_43:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r2_inline_43_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r2_inline_43_second_zero_veneer
rx_p1_J_r2_inline_43_shift_one:
    asr r18
    rjmp rx_p2_J_r3
rx_p1_J_r2_inline_43_second_zero_veneer:
    rjmp rx_p1_J_r2_inline_43_second_zero
rx_p0_J_r1_inline_42_second_zero_veneer:
    rjmp rx_p0_J_r1_inline_42_second_zero
rx_p2_J_r0_after_recovered_40_second_zero_veneer:
    rjmp rx_p2_J_r0_after_recovered_40_second_zero
rx_p1_K_r0_first_eop:
    ret
rx_p1_K_r0_unfunded:
    ret
rx_p1_K_r0:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r0_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r0_second_zero_veneer
    sec
rx_p1_K_r0_shift_one:
    ror r18
    nop
rx_p2_K_r1_inline_40:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r1_inline_40_different
    andi r17, 6
    in r19, 9
    breq rx_p2_K_r1_inline_40_second_zero_veneer
rx_p2_K_r1_inline_40_shift_one:
    asr r18
    rjmp rx_p0_K_r2
rx_p2_K_r1_inline_40_second_zero_veneer:
    rjmp rx_p2_K_r1_inline_40_second_zero
rx_p1_K_r0_second_zero_veneer:
    rjmp rx_p1_K_r0_second_zero
rx_p1_K_r2_inline_48_second_zero:
    andi r19, 6
    breq rx_p1_K_r2_inline_48_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r2_inline_48_unfunded
    sec
rx_p1_K_r2_inline_48_shift_recovered_one:
    ror r18
rx_p1_K_r2_inline_48_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r2_inline_48_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r2_inline_48_second_eop:
    ret
rx_p1_K_r2_inline_48_different:
    breq rx_p1_K_r2_inline_48_first_zero
rx_p1_K_r2_inline_48_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r2_inline_48_first_zero:
    andi r19, 6
    breq rx_p1_K_r2_inline_48_first_eop
    andi r17, 6
    breq rx_p1_K_r2_inline_48_first_eop
    rjmp rx_p1_K_r2_inline_48_unfunded
rx_p1_K_r2_inline_48_first_eop:
    ret
rx_p1_K_r2_inline_48_unfunded:
    ret
rx_p0_K_r1_inline_47_second_zero:
    andi r19, 6
    breq rx_p0_K_r1_inline_47_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r1_inline_47_unfunded
    sec
rx_p0_K_r1_inline_47_shift_recovered_one:
    ror r18
rx_p0_K_r1_inline_47_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r1_inline_47_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r1_inline_47_second_eop:
    ret
rx_p0_K_r1_inline_47_different:
    breq rx_p0_K_r1_inline_47_first_zero
rx_p0_K_r1_inline_47_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r1_inline_47_first_zero:
    andi r19, 6
    breq rx_p0_K_r1_inline_47_first_eop
    andi r17, 6
    breq rx_p0_K_r1_inline_47_first_eop
    rjmp rx_p0_K_r1_inline_47_unfunded
rx_p0_K_r1_inline_47_first_eop:
    ret
rx_p0_K_r1_inline_47_unfunded:
    ret
rx_p1_J_r1_inline_50_second_zero:
    andi r19, 6
    breq rx_p1_J_r1_inline_50_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r1_inline_50_unfunded
    sec
rx_p1_J_r1_inline_50_shift_recovered_one:
    ror r18
rx_p1_J_r1_inline_50_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r1_inline_50_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r1_inline_50_second_eop:
    ret
rx_p1_J_r1_inline_50_different:
    breq rx_p1_J_r1_inline_50_first_zero
rx_p1_J_r1_inline_50_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r1_inline_50_first_zero:
    andi r19, 6
    breq rx_p1_J_r1_inline_50_first_eop
    andi r17, 6
    breq rx_p1_J_r1_inline_50_first_eop
    rjmp rx_p1_J_r1_inline_50_unfunded
rx_p1_J_r1_inline_50_first_eop:
    ret
rx_p1_J_r1_inline_50_unfunded:
    ret
rx_p0_J_r0_after_recovered_47_second_zero:
    andi r19, 6
    breq rx_p0_J_r0_after_recovered_47_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r0_after_recovered_47_unfunded
    sec
rx_p0_J_r0_after_recovered_47_shift_recovered_one:
    ror r18
rx_p0_J_r0_after_recovered_47_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r0_after_recovered_47_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r0_after_recovered_47_second_eop:
    ret
rx_p0_J_r0_after_recovered_47_different:
    breq rx_p0_J_r0_after_recovered_47_first_zero
rx_p0_J_r0_after_recovered_47_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r0_after_recovered_47_first_zero:
    andi r17, 6
    breq rx_p0_J_r0_after_recovered_47_first_eop
    rjmp rx_p0_J_r0_after_recovered_47_unfunded
rx_p0_J_r0_after_recovered_47_first_eop:
    ret
rx_p0_J_r0_after_recovered_47_unfunded:
    ret
rx_p2_K_r0_second_zero:
    andi r19, 6
    breq rx_p2_K_r0_second_eop
    cpse r19, r20
    rjmp rx_p2_K_r0_unfunded
    sec
rx_p2_K_r0_shift_recovered_one:
    ror r18
rx_p2_K_r0_shift_future_zero:
    lsr r18
    nop
rx_p2_K_r0_consumed_future_symbol:
    rjmp rx_p1_J_r0
rx_p2_K_r0_second_eop:
    ret
rx_p2_K_r0_different:
    breq rx_p2_K_r0_first_zero
rx_p2_K_r0_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r0_first_zero:
    andi r17, 6
    breq rx_p2_K_r0_first_eop
rx_p2_K_r0_shift_recovered_zero:
    lsr r18
rx_p0_J_r0_after_recovered_47:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r0_after_recovered_47_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r0_after_recovered_47_second_zero_veneer
    sec
rx_p0_J_r0_after_recovered_47_shift_one:
    ror r18
rx_p1_J_r1_inline_50:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r1_inline_50_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r1_inline_50_second_zero_veneer
rx_p1_J_r1_inline_50_shift_one:
    asr r18
    rjmp rx_p2_J_r2
rx_p1_J_r1_inline_50_second_zero_veneer:
    rjmp rx_p1_J_r1_inline_50_second_zero
rx_p0_J_r0_after_recovered_47_second_zero_veneer:
    rjmp rx_p0_J_r0_after_recovered_47_second_zero
rx_p2_K_r0_first_eop:
    ret
rx_p2_K_r0_unfunded:
    ret
rx_p2_K_r0:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r0_different
    andi r17, 6
    in r19, 9
    breq rx_p2_K_r0_second_zero_veneer
    sec
rx_p2_K_r0_shift_one:
    ror r18
    nop
rx_p0_K_r1_inline_47:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r1_inline_47_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r1_inline_47_second_zero_veneer
rx_p0_K_r1_inline_47_shift_one:
    asr r18
    nop
rx_p1_K_r2_inline_48:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r2_inline_48_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r2_inline_48_second_zero_veneer
rx_p1_K_r2_inline_48_shift_one:
    asr r18
    rjmp rx_p2_K_r3
rx_p1_K_r2_inline_48_second_zero_veneer:
    rjmp rx_p1_K_r2_inline_48_second_zero
rx_p0_K_r1_inline_47_second_zero_veneer:
    rjmp rx_p0_K_r1_inline_47_second_zero
rx_p2_K_r0_second_zero_veneer:
    rjmp rx_p2_K_r0_second_zero
rx_p1_J_r5_inline_52_second_zero:
    andi r19, 6
    breq rx_p1_J_r5_inline_52_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r5_inline_52_unfunded
    sec
rx_p1_J_r5_inline_52_shift_recovered_one:
    ror r18
    nop
    nop
    nop
rx_p1_J_r5_inline_52_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r5_inline_52_second_eop:
    ret
rx_p1_J_r5_inline_52_different:
    breq rx_p1_J_r5_inline_52_first_zero
rx_p1_J_r5_inline_52_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r5_inline_52_first_zero:
    andi r19, 6
    breq rx_p1_J_r5_inline_52_first_eop
    andi r17, 6
    breq rx_p1_J_r5_inline_52_first_eop
    rjmp rx_p1_J_r5_inline_52_unfunded
rx_p1_J_r5_inline_52_first_eop:
    ret
rx_p1_J_r5_inline_52_unfunded:
    ret
rx_p0_J_r4_second_zero:
    andi r19, 6
    breq rx_p0_J_r4_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r4_unfunded
    sec
rx_p0_J_r4_shift_recovered_one:
    ror r18
rx_p0_J_r4_shift_future_zero:
    lsr r18
    nop
rx_p0_J_r4_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r4_second_eop:
    ret
rx_p0_J_r4_different:
    breq rx_p0_J_r4_first_zero
rx_p0_J_r4_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r4_first_zero:
    andi r19, 6
    breq rx_p0_J_r4_first_eop
    andi r17, 6
    breq rx_p0_J_r4_first_eop
    rjmp rx_p0_J_r4_unfunded
rx_p0_J_r4_first_eop:
    ret
rx_p0_J_r4_unfunded:
    ret
rx_p0_J_r4:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r4_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r4_second_zero_veneer
rx_p0_J_r4_shift_one:
    asr r18
    nop
rx_p1_J_r5_inline_52:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r5_inline_52_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r5_inline_52_second_zero_veneer
rx_p1_J_r5_inline_52_shift_one:
    asr r18
    rjmp rx_p2_J_r6
rx_p1_J_r5_inline_52_second_zero_veneer:
    rjmp rx_p1_J_r5_inline_52_second_zero
rx_p0_J_r4_second_zero_veneer:
    rjmp rx_p0_J_r4_second_zero
rx_p1_J_r4_second_zero:
    andi r19, 6
    breq rx_p1_J_r4_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r4_unfunded
    sec
rx_p1_J_r4_shift_recovered_one:
    ror r18
rx_p1_J_r4_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_J_r4_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r4_second_eop:
    ret
rx_p1_J_r4_different:
    breq rx_p1_J_r4_first_zero
rx_p1_J_r4_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r4_first_zero:
    andi r19, 6
    breq rx_p1_J_r4_first_eop
    andi r17, 6
    breq rx_p1_J_r4_first_eop
    rjmp rx_p1_J_r4_unfunded
rx_p1_J_r4_first_eop:
    ret
rx_p1_J_r4_unfunded:
    ret
rx_p1_J_r4:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r4_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r4_second_zero_veneer
rx_p1_J_r4_shift_one:
    asr r18
    rjmp rx_p2_J_r5
rx_p1_J_r4_second_zero_veneer:
    rjmp rx_p1_J_r4_second_zero
rx_p2_J_r4_second_zero:
    andi r19, 6
    breq rx_p2_J_r4_second_eop
    cpse r19, r21
    rjmp rx_p2_J_r4_unfunded
    sec
rx_p2_J_r4_shift_recovered_one:
    ror r18
rx_p2_J_r4_shift_future_zero:
    lsr r18
    nop
rx_p2_J_r4_consumed_future_symbol:
    rjmp rx_p1_K_r0
rx_p2_J_r4_second_eop:
    ret
rx_p2_J_r4_different:
    breq rx_p2_J_r4_first_zero
rx_p2_J_r4_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r4_first_zero:
    andi r19, 6
    breq rx_p2_J_r4_first_eop
    andi r17, 6
    breq rx_p2_J_r4_first_eop
    rjmp rx_p2_J_r4_unfunded
rx_p2_J_r4_first_eop:
    ret
rx_p2_J_r4_unfunded:
    ret
rx_p2_J_r4:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r4_different
    andi r17, 6
    in r19, 9
    breq rx_p2_J_r4_second_zero_veneer
rx_p2_J_r4_shift_one:
    asr r18
    rjmp rx_p0_J_r5
rx_p2_J_r4_second_zero_veneer:
    rjmp rx_p2_J_r4_second_zero
rx_p1_K_r5_inline_56_second_zero:
    andi r19, 6
    breq rx_p1_K_r5_inline_56_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r5_inline_56_unfunded
    sec
rx_p1_K_r5_inline_56_shift_recovered_one:
    ror r18
    nop
    nop
    nop
rx_p1_K_r5_inline_56_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r5_inline_56_second_eop:
    ret
rx_p1_K_r5_inline_56_different:
    breq rx_p1_K_r5_inline_56_first_zero
rx_p1_K_r5_inline_56_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r5_inline_56_first_zero:
    andi r19, 6
    breq rx_p1_K_r5_inline_56_first_eop
    andi r17, 6
    breq rx_p1_K_r5_inline_56_first_eop
    rjmp rx_p1_K_r5_inline_56_unfunded
rx_p1_K_r5_inline_56_first_eop:
    ret
rx_p1_K_r5_inline_56_unfunded:
    ret
rx_p0_K_r4_second_zero:
    andi r19, 6
    breq rx_p0_K_r4_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r4_unfunded
    sec
rx_p0_K_r4_shift_recovered_one:
    ror r18
rx_p0_K_r4_shift_future_zero:
    lsr r18
    nop
rx_p0_K_r4_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r4_second_eop:
    ret
rx_p0_K_r4_different:
    breq rx_p0_K_r4_first_zero
rx_p0_K_r4_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r4_first_zero:
    andi r19, 6
    breq rx_p0_K_r4_first_eop
    andi r17, 6
    breq rx_p0_K_r4_first_eop
    rjmp rx_p0_K_r4_unfunded
rx_p0_K_r4_first_eop:
    ret
rx_p0_K_r4_unfunded:
    ret
rx_p0_K_r4:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r4_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r4_second_zero_veneer
rx_p0_K_r4_shift_one:
    asr r18
    nop
rx_p1_K_r5_inline_56:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r5_inline_56_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r5_inline_56_second_zero_veneer
rx_p1_K_r5_inline_56_shift_one:
    asr r18
    rjmp rx_p2_K_r6
rx_p1_K_r5_inline_56_second_zero_veneer:
    rjmp rx_p1_K_r5_inline_56_second_zero
rx_p0_K_r4_second_zero_veneer:
    rjmp rx_p0_K_r4_second_zero
rx_p1_K_r4_second_zero:
    andi r19, 6
    breq rx_p1_K_r4_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r4_unfunded
    sec
rx_p1_K_r4_shift_recovered_one:
    ror r18
rx_p1_K_r4_shift_future_zero:
    lsr r18
    nop
    nop
rx_p1_K_r4_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r4_second_eop:
    ret
rx_p1_K_r4_different:
    breq rx_p1_K_r4_first_zero
rx_p1_K_r4_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r4_first_zero:
    andi r19, 6
    breq rx_p1_K_r4_first_eop
    andi r17, 6
    breq rx_p1_K_r4_first_eop
    rjmp rx_p1_K_r4_unfunded
rx_p1_K_r4_first_eop:
    ret
rx_p1_K_r4_unfunded:
    ret
rx_p1_K_r4:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r4_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r4_second_zero_veneer
rx_p1_K_r4_shift_one:
    asr r18
    rjmp rx_p2_K_r5
rx_p1_K_r4_second_zero_veneer:
    rjmp rx_p1_K_r4_second_zero
rx_p2_K_r4_second_zero:
    andi r19, 6
    breq rx_p2_K_r4_second_eop
    cpse r19, r20
    rjmp rx_p2_K_r4_unfunded
    sec
rx_p2_K_r4_shift_recovered_one:
    ror r18
rx_p2_K_r4_shift_future_zero:
    lsr r18
    nop
rx_p2_K_r4_consumed_future_symbol:
    rjmp rx_p1_J_r0
rx_p2_K_r4_second_eop:
    ret
rx_p2_K_r4_different:
    breq rx_p2_K_r4_first_zero
rx_p2_K_r4_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r4_first_zero:
    andi r19, 6
    breq rx_p2_K_r4_first_eop
    andi r17, 6
    breq rx_p2_K_r4_first_eop
    rjmp rx_p2_K_r4_unfunded
rx_p2_K_r4_first_eop:
    ret
rx_p2_K_r4_unfunded:
    ret
rx_p2_K_r4:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r4_different
    andi r17, 6
    in r19, 9
    breq rx_p2_K_r4_second_zero_veneer
rx_p2_K_r4_shift_one:
    asr r18
    rjmp rx_p0_K_r5
rx_p2_K_r4_second_zero_veneer:
    rjmp rx_p2_K_r4_second_zero
rx_p1_J_r6_inline_60_different:
    breq rx_p1_J_r6_inline_60_first_zero
    nop
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r6_inline_60_first_zero:
    andi r19, 6
    breq rx_p1_J_r6_inline_60_first_eop
    andi r17, 6
    breq rx_p1_J_r6_inline_60_first_eop
    rjmp rx_p1_J_r6_inline_60_unfunded
rx_p1_J_r6_inline_60_first_eop:
    ret
rx_p1_J_r6_inline_60_unfunded:
    ret
rx_p0_J_r5_second_zero:
    andi r19, 6
    breq rx_p0_J_r5_second_eop
    cpse r19, r21
    rjmp rx_p0_J_r5_unfunded
    sec
rx_p0_J_r5_shift_recovered_one:
    ror r18
    nop
    nop
rx_p0_J_r5_consumed_future_symbol:
    rjmp rx_p2_K_r0
rx_p0_J_r5_second_eop:
    ret
rx_p0_J_r5_different:
    breq rx_p0_J_r5_first_zero
rx_p0_J_r5_shift_zero:
    lsr r18
    rjmp rx_p1_K_r0
rx_p0_J_r5_first_zero:
    andi r19, 6
    breq rx_p0_J_r5_first_eop
    andi r17, 6
    breq rx_p0_J_r5_first_eop
    rjmp rx_p0_J_r5_unfunded
rx_p0_J_r5_first_eop:
    ret
rx_p0_J_r5_unfunded:
    ret
rx_p0_J_r5:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r5_different
    andi r17, 6
    in r19, 9
    breq rx_p0_J_r5_second_zero_veneer
rx_p0_J_r5_shift_one:
    asr r18
    nop
rx_p1_J_r6_inline_60:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r6_inline_60_different
rx_p1_J_r6_inline_60_missing_stuff:
    ret
rx_p0_J_r5_second_zero_veneer:
    rjmp rx_p0_J_r5_second_zero
rx_p1_J_r5_second_zero:
    andi r19, 6
    breq rx_p1_J_r5_second_eop
    cpse r19, r21
    rjmp rx_p1_J_r5_unfunded
    sec
rx_p1_J_r5_shift_recovered_one:
    ror r18
    nop
    nop
    nop
rx_p1_J_r5_consumed_future_symbol:
    rjmp rx_p0_K_r0
rx_p1_J_r5_second_eop:
    ret
rx_p1_J_r5_different:
    breq rx_p1_J_r5_first_zero
rx_p1_J_r5_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r5_first_zero:
    andi r19, 6
    breq rx_p1_J_r5_first_eop
    andi r17, 6
    breq rx_p1_J_r5_first_eop
    rjmp rx_p1_J_r5_unfunded
rx_p1_J_r5_first_eop:
    ret
rx_p1_J_r5_unfunded:
    ret
rx_p1_J_r5:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r5_different
    andi r17, 6
    in r19, 9
    breq rx_p1_J_r5_second_zero_veneer
rx_p1_J_r5_shift_one:
    asr r18
    rjmp rx_p2_J_r6
rx_p1_J_r5_second_zero_veneer:
    rjmp rx_p1_J_r5_second_zero
rx_p2_J_r5_second_zero:
    andi r19, 6
    breq rx_p2_J_r5_second_eop
    cpse r19, r21
    rjmp rx_p2_J_r5_unfunded
    sec
rx_p2_J_r5_shift_recovered_one:
    ror r18
    nop
    nop
rx_p2_J_r5_consumed_future_symbol:
    rjmp rx_p1_K_r0
rx_p2_J_r5_second_eop:
    ret
rx_p2_J_r5_different:
    breq rx_p2_J_r5_first_zero
rx_p2_J_r5_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r5_first_zero:
    andi r19, 6
    breq rx_p2_J_r5_first_eop
    andi r17, 6
    breq rx_p2_J_r5_first_eop
    rjmp rx_p2_J_r5_unfunded
rx_p2_J_r5_first_eop:
    ret
rx_p2_J_r5_unfunded:
    ret
rx_p2_J_r5:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r5_different
    andi r17, 6
    in r19, 9
    breq rx_p2_J_r5_second_zero_veneer
rx_p2_J_r5_shift_one:
    asr r18
    rjmp rx_p0_J_r6
rx_p2_J_r5_second_zero_veneer:
    rjmp rx_p2_J_r5_second_zero
rx_p1_K_r6_inline_64_different:
    breq rx_p1_K_r6_inline_64_first_zero
    nop
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r6_inline_64_first_zero:
    andi r19, 6
    breq rx_p1_K_r6_inline_64_first_eop
    andi r17, 6
    breq rx_p1_K_r6_inline_64_first_eop
    rjmp rx_p1_K_r6_inline_64_unfunded
rx_p1_K_r6_inline_64_first_eop:
    ret
rx_p1_K_r6_inline_64_unfunded:
    ret
rx_p0_K_r5_second_zero:
    andi r19, 6
    breq rx_p0_K_r5_second_eop
    cpse r19, r20
    rjmp rx_p0_K_r5_unfunded
    sec
rx_p0_K_r5_shift_recovered_one:
    ror r18
    nop
    nop
rx_p0_K_r5_consumed_future_symbol:
    rjmp rx_p2_J_r0
rx_p0_K_r5_second_eop:
    ret
rx_p0_K_r5_different:
    breq rx_p0_K_r5_first_zero
rx_p0_K_r5_shift_zero:
    lsr r18
    rjmp rx_p1_J_r0
rx_p0_K_r5_first_zero:
    andi r19, 6
    breq rx_p0_K_r5_first_eop
    andi r17, 6
    breq rx_p0_K_r5_first_eop
    rjmp rx_p0_K_r5_unfunded
rx_p0_K_r5_first_eop:
    ret
rx_p0_K_r5_unfunded:
    ret
rx_p0_K_r5:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r5_different
    andi r17, 6
    in r19, 9
    breq rx_p0_K_r5_second_zero_veneer
rx_p0_K_r5_shift_one:
    asr r18
    nop
rx_p1_K_r6_inline_64:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r6_inline_64_different
rx_p1_K_r6_inline_64_missing_stuff:
    ret
rx_p0_K_r5_second_zero_veneer:
    rjmp rx_p0_K_r5_second_zero
rx_p1_K_r5_second_zero:
    andi r19, 6
    breq rx_p1_K_r5_second_eop
    cpse r19, r20
    rjmp rx_p1_K_r5_unfunded
    sec
rx_p1_K_r5_shift_recovered_one:
    ror r18
    nop
    nop
    nop
rx_p1_K_r5_consumed_future_symbol:
    rjmp rx_p0_J_r0
rx_p1_K_r5_second_eop:
    ret
rx_p1_K_r5_different:
    breq rx_p1_K_r5_first_zero
rx_p1_K_r5_shift_zero:
    lsr r18
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r5_first_zero:
    andi r19, 6
    breq rx_p1_K_r5_first_eop
    andi r17, 6
    breq rx_p1_K_r5_first_eop
    rjmp rx_p1_K_r5_unfunded
rx_p1_K_r5_first_eop:
    ret
rx_p1_K_r5_unfunded:
    ret
rx_p1_K_r5:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r5_different
    andi r17, 6
    in r19, 9
    breq rx_p1_K_r5_second_zero_veneer
rx_p1_K_r5_shift_one:
    asr r18
    rjmp rx_p2_K_r6
rx_p1_K_r5_second_zero_veneer:
    rjmp rx_p1_K_r5_second_zero
rx_p2_K_r5_second_zero:
    andi r19, 6
    breq rx_p2_K_r5_second_eop
    cpse r19, r20
    rjmp rx_p2_K_r5_unfunded
    sec
rx_p2_K_r5_shift_recovered_one:
    ror r18
    nop
    nop
rx_p2_K_r5_consumed_future_symbol:
    rjmp rx_p1_J_r0
rx_p2_K_r5_second_eop:
    ret
rx_p2_K_r5_different:
    breq rx_p2_K_r5_first_zero
rx_p2_K_r5_shift_zero:
    lsr r18
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r5_first_zero:
    andi r19, 6
    breq rx_p2_K_r5_first_eop
    andi r17, 6
    breq rx_p2_K_r5_first_eop
    rjmp rx_p2_K_r5_unfunded
rx_p2_K_r5_first_eop:
    ret
rx_p2_K_r5_unfunded:
    ret
rx_p2_K_r5:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r5_different
    andi r17, 6
    in r19, 9
    breq rx_p2_K_r5_second_zero_veneer
rx_p2_K_r5_shift_one:
    asr r18
    rjmp rx_p0_K_r6
rx_p2_K_r5_second_zero_veneer:
    rjmp rx_p2_K_r5_second_zero
rx_p0_J_r6_different:
    breq rx_p0_J_r6_first_zero
    nop
    rjmp rx_p1_K_r0
rx_p0_J_r6_first_zero:
    andi r19, 6
    breq rx_p0_J_r6_first_eop
    andi r17, 6
    breq rx_p0_J_r6_first_eop
    rjmp rx_p0_J_r6_unfunded
rx_p0_J_r6_first_eop:
    ret
rx_p0_J_r6_unfunded:
    ret
rx_p0_J_r6:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p0_J_r6_different
rx_p0_J_r6_missing_stuff:
    ret
rx_p1_J_r6_different:
    breq rx_p1_J_r6_first_zero
    nop
    nop
    rjmp rx_p2_K_r0
rx_p1_J_r6_first_zero:
    andi r19, 6
    breq rx_p1_J_r6_first_eop
    andi r17, 6
    breq rx_p1_J_r6_first_eop
    rjmp rx_p1_J_r6_unfunded
rx_p1_J_r6_first_eop:
    ret
rx_p1_J_r6_unfunded:
    ret
rx_p1_J_r6:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p1_J_r6_different
rx_p1_J_r6_missing_stuff:
    ret
rx_p2_J_r6_different:
    breq rx_p2_J_r6_first_zero
    nop
    nop
    rjmp rx_p0_K_r0
rx_p2_J_r6_first_zero:
    andi r19, 6
    breq rx_p2_J_r6_first_eop
    andi r17, 6
    breq rx_p2_J_r6_first_eop
    rjmp rx_p2_J_r6_unfunded
rx_p2_J_r6_first_eop:
    ret
rx_p2_J_r6_unfunded:
    ret
rx_p2_J_r6:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r20
    rjmp rx_p2_J_r6_different
rx_p2_J_r6_missing_stuff:
    ret
rx_p0_K_r6_different:
    breq rx_p0_K_r6_first_zero
    nop
    rjmp rx_p1_J_r0
rx_p0_K_r6_first_zero:
    andi r19, 6
    breq rx_p0_K_r6_first_eop
    andi r17, 6
    breq rx_p0_K_r6_first_eop
    rjmp rx_p0_K_r6_unfunded
rx_p0_K_r6_first_eop:
    ret
rx_p0_K_r6_unfunded:
    ret
rx_p0_K_r6:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p0_K_r6_different
rx_p0_K_r6_missing_stuff:
    ret
rx_p1_K_r6_different:
    breq rx_p1_K_r6_first_zero
    nop
    nop
    rjmp rx_p2_J_r0
rx_p1_K_r6_first_zero:
    andi r19, 6
    breq rx_p1_K_r6_first_eop
    andi r17, 6
    breq rx_p1_K_r6_first_eop
    rjmp rx_p1_K_r6_unfunded
rx_p1_K_r6_first_eop:
    ret
rx_p1_K_r6_unfunded:
    ret
rx_p1_K_r6:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p1_K_r6_different
rx_p1_K_r6_missing_stuff:
    ret
rx_p2_K_r6_different:
    breq rx_p2_K_r6_first_zero
    nop
    nop
    rjmp rx_p0_J_r0
rx_p2_K_r6_first_zero:
    andi r19, 6
    breq rx_p2_K_r6_first_eop
    andi r17, 6
    breq rx_p2_K_r6_first_eop
    rjmp rx_p2_K_r6_unfunded
rx_p2_K_r6_first_eop:
    ret
rx_p2_K_r6_unfunded:
    ret
rx_p2_K_r6:
    in r16, 9
    andi r16, 6
    in r17, 9
    cpse r16, r21
    rjmp rx_p2_K_r6_different
rx_p2_K_r6_missing_stuff:
    ret
usb_control_process_received_packet:
bootloader_poll_begin:
bootloader_start_application:
    ret
