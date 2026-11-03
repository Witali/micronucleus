/* Private PC-typed lookahead entry schedule. No full loader behavior.
 * Actual-five callers enter typed_five_setup at FIRST-1 or typed_five_entry
 * directly at FIRST. The actual-six caller enters typed_six_entry at FIRST.
 * These classes are supplied by the caller's control path, never inferred
 * from the retained payload/history byte. T at the clock 32 join is zero
 * for the DATA-zero path, one after newly consuming a mandatory zero.
 * A full replacement must reconstruct the existing PID-family T discriminator
 * from its stored PID before using the old combined-RX EOF classifier. */
    .text
    .org BOOT_AT
    .global bootloader_start
typed_six_entry:
    in r17, 9                 /* 0: separate capture prefix for actual-six */
    andi r17, 6               /* 1 */
    in r19, 9                 /* 2 */
    breq prior_six_zero       /* 3 ->zero-symbol check at5 */
    rjmp prior_six            /* 4 ->transition check at6 */
prior_six:
    eor r16, r17
    andi r16, 6
    breq rejected
prior_six_consumed:
    ret
prior_six_zero:
    andi r19, 6
    breq rejected
prior_six_zero_consumed:
    ret
rejected:
    ret
initial_eop:
    ret
bootloader_start:
USB_handler:
prearm_entry:
typed_five_setup:
    nop                       /* FIRST-1: caller already proved actual-five */
typed_five_entry:
first_phase0:
    in r17, 9                 /* 0 */
    andi r17, 6               /* 1 */
    in r19, 9                 /* 2 */
    breq first_zero           /* 3 */
    bst r1, 0                 /* 4: T0 = no newly consumed stuffed zero */
    eor r16, r17              /* 5 */
    andi r16, 6               /* 6 */
    subi r16, 1               /* 7 */
    brcc data_zero_pending    /* 8 */
shift_sixth_one:
    ror r18                   /* 9 */
first_stuffed_phase1:
    in r16, 9                 /* 10, rather than the old late11 */
    andi r16, 6               /* 11 */
    in r17, 9                 /* 12 */
    breq stuffed_first_zero   /* 13 */
    eor r19, r16              /* 14 */
    andi r19, 6               /* 15 */
    breq rejected             /* 16 */
    bst r18, 7                /* 17: proved sixth DATA one supplies T1 */
    nop                       /* 18 */
    rjmp next_phase2          /* 19 ->FIRST21 */
stuffed_first_zero:
    andi r17, 6               /* 15 */
    breq rejected             /* 16 */
    bst r18, 7                /* 17: proved sixth DATA one supplies T1 */
    nop                       /* 18 */
    rjmp next_phase2          /* 19 ->FIRST21 */
first_zero:
    bst r1, 0                 /* 5: same T0 on recovered-FIRST-zero */
    andi r19, 6               /* 6 */
    breq initial_eop          /* 7 */
    rjmp data_zero_pending    /* 8 ->FIRST10 */
data_zero_pending:
    in r16, 9                 /* 10 */
shift_pending_zero:
    lsr r18                   /* 11: retire the preceding real DATA zero */
    in r17, 9                 /* 12 */
    andi r16, 6               /* 13 */
    breq pending_first_zero   /* 14 */
    eor r19, r16              /* 15 */
    andi r19, 6               /* 16 */
    subi r19, 1               /* 17 */
shift_following_phase1:
    ror r18                   /* 18 */
    rjmp next_phase2          /* 19 ->FIRST21 */
pending_first_zero:
    andi r17, 6               /* 16 */
    breq pending_eop          /* 17 */
shift_following_zero:
    lsr r18                   /* 18 */
    rjmp next_phase2          /* 19 */
pending_eop:
    ret
next_phase2:
    in r19, 9                 /* 21 */
    andi r19, 6               /* 22 */
    in r16, 9                 /* 23 */
    breq phase2_first_zero    /* 24 */
    eor r17, r19              /* 25 */
    andi r17, 6               /* 26 */
    subi r17, 1               /* 27 */
shift_phase2:
    ror r18                   /* 28 */
    nop                       /* 29 */
    rjmp joined_next_phase0   /* 30 ->FIRST32 */
phase2_first_zero:
    andi r16, 6               /* 26 */
    breq phase2_eop           /* 27 */
shift_phase2_zero:
    lsr r18                   /* 28 */
    nop                       /* 29 */
    rjmp joined_next_phase0   /* 30 */
phase2_eop:
    ret
joined_next_phase0:
    ret
usb_control_process_received_packet:
bootloader_poll_begin:
bootloader_start_application:
    ret
