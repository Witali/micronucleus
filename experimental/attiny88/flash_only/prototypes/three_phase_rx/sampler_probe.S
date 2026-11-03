/* Test fixture only: ordinary three-phase sampling, with RET stubs for
 * missing stuffing/EOP continuations. No publication or USB device startup. */
    .text
    .org BOOT_AT
    .global bootloader_start
bootloader_start:
USB_handler:
raw_loop_phase0:
    in r17, 9
    andi r17, 6
    in r19, 9
    breq raw_loop_eop
    eor r16, r17
    andi r16, 6
    subi r16, 1
    ror r18
    cpi r18, 0xfc
    brcc raw_loop_stuff0
raw_loop_phase1:
    in r16, 9
    andi r16, 6
    in r17, 9
    breq raw_loop_eop
    eor r19, r16
    andi r19, 6
    subi r19, 1
    ror r18
    cpi r18, 0xfc
    brcs raw_loop_phase2
raw_loop_stuff1:
    ret
raw_loop_phase2:
    in r19, 9
    andi r19, 6
    in r16, 9
    breq raw_loop_eop
    eor r17, r19
    andi r17, 6
    subi r17, 1
    ror r18
    cpi r18, 0xfc
    brcs raw_loop_phase0
raw_loop_stuff2:
    ret
raw_loop_stuff0:
    ret
raw_loop_eop:
usb_control_process_received_packet:
bootloader_poll_begin:
bootloader_start_application:
    ret
