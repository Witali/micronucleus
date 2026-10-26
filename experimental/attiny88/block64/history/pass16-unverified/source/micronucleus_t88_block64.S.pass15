/* Micronucleus ATtiny88 16 MHz Block64 v3.3 fixed 8-byte GET_STATUS (Pass11) ASM.
 * BASED ON Optimized Micronucleus t88_default 16 MHz ATtiny88 bootloader, pass 3.
 * Assembler reconstruction of public Micronucleus firmware with conservative code-size
 * SRAM pointer reuse in V-USB with cycle-neutral sync-stage initialization.
 * RX/TX sampler and sender timings preserved by cycle tests; CRC-16 unchanged.
 * Source uses historical mnemonic labels; numeric names do NOT encode relocated addresses.
 * The normal AVR interrupt vector table is fully application-owned except RESET.
 * Page 0 updates erase the entire 64-byte page; only the rewritten RESET word
 * is forcibly redirected to Micronucleus. This is SOFTWARE protection, not
 * a power-failure-safe or hardware-locked RESET word.
 * Original Micronucleus contributors and modifications: GPL-2.0-or-later.
 */
#include "device_attiny88.inc"
#include "block64_protocol.inc"

.section .text
/* Edit BOOT_AT only after the build audits that the loader fits in flash. */
.org BOOT_AT
.global bootloader_start
bootloader_start:
    rjmp startup
/* Six-byte static status metadata and relocated standard USB descriptors. */
    .byte ((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff), T88_FLASH_PAGE_BYTES, T88_EEPROM_BYTES, BLOCK64_PROTO_MARKER, 0x03  /* six metadata bytes; live result/state in SRAM */
    .byte 0x09, 0x02, 0x12, 0x00, 0x01, 0x01, 0x00, 0x80  /* configuration descriptor */
    .byte 0x32, 0x09, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00  /* interface descriptor follows */
    .byte 0x00, 0x00, 0x12, 0x01, 0x10, 0x01, 0xff, 0x00  /* device descriptor follows */
    .byte 0x00, 0x08, 0xd0, 0x16, 0x53, 0x07, BLOCK64_VERSION_MINOR, BLOCK64_VERSION_MAJOR  /* VID/PID, bcdDevice=3.3 */
    .byte 0x00, 0x00, 0x00, 0x01  /* 1a6a */

startup:
    eor     r1, r1
#if !T88_ASSUME_RESET_STACK_INIT
    /* Needed only when entered through a software jump, not a hardware reset. */
    out     T88_IO_SREG, r1
    /* Optional software stack reinitialization if entered without RESET. */
    ldi     r28, (T88_RAMEND & 0xff)
    ldi     r29, (T88_RAMEND >> 8)
    out     T88_IO_SPL, r28
    out     T88_IO_SPH, r29
#endif
    /* Removed 0x1a7a: ldi     r18, 0x01 (size-optimized, see CHANGES.md) */
    ldi     r26, (T88_RAMSTART & 0xff)
    ldi     r27, (T88_RAMSTART >> 8)
    /* Removed 0x1a80: rjmp    L1a84 (size-optimized, see CHANGES.md) */

L1a82:
    st      X+, r1

L1a84:
    /* 0x0100..0x0139 includes USB variables AND Block64 state.
       The original limit 0x012C left the state machine uninitialized. */
    cpi     r26, 0x3a
    /* SRAM 0x0100..0x0139 is cleared, including both live status bytes. */
    brbc    1, L1a82
    /* X == 0x013A; preload constant tail once, not on every status poll. */
    ldi     r30, ((BOOT_AT + 2) & 0xff)
    ldi     r31, ((BOOT_AT + 2) >> 8)
    /* X begins at 0x013A: after six metadata bytes it reaches 0x0140. */
block_init_status_tail:
    lpm     r18, Z+
    st      X+, r18
    cpi     r26, 0x40
    brne    block_init_status_tail
    rjmp    main

/* Byte-exact AVR USB PHY (NRZI, stuffing, CRC16, packet ACK/NAK). */
#include "vusb_phy.inc"

main:
    wdr
    /* WDT unlock: WDCE|WDE=0x18 is sufficient regardless of the
       previous prescaler and interrupt settings. Next store, immediately,
       clears WDE/WDCE; timed sequence is unchanged. Saves four bytes. */
    ldi     r24, 0x18
    sts     T88_MEM_WDTCSR, r24
    sts     T88_MEM_WDTCSR, r1
    sbi     T88_IO_DDRD, 1
    /* 300.94 ms initial USB disconnect: 19 x 63355 inner loops.
       Previous 3000 x 400 countdown cost 4,815,001 cycles;
       this takes 4,815,056 cycles at 16 MHz (difference 55 cycles),
       two bytes less while preserving the USB disconnect duration. */
    ldi     r18, 19

L1d02:
    ldi     r24, (63355 & 0xff)
    ldi     r25, (63355 >> 8)

L1d06:
    sbiw    r24, 1
    brne    L1d06
    dec     r18
    brne    L1d02
    cbi     T88_IO_DDRD, 1
    ldi     r24, 0x5a
    sts     0x010f, r24
    ldi     r24, 0xff
    sts     0x0100, r24
    /* After reset both PCMSK2 and PCICR are zero.  Only PCINT18 / PCIE2
       are required: direct writes avoid redundant read-modify-write. */
    ldi     r24, 0x04
    sts     T88_MEM_PCMSK2, r24
    sts     T88_MEM_PCICR, r24
    /* Removed 0x1d30: sbi     0xa, 0 (size-optimized, see CHANGES.md) */
    mov     r7, r1
    mov     r3, r1
    mov     r5, r1
    mov     r4, r1

L1d3a:
    ldi     r28, 0xd5
    ldi     r29, 0x14
    ldi     r24, 0x64

L1d40:
    in      r25, 0x9
    andi    r25, 0x06
    brbs    1, L1d48
    ldi     r24, 0x64

L1d48:
    subi    r24, 0x01
    brbc    1, L1d54
    sts     0x0113, r1
    sts     0x010c, r1

L1d54:
    sbis    T88_IO_PCIFR, 2
    rjmp    L1e98
    rcall   USB_handler
    sbi     T88_IO_PCIFR, 2  /* PCIFR.PCIF2 W1C; reset PCMSK0/1/3 stay zero.
                        SBI is 2 cycles vs LDI+OUT 2 cycles. */

L1d5e:
    wdr
    /* Common IDLE/DONE/ERROR path bypasses RCALL/RET altogether.
       On active operations the preloaded state r18 is reused below. */
    ldi     r28, 0x00
    ldi     r29, 0x01
    ldd     r18, Y+57
    cpi     r18, ST_RUN
    brlo    L1d9c
    rcall   block_memory_service

/* Examine a staged USB packet; SETUP and DATA OUT have distinct handlers. */
/* Control endpoint zero: SETUP/OUT, 8-byte DATA packetization. */
#include "vusb_ep0.inc"

L1e64:
    movw    r24, r6
    adiw    r24, 1
    movw    r6, r24
    subi    r24, 0xb0
    sbci    r25, 0x04
    brne    L1e7c
    ldd     r18, Y+57
    cpi     r18, ST_IDLE
    brne    L1e7c
    ldi     r30, ((BOOT_AT - 3) & 0xff)
    ldi     r31, ((BOOT_AT - 3) >> 8)
    lpm     r30, Z
    cpi     r30, 0xff
    brne    L1eac

L1e7c:
    /* Removed 0x1e7c: andi    r24, 0x4c (size-optimized, see CHANGES.md) */
    /* Removed 0x1e7e: brbc    1, L1e82 (size-optimized, see CHANGES.md) */
    /* Removed 0x1e80: rjmp    L1f82 (size-optimized, see CHANGES.md) */

L1e82:
    /* Removed 0x1e82: cbi     0xb, 0 (size-optimized, see CHANGES.md) */

L1e84:
    sbis    T88_IO_PCIFR, 2
    rjmp    L1d3a
    ldi     r24, 0x1c

L1e8a:
    sbis    T88_IO_PIND, 1
    ldi     r24, 0x1c
    subi    r24, 0x01
    brbc    1, L1e8a
    sbi     T88_IO_PCIFR, 2  /* PCIFR.PCIF2 W1C; reset PCMSK0/1/3 stay zero.
                        SBI is 2 cycles vs LDI+OUT 2 cycles. */
    rjmp    L1d3a

L1e98:
    sbiw    r28, 1
    brbs    1, L1e9e
    rjmp    L1d40

L1e9e:
    /* Only an expired quiet polling interval may start a blocking SPM.
       After the host has seen the USB status stage it must pause before
       issuing another request. No code in USB_handler has been changed. */
    rcall   block_spm_after_quiet
    rjmp    L1d5e

L1eac:
    /* Removed 0x1eac: cbi     0xb, 0 (size-optimized, see CHANGES.md) */
    out     T88_IO_DDRD, r1
    sts     T88_MEM_PCICR, r1
    sts     T88_MEM_PCMSK2, r1
    in      r24, 0x34
    out     T88_IO_GPIOR0, r24
    out     T88_IO_MCUSR, r1
app_jump:
    .word (0xc000 | (((bootloader_start - 4 - app_jump - 2)/2) & 0x0fff)) /* relative RJMP into application postscript */

/* ------------------ Unified 1..64 byte memory protocol -----------------
 * USB low-speed endpoint zero carries 8 bytes per DATA packet.
 * Control transfer wLength=1..64 uses repeated DATA0/DATA1 packets.
 * The low-level NRZI RX/TX and USB packet CRC implementation is untouched.
 * Vendor IN: READ=0x10, GET_STATUS=0x12 (always request 8 bytes, no 0x20 INFO).
 * Vendor OUT: WRITE=0x11, RUN=0x13.
 * wValue=16-bit byte address, wIndex=memory (0 Flash, 1 EEPROM).
 * Flash WRITE is exactly 64 bytes, aligned at 64. ERASE_PAGE is distinct.
 * Partial Flash writes are host-side read/modify/write of full pages.
 * SPM is deferred until after USB status TX and a quiet polling interval.
 * No legacy SPI or old Micronucleus vendor opcodes are accepted.
 */
block_vendor_dispatch:
    ldd     r18, Y+23         /* vendor bmRequestType */
    cpi     r18, 0xc0
    breq    block_vendor_in
    cpi     r18, 0x40
    brne    block_vendor_reject
block_vendor_out:
    cpi     r25, OP_WRITE
    breq    block_write_setup
    cpi     r25, OP_RUN
    breq    block_run
    cpi     r25, OP_ERASE_PAGE
    breq    block_erase_setup
block_vendor_reject:
    rjmp    block_reject
block_vendor_in:
    cpi     r25, OP_GET_STATUS
    breq    block_status
    cpi     r25, OP_READ
    breq    block_read_setup
    /* Do not chain two RJMP instructions through block_vendor_reject. */
    rjmp    block_reject

/* Live SRAM response overlay at 0x0138:
 * [last_result, state, app_hi, app_lo, page_bytes, eeprom_bytes,
 *  protocol_minor (0x33), feature_flags (0x03)].
 * The six constant bytes are initialized exactly once after reset.
 * GET_STATUS has one supported form: host wLength=8 on every request.
 * Generic EP0 still clamps any malformed shorter wLength to preserve USB
 * data-stage correctness. No extra per-command length path is needed. */
/* ERASE_PAGE uses a zero-length Vendor OUT control request.
   Host is responsible for waiting for completion before WRITE_PAGE.
   Must not erase any bootloader byte; 0x1980 is the final writable page
   for BOOT_AT=0x19C0 (other layouts derive it from BOOT_AT). */
block_erase_setup:
    /* ERASE has wLength=0. Reuse the common page bounds checker by
       temporarily validating a full 64-byte page, then restore wLength. */
    ldd     r18, Y+29
    tst     r18                  /* length high byte checked by shared validator */
    brne    block_vendor_reject
    ldi     r24, 64              /* validate one complete Flash page */
    rcall   block_validate_page_range
    brcc    block_vendor_reject
    mov     r18, r22
    andi    r18, 0x3f
    or      r18, r16             /* both page offset and memory type must be zero */
    brne    block_vendor_reject
    ldi     r17, ST_FLASH_WAIT_PREP
    ldi     r18, RESULT_BUSY
    std     Y+54, r18  /* 1=erase, 0=page-write */
    mov     r24, r1     /* Zero-length status response */
    rjmp    block_begin_mutation


block_status:
    /* Fixed 8-byte reply. Generic EP0 limiting remains for USB correctness. */
    ldi     r18, 0x38
    ldi     r19, 0x81            /* SRAM pointer marker: 0x0138 */
    ldi     r24, BLOCK64_STATUS_BYTES
    rjmp    L1f22

block_run:
    /* Only run when EEPROM/Flash modification is fully complete. */
    ldd     r18, Y+57
    cpi     r18, ST_ERROR /* 0=IDLE, 1=DONE allow run; others reject */
    brsh    block_reject
block_run_ready:
    ldi     r18, ST_RUN
    std     Y+57, r18
    ldi     r24, 0
    rjmp    L1de2

/* Both READ and WRITE share validation. Valid 1..64 byte counts;
   Flash bound is BOOT_AT (includes 4-byte reset postscript for host);
   EEPROM bound is 64 bytes. No wraparound is permitted. */
block_read_setup:
    rcall   block_validate_range
    brcc    block_reject
    /* Common range validator also enforces the idle/EEPROM-ready interlock. */
block_read_range_ok:
    /* r16=memory type; r22:r23=start address; r24=request size. */
    tst     r16
    breq    block_read_flash
    /* EEPROM-busy test is shared with block_check_idle_for_write. */
    /* Snapshot EEPROM to 64-byte SRAM buffer before starting DATA IN. */
    ldi     r26, 0x40
    ldi     r27, 0x01
    mov     r20, r24
    /* r22 is disposable here and already contains the EEPROM address. */
    /* EEPROM is idle and EECR uses erase/write mode with no ready IRQ.
       Preload the EERE strobe once; OUT is one cycle vs SBI's two.
       This changes EERE only, and all other EECR bits are deliberately 0. */
    /* The range validator guarantees memory-type r16 == 1 here, so it
       doubles as the EEPROM read strobe without loading another register. */
block_snapshot_eeprom_loop:
    out     T88_IO_EEARL, r22
    out     T88_IO_EECR, r16
    in      r18, 0x20
    st      X+, r18
    inc     r22
    dec     r20
    brne    block_snapshot_eeprom_loop
    ldi     r18, 0x40
    ldi     r19, 0x81    /* marker: SRAM 0x0140 */
    rjmp    L1f22

block_read_flash:
    movw    r18, r22
    rjmp    L1f22

block_write_setup:
    rcall   block_validate_range
    brcc    block_write_bad
    /* Host must send an entire aligned Flash page, never a fragment.
       EEPROM still accepts 1..64 bytes. */
    tst     r16
    brne    block_write_validated
    mov     r17, r22
    andi    r17, 0x3f
    brne    block_write_bad
    cpi     r24, 64
    brne    block_write_bad
block_write_validated:
    std     Y+48, r16
    std     Y+51, r24
    std     Y+54, r1
    ldi     r17, 0x4b            /* USB DATA1 first after SETUP */
    std     Y+55, r17
    std     Y+52, r1
    ldi     r24, EMPTY_MESSAGE
    ldi     r17, ST_RECEIVE
block_begin_mutation:
    /* Common init: state, address and BUSY status for ERASE and WRITE. */
    std     Y+57, r17
    std     Y+49, r22
    std     Y+50, r23
    ldi     r18, RESULT_BUSY
    std     Y+56, r18
    std     Y+0, r24
    rjmp    L1df8
block_write_bad:
block_reject:
    /* A malformed or overlapping command may not cancel an in-progress
       operation; otherwise a hostile SETUP could interrupt a pending SPM. */
    ldd     r18, Y+57
    cpi     r18, ST_RECEIVE
    brsh    block_reject_no_state
    /* Both RESULT_BOUNDS and ST_ERROR are value 2. */
    ldi     r18, RESULT_BOUNDS
    std     Y+56, r18
    std     Y+57, r18
block_reject_no_state:
    /* Every vendor command reaches here only after the standard SETUP
       dispatcher has already set CTX_MSG_LENGTH to EMPTY_MESSAGE.
       No reply was queued on a rejected path. */
    rjmp    L1df8


/* Validate wValue+wLength against selected memory bounds. Carry set
 * on success; r16 type, r22:r23 address, r24 length; r18:r19 scratch. */
block_validate_range:
    ldd     r24, Y+29
    tst     r24
    breq    block_invalid_range
    cpi     r24, 65
    brsh    block_invalid_range
block_validate_page_range:
    /* Caller supplied 1..64 (ERASE uses 64 even though USB wLength=0). */
    ldd     r16, Y+27
    ldd     r18, Y+28
    ldd     r19, Y+30
    or      r18, r19
    brne    block_invalid_range
    cpi     r16, 2
    brsh    block_invalid_range
    ldd     r22, Y+25
    ldd     r23, Y+26
    /* Avoid 17-bit address+length arithmetic: compare address <= bound-length.
       Both memory bounds are >=64, and 1<=length<=64 was checked above. */
    /* Select the exclusive end: EEPROM=64, Flash=BOOT_AT. */
    ldi     r20, 64
    ldi     r21, 0
    tst     r16
    brne    block_check_selected_bound
#if (BOOT_AT & 0xff) != 64
    ldi     r20, (BOOT_AT & 0xff)
#endif
    ldi     r21, (BOOT_AT >> 8)
block_check_selected_bound:
    sub     r20, r24
    sbc     r21, r1
    cp      r20, r22
    cpc     r21, r23
    brcs    block_invalid_range
block_valid_range:
block_check_idle_for_write:
    /* C=1 for allowed address and idle EEPROM/Flash.  Fall through
       instead of dispatching through RCALL/RET or an RJMP. */
    ldd     r17, Y+57
    cpi     r17, ST_RUN
    brsh    block_idle_return
    sbic    T88_IO_EECR, 1
    clc
block_idle_return:
    ret
block_invalid_range:
    clc
    ret

/* One incoming OUT DATA0/1 packet containing 1..8 payload bytes.
 * RX data already ACKed by USB_handler; buffer stays NAK until consumed.
 */
block_accept_out:
    ldd     r18, Y+57
    cpi     r18, ST_RECEIVE
    brne    block_out_return
    /* ACK may have been lost at the host; ignore repeated DATA0/DATA1. */
    ldd     r17, Y+22            /* received PID */
    ldd     r18, Y+55
    cp      r17, r18
    brne    block_out_return
    /* r24 = rxLength - 3, valid length 1..8 and <= remaining */
    tst     r24
    breq    block_out_return
    cpi     r24, 9
    brsh    block_out_return
    /* Verify DATA CRC16 using the same 44-byte V-USB CRC routine.
       This runs AFTER the hardware-timed packet ACK, outside USB sampling.
       Discard corrupted payload and force a host timeout rather than
       silently writing Flash/EEPROM. */
    mov     r23, r24
    ldi     r26, 0x17
    ldi     r27, 0x01
    add     r26, r23
    ld      r16, X+            /* received CRC low */
    ld      r17, X             /* received CRC high */
    ldi     r24, 0x17
    ldi     r25, 0x01
    mov     r22, r23
    rcall   usb_crc16_append
    cp      r24, r16
    cpc     r25, r17  /* combine 16-bit equality with propagated Z */
    brne    block_out_return
    /* Subtraction both checks packet count and updates bytes remaining. */
    ldd     r18, Y+51
    sub     r18, r23
    brcs    block_out_return
    std     Y+51, r18
    /* Z tracks both destination and new received-byte count. */
    ldi     r26, 0x17            /* RX payload at 0x0117 */
    /* XH remains 0x01 after usb_crc16_append (at most 8+2 byte steps). */
    ldd     r30, Y+52
    subi    r30, 0xc0            /* add MEM_BUFFER low-byte (0x40) */
    ldi     r31, 0x01
block_out_copy_byte:
    ld      r20, X+
    st      Z+, r20
    dec     r23
    brne    block_out_copy_byte
    subi    r30, 0x40            /* convert pointer back into count */
    std     Y+52, r30
    ldd     r17, Y+55
    ldi     r20, 0x88            /* DATA0/DATA1 PID XOR mask */
    eor     r17, r20
    std     Y+55, r17
    tst     r18
    brne    block_out_return
    /* Received full wLength. Queue asynchronous memory commit. */
    /* For type 0/1 select 6=FLASH_WAIT_PREP or 5=WRITE_EEPROM. */
    ldd     r17, Y+48
    ldi     r20, ST_FLASH_WAIT_PREP
    sub     r20, r17
    std     Y+57, r20
    tst     r17
    brne    block_out_return
    /* The last FLASH DATA OUT byte queues the status-stage ZLP. */
    std     Y+0, r1
block_out_return:
    rjmp    L1df8 /* Tail-dispatch into the existing EP0 release path. */

/* Called from main loop, never within the cycle-critical USB packet engine.
 * EEPROM programming progresses one byte whenever EEPE clears. Flash
 * erase/fill/write executes only after the entire control OUT payload.
 */
/* The active states enter with Y=0x0100 and r18=MEM_STATE preloaded.
   The shared service_return is the RET at end of block_complete_flash. */
block_memory_service:
    cpi     r18, ST_WRITE_EEPROM
    breq    block_step_eeprom
    cpi     r18, ST_RUN
    brne    block_memory_service_return
    ldd     r18, Y+15
    cpi     r18, EP0_NAK
    brne    block_memory_service_return
    rjmp    L1eac

block_memory_service_return:
    ret

block_step_eeprom:
    sbic    T88_IO_EECR, 1           /* EEPE active? */
    ret
    ldd     r18, Y+54
    ldd     r19, Y+52  /* Once EEPROM RX completes, MEM_INDEX equals total. */
    cp      r18, r19
    breq    block_complete
block_eeprom_more_bytes:
    ldd     r20, Y+49
    add     r20, r18
    ldi     r30, 0x40
    add     r30, r18
    ldi     r31, 0x01
    ld      r21, Z
    out     T88_IO_EEARL, r20         /* EEARL */
    out     T88_IO_EEDR, r21         /* EEDR */
    /* EEDR's old r21 value is no longer needed. Set EEMPE using one-cycle
       OUT instead of OUT+SBI; the subsequent two-cycle SBI(EEPE) meets
       the <=4-cycle window. Mode EEPM=00 and interrupt EERIE=0. */
    ldi     r21, (1 << 2)
    out     T88_IO_EECR, r21
    sbi     T88_IO_EECR, 1
    inc     r18
    std     Y+54, r18
    ret

block_complete:
    /* Finish EEPROM control-OUT with a ZLP; Flash finishes separately. */
    std     Y+0, r1
    rjmp    block_complete_flash

/* This hook runs only when the main USB polling window has expired.
   The control OUT status ZLP must have been physically emitted first,
   i.e. its TX length returned to EP0_NAK. The host waits after the
   successful control transfer, because ATtiny88 stalls during SPM. */
block_spm_after_quiet:
    ldi     r28, 0x00
    ldi     r29, 0x01
    ldd     r18, Y+57
    cpi     r18, ST_SPM_WAIT_SENT
    brne    block_service_return
    ldd     r18, Y+15
    cpi     r18, EP0_NAK
    brne    block_service_return
    ldd     r18, Y+54
    tst     r18
    breq    block_commit_flash

block_flash_erase_only:
    /* Share page-address setup, SPMCSR write and SPM with WRITE_PAGE.
       No extra delay between OUT SPMCSR and SPM. */
    ldi     r18, 0x03
    rjmp    block_execute_spm

block_commit_flash:
    /* Same interlock as standalone ERASE_PAGE, no duplicate EEPE check. */
    rcall   block_load_page_z
    /* Patch ONLY 0x0000..0x0001 on page 0. Leave 0x0002..0x003f
       exactly as supplied by the application, including all ISR vectors.
       This does NOT keep RESET valid between ERASE_PAGE and WRITE. */
    sbiw    r30, 0         /* Test page-zero address without a scratch register. */
    brne    block_flash_fill_start
    ldi     r26, 0x40
    ldi     r27, 0x01
    ldi     r18, (RESET_RJMP & 0xff)
    st      X+, r18
    ldi     r18, (RESET_RJMP >> 8)
    st      X, r18
block_flash_fill_start:
    /* Clear stale hardware page buffer. Page erase was a separate call. */
    ldi     r18, 0x11
    out     T88_IO_SPMCSR, r18        /* CTPB|SELFPRGEN */
    spm
    ldi     r26, 0x40
    ldi     r27, 0x01
    /* X advances from 0x0140 to 0x0180 after exactly 32 word loads. */
    ldi     r18, 0x01
block_flash_fill_word:
    ld      r0, X+
    ld      r1, X+
    out     T88_IO_SPMCSR, r18
    spm
    /* The 64-byte page is aligned: only the low six Z bits select a word.
       SUBI adds 2 in one cycle, whereas ADIW costs two. An overflow of
       ZL can happen only after the *last* word of a page at xxC0; Z is
       reloaded before PAGE WRITE, so ZH need not be incremented here. */
    subi    r30, 0xfe
    cpi     r26, 0x80
    brne    block_flash_fill_word
    clr     r1
    ldi     r18, 0x05
block_execute_spm:
    /* Hardware requires page-aligned Z for both erase and write. */
    rcall   block_load_page_z
    out     T88_IO_SPMCSR, r18
    spm
    /* Fall through into shared completion; no second USB status. */

block_complete_flash:
    /* The control transfer has already completed; never queue another ZLP. */
    std     Y+56, r1
    ldi     r18, ST_DONE
    std     Y+57, r18
block_service_return:
    ret

/* Standard USB Chapter 9 request handlers (not Block64 vendor commands). */
#include "vusb_standard.inc"

/* Shared non-USB address builder for both Flash SPM operations and
   the page-buffer refill. Saves 4 bytes despite RCALL/RET overhead.
   Must execute before SPMCSR timing-critical write, not after it. */
block_load_page_z:
    ldd     r30, Y+49
    andi    r30, 0xc0
    ldd     r31, Y+50
    ret
