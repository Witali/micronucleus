from pathlib import Path
P=Path(__file__).resolve().parent.parent
src=(P/'reference/previous_bulk8_1344.S').read_text()
src=src.replace('Micronucleus ATtiny88 16 MHz ASM + EEPROM + bounded Flash read.', 'Micronucleus ATtiny88 16 MHz Block64 v3.0 ASM: Flash/EEPROM 1..64B read/write.')
# New major version intentionally refuses the legacy host application protocol.
src=src.replace('#define BOOT_AT 0x1ac0','#define BOOT_AT 0x1980')
src=src.replace('0x93, 0x11, 0xe0, 0x00','0x93, 0x11, 0xe1, 0x00')
src=src.replace('0x00, 0x08, 0xd0, 0x16, 0x53, 0x07, 0x10, 0x02','0x00, 0x08, 0xd0, 0x16, 0x53, 0x07, 0x00, 0x03')
newdefs='''
/* Block64 protocol v3.0 (incompatible with old Micronucleus CLI). */
#define MEM_STATE 0x0130
#define MEM_TYPE 0x0131
#define MEM_ADDR_LO 0x0132
#define MEM_ADDR_HI 0x0133
#define MEM_REMAIN 0x0134
#define MEM_INDEX 0x0135
#define MEM_TOTAL 0x0136
#define MEM_STATUS 0x0137
#define MEM_PROGRESS 0x0138
#define MEM_EXPECT_PID 0x0139  /* USB DATA1 after SETUP, toggles per accepted OUT */
#define MEM_BUFFER 0x0140   /* one 64-byte SRAM page, 0x0140-0x017f */
#define ST_IDLE 0
#define ST_RECEIVE 1
#define ST_WRITE_EEPROM 2
#define ST_WRITE_FLASH 3
#define ST_DONE 4
#define ST_RUN 5
#define ST_ERROR 6
#define OP_READ 0x10
#define OP_WRITE 0x11
#define OP_STATUS 0x12
#define OP_RUN 0x13
#define OP_INFO 0x20
#define MEM_FLASH 0
#define MEM_EEPROM 1
#define RESULT_OK 0
#define RESULT_BUSY 1
#define RESULT_BOUNDS 2
#define RESULT_FAIL 3
#define EP0_NAK 0x5a
#define EMPTY_MESSAGE 0xff
#define EP0_MAX_PACKET 8
#define BLOCK_MAX 64
#define RESET_RJMP (0xc000 | (((BOOT_AT/2)-1) & 0x0fff))
'''
src=src.replace('.section .text\n',newdefs+'\n.section .text\n',1)
# main code: remove old Flash erase/write dispatch and add memory service.
start=src.index('usb_program_page:\n')
stop=src.index('main:\n',start)
src=src[:start]+src[stop:]
start=src.index('L1d5e:\n')
stop=src.index('L1de2:\n',start)
src=src[:start]+'''L1d5e:
    wdr
    rcall   block_memory_service

/* Examine a staged USB packet; SETUP and DATA OUT have distinct handlers. */
L1d9c:
    ldi     r28, 0x00
    ldi     r29, 0x01
    ldd     r24, Y+18
    subi    r24, 3
    brmi    L1dfc
    ldd     r25, Y+13
    cpi     r25, 0xe1            /* OUT token, DATA0/1 already decoded */
    breq    block_out_packet
    cpi     r25, 0x2d            /* SETUP token */
    brne    L1df8
    cpi     r24, 8
    brne    L1df8
    mov     r7, r1               /* extend inactivity timeout */
    ldi     r24, 0xc3            /* initialize DATA0, TX toggle -> DATA1 */
    std     Y+1, r24
    ldi     r24, EP0_NAK
    std     Y+15, r24
    ldi     r24, EMPTY_MESSAGE
    std     Y+0, r24             /* do not send reply until prepared */
    ldd     r24, Y+23            /* bmRequestType */
    andi    r24, 0x60
    ldd     r25, Y+24            /* bRequest */
    breq    block_standard_setup
    rjmp    block_vendor_dispatch
block_standard_setup:
    rjmp    old_vendor_dispatch

block_out_packet:
    rcall   block_accept_out
    rjmp    L1df8

''' + src[stop:]
# Replace TX memcpy logic only, leave USB_handler unchanged.
start=src.index('    ldd     r30, Y+16\n',src.index('L1dfc:\n'))
stop=src.index('L1e4c:\n',start)
src=src[:start]+'''    ldd     r30, Y+16
    ldd     r31, Y+17
    /* 0x810a denotes a prefilled 8-byte EP0 reply; skip copying. */
    sbrs    r31, 7
    rjmp    tx_copy_flash_start
    cpi     r30, 0x0a
    breq    L1e4c
    /* 0x81xx encodes a real SRAM source. Clear marker before LD. */
    andi    r31, 0x7f
    ldi     r26, 0x02
    ldi     r27, 0x01
    mov     r24, r23

tx_copy_sram_loop:
    ld      r25, Z+
    st      X+, r25
    dec     r24
    brne    tx_copy_sram_loop
    ori     r31, 0x80            /* persist SRAM marker */
    rjmp    tx_update_source_pointer

tx_copy_flash_start:
    ldi     r26, 0x02
    ldi     r27, 0x01
    mov     r24, r23
L1e3a:
    lpm     r25, Z+
    st      X+, r25
    dec     r24
    brne    L1e3a

tx_update_source_pointer:
    std     Y+17, r31
    std     Y+16, r30

''' + src[stop:]
# Prevent auto exit while processing non-idle memory operations.
start=src.index('L1e64:\n')
stop=src.index('L1e7c:\n',start)
src=src[:start]+'''L1e64:
    movw    r24, r6
    adiw    r24, 1
    movw    r6, r24
    subi    r24, 0xb0
    sbci    r25, 0x04
    brne    L1e7c
    lds     r18, MEM_STATE
    cpi     r18, ST_IDLE
    brne    L1e7c
    ldi     r30, ((BOOT_AT - 3) & 0xff)
    ldi     r31, ((BOOT_AT - 3) >> 8)
    lpm     r30, Z
    cpi     r30, 0xff
    brne    L1eac

''' + src[stop:]
# replace old protocol dispatch following app_jump with new, standard USB code kept from old fallback
start=src.index('L1ec0:\n')
std=src[src.index('old_vendor_dispatch:\n'):src.index('/* ---------------- EEPROM operations')]
# common EEPROM/Flash protocol does not need historical old 'Micronucleus' vendor commands;
# standard GET_STATUS/GET_DESCRIPTOR etc remain as before.
newlogic='''/* ------------------ Unified 1..64 byte memory protocol -----------------
 * USB low-speed endpoint zero carries 8 bytes per DATA packet.
 * Control transfer wLength=1..64 uses repeated DATA0/DATA1 packets.
 * The low-level NRZI RX/TX and USB packet CRC implementation is untouched.
 * Vendor IN:  READ=0x10, STATUS=0x12, INFO=0x20.
 * Vendor OUT: WRITE=0x11, RUN=0x13.
 * wValue=16-bit byte address, wIndex=memory (0 Flash, 1 EEPROM).
 * For Flash writes, address+len MUST remain within a single 64-byte page.
 * A partial Flash write preserves the other bytes in that page (RMW).
 * No legacy SPI or old Micronucleus vendor opcodes are accepted.
 */
block_vendor_dispatch:
    ldd     r18, Y+23         /* complete bmRequestType (IN/OUT) */
    cpi     r18, 0xc0
    breq    block_vendor_in
    cpi     r18, 0x40
    breq    block_vendor_out
    rjmp    block_reject

block_vendor_in:
    cpi     r25, OP_INFO
    breq    block_info
    cpi     r25, OP_STATUS
    breq    block_status
    cpi     r25, OP_READ
    breq    block_read_setup
    rjmp    block_reject

block_vendor_out:
    cpi     r25, OP_WRITE
    breq    block_write_setup
    cpi     r25, OP_RUN
    breq    block_run
    rjmp    block_reject

block_info:
    ldi     r18, ((BOOT_AT + 2) & 0xff)
    ldi     r19, ((BOOT_AT + 2) >> 8)
    ldi     r24, 8
    rjmp    L1f22

block_status:
    lds     r18, MEM_STATUS
    std     Y+2, r18
    ldi     r24, 1
    rjmp    L1f34

block_run:
    /* Only run when EEPROM/Flash modification is fully complete. */
    lds     r18, MEM_STATE
    cpi     r18, ST_IDLE
    breq    block_run_ready
    cpi     r18, ST_DONE
    breq    block_run_ready
    rjmp    block_reject
block_run_ready:
    ldi     r18, ST_RUN
    sts     MEM_STATE, r18
    ldi     r24, 0
    rjmp    L1de2

/* Both READ and WRITE share validation. Valid 1..64 byte counts;
   Flash bound is BOOT_AT (includes 4-byte reset postscript for host);
   EEPROM bound is 64 bytes. No wraparound is permitted. */
block_read_setup:
    rcall   block_validate_range
    brcs    block_read_range_ok
    rjmp    block_reject
block_read_range_ok:
    /* r16=memory type; r22:r23=start address; r24=request size. */
    tst     r16
    breq    block_read_flash
    sbic    0x1f, 1
    rjmp    block_reject
    /* Snapshot EEPROM to 64-byte SRAM buffer before starting DATA IN. */
    ldi     r26, 0x40
    ldi     r27, 0x01
    mov     r20, r24
    mov     r17, r22
block_snapshot_eeprom_loop:
    out     0x21, r17
    sbi     0x1f, 0
    in      r18, 0x20
    st      X+, r18
    inc     r17
    dec     r20
    brne    block_snapshot_eeprom_loop
    ldi     r18, 0x40
    ldi     r19, 0x81    /* marker: SRAM 0x0140 */
    rjmp    L1f22

block_read_flash:
    mov     r18, r22
    mov     r19, r23
    rjmp    L1f22

block_write_setup:
    rcall   block_validate_range
    brcc    block_reject
    /* Flash write must not cross a hardware page. */
    tst     r16
    brne    block_write_validated
    mov     r17, r22
    andi    r17, 0x3f
    add     r17, r24
    cpi     r17, 65
    brsh    block_reject
block_write_validated:
    /* Reject concurrent write or an EEPROM controller still busy. */
    lds     r17, MEM_STATE
    cpi     r17, ST_RECEIVE
    breq    block_reject
    cpi     r17, ST_WRITE_EEPROM
    breq    block_reject
    cpi     r17, ST_WRITE_FLASH
    breq    block_reject
    sbic    0x1f, 1
    rjmp    block_reject
    ldi     r17, ST_RECEIVE
    sts     MEM_STATE, r17
    sts     MEM_TYPE, r16
    sts     MEM_ADDR_LO, r22
    sts     MEM_ADDR_HI, r23
    sts     MEM_REMAIN, r24
    sts     MEM_TOTAL, r24
    clr     r17
    sts     MEM_PROGRESS, r17
    ldi     r17, 0x4b            /* USB DATA1 first after SETUP */
    sts     MEM_EXPECT_PID, r17
    ldi     r17, RESULT_BUSY
    sts     MEM_STATUS, r17
    /* For Flash, cache entire existing 64-byte page in RAM. */
    tst     r16
    brne    block_write_eeprom_pointer
    mov     r30, r22
    andi    r30, 0xc0
    mov     r31, r23
    ldi     r26, 0x40
    ldi     r27, 0x01
    ldi     r20, 64
block_cache_flash_loop:
    lpm     r18, Z+
    st      X+, r18
    dec     r20
    brne    block_cache_flash_loop
    mov     r17, r22
    andi    r17, 0x3f
    rjmp    block_write_store_pointer
block_write_eeprom_pointer:
    clr     r17
block_write_store_pointer:
    sts     MEM_INDEX, r17
    ldi     r17, EMPTY_MESSAGE
    std     Y+0, r17         /* NAK status until data commit completes */
    rjmp    L1df8

block_reject:
    ldi     r18, RESULT_BOUNDS
    sts     MEM_STATUS, r18
    lds     r18, MEM_STATE
    cpi     r18, ST_WRITE_EEPROM
    breq    block_reject_no_state
    cpi     r18, ST_WRITE_FLASH
    breq    block_reject_no_state
    ldi     r18, ST_ERROR
    sts     MEM_STATE, r18
block_reject_no_state:
    ldi     r24, EMPTY_MESSAGE
    std     Y+0, r24         /* unsupported write fails by timeout, not bogus ACK */
    rjmp    L1df8

/* Validate wValue+wLength against selected memory bounds. Carry set
 * on success; r16 type, r22:r23 address, r24 length; r18:r19 scratch. */
block_validate_range:
    ldd     r16, Y+27
    ldd     r18, Y+28
    tst     r18
    brne    block_invalid_range
    cpi     r16, 2
    brsh    block_invalid_range
    ldd     r24, Y+29
    ldd     r18, Y+30
    tst     r18
    brne    block_invalid_range
    tst     r24
    breq    block_invalid_range
    cpi     r24, 65
    brsh    block_invalid_range
    ldd     r22, Y+25
    ldd     r23, Y+26
    /* Address + length = 17-bit sum, reject carry and upper bounds. */
    mov     r18, r22
    mov     r19, r23
    add     r18, r24
    adc     r19, r1
    brcs    block_invalid_range
    tst     r16
    breq    block_validate_flash
    tst     r19
    brne    block_invalid_range
    cpi     r18, 65
    brsh    block_invalid_range
    sec
    ret
block_validate_flash:
    ldi     r20, (BOOT_AT & 0xff)
    ldi     r21, (BOOT_AT >> 8)
    cp      r20, r18
    cpc     r21, r19
    brcs    block_invalid_range
    sec
    ret
block_invalid_range:
    clc
    ret

/* One incoming OUT DATA0/1 packet containing 1..8 payload bytes.
 * RX data already ACKed by USB_handler; buffer stays NAK until consumed.
 */
block_accept_out:
    lds     r18, MEM_STATE
    cpi     r18, ST_RECEIVE
    brne    block_out_return
    /* ACK may have been lost at the host; ignore repeated DATA0/DATA1. */
    ldd     r17, Y+22            /* received PID */
    lds     r18, MEM_EXPECT_PID
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
    brne    block_out_return
    cp      r25, r17
    brne    block_out_return
    mov     r24, r23
    lds     r18, MEM_REMAIN
    cp      r18, r24
    brlo    block_out_return
    sub     r18, r24
    sts     MEM_REMAIN, r18
    lds     r19, MEM_INDEX
    ldi     r26, 0x17            /* RX payload at 0x0117 */
    ldi     r27, 0x01
    ldi     r30, 0x40            /* SRAM block data 0x0140 + index */
    add     r30, r19
    ldi     r31, 0x01
block_out_copy_byte:
    ld      r20, X+
    st      Z+, r20
    inc     r19
    dec     r24
    brne    block_out_copy_byte
    sts     MEM_INDEX, r19
    lds     r17, MEM_EXPECT_PID
    ldi     r20, 0x88            /* DATA0/DATA1 PID XOR mask */
    eor     r17, r20
    sts     MEM_EXPECT_PID, r17
    tst     r18
    brne    block_out_return
    /* Received full wLength. Queue asynchronous memory commit. */
    lds     r20, MEM_TYPE
    tst     r20
    breq    block_out_flash
    ldi     r20, ST_WRITE_EEPROM
    rjmp    block_out_set_state
block_out_flash:
    ldi     r20, ST_WRITE_FLASH
block_out_set_state:
    sts     MEM_STATE, r20
block_out_return:
    ret

/* Called from main loop, never within the cycle-critical USB packet engine.
 * EEPROM programming progresses one byte whenever EEPE clears. Flash
 * erase/fill/write executes only after the entire control OUT payload.
 */
block_memory_service:
    ldi     r28, 0x00
    ldi     r29, 0x01
    lds     r18, MEM_STATE
    cpi     r18, ST_WRITE_EEPROM
    breq    block_step_eeprom
    cpi     r18, ST_WRITE_FLASH
    breq    block_commit_flash
    cpi     r18, ST_RUN
    brne    block_service_return
    rjmp    block_service_run
block_service_return:
    ret

block_step_eeprom:
    sbic    0x1f, 1           /* EEPE active? */
    ret
    lds     r18, MEM_PROGRESS
    lds     r19, MEM_TOTAL
    cp      r18, r19
    breq    block_complete
    lds     r20, MEM_ADDR_LO
    add     r20, r18
    ldi     r30, 0x40
    add     r30, r18
    ldi     r31, 0x01
    ld      r21, Z
    out     0x21, r20         /* EEARL */
    out     0x20, r21         /* EEDR */
    out     0x1f, r1         /* erase-and-write mode */
    sbi     0x1f, 2          /* EEMPE: master enable */
    sbi     0x1f, 1          /* EEPE within 4 cycles */
    inc     r18
    sts     MEM_PROGRESS, r18
    ret

block_commit_flash:
    sbic    0x1f, 1           /* EEPROM must be ready before SPM */
    ret
    lds     r30, MEM_ADDR_LO
    andi    r30, 0xc0
    lds     r31, MEM_ADDR_HI
    /* If programming page 0, force reset vector to enter loader. */
    mov     r18, r30
    or      r18, r31
    brne    block_flash_erase
    ldi     r26, 0x40
    ldi     r27, 0x01
    ldi     r18, (RESET_RJMP & 0xff)
    st      X+, r18
    ldi     r18, (RESET_RJMP >> 8)
    st      X, r18
block_flash_erase:
    ldi     r18, 0x03
    out     0x37, r18        /* PGERS|SELFPRGEN */
    spm
    ldi     r18, 0x11
    out     0x37, r18        /* CTPB|SELFPRGEN */
    spm
    ldi     r26, 0x40
    ldi     r27, 0x01
    ldi     r20, 32          /* 32 words in one 64-byte page */
block_flash_fill_word:
    ld      r0, X+
    ld      r1, X+
    ldi     r18, 0x01
    out     0x37, r18
    spm
    adiw    r30, 2
    dec     r20
    brne    block_flash_fill_word
    clr     r1
    /* Page write must have Z low six address bits zero. */
    lds     r30, MEM_ADDR_LO
    andi    r30, 0xc0
    lds     r31, MEM_ADDR_HI
    ldi     r18, 0x05
    out     0x37, r18
    spm
    rjmp    block_complete

block_complete:
    ldi     r18, RESULT_OK
    sts     MEM_STATUS, r18
    ldi     r18, ST_DONE
    sts     MEM_STATE, r18
    /* Prepare the DATA1 zero-length status packet for control OUT. */
    ldi     r18, 0
    sts     0x0100, r18
    ret

block_service_run:
    /* TX length reverts to NAK (0x5A) when status packet has been sent. */
    lds     r18, 0x010f
    cpi     r18, EP0_NAK
    brne    block_run_wait
    rjmp    L1eac
block_run_wait:
    ret

'''
src=src[:start]+newlogic+std
# Compact nearly 40 RAM-global accesses from 4-byte LDS/STS to
# 2-byte LDD/STD Y+q. All calls to these handlers have Y=0x0100;
# main initialization does not, so keep its two absolute writes.
import re
refs={'MEM_STATE':48,'MEM_TYPE':49,'MEM_ADDR_LO':50,'MEM_ADDR_HI':51,
      'MEM_REMAIN':52,'MEM_INDEX':53,'MEM_TOTAL':54,'MEM_STATUS':55,
      'MEM_PROGRESS':56,'MEM_EXPECT_PID':57}
first=src.index('block_memory_service:')
for tag,off in refs.items():
    pat=r'\blds\s+(r\d+),\s*'+tag+r'\b'
    src=re.sub(pat,lambda m:f'ldd     {m.group(1)}, Y+{off}',src)
    pat=r'\bsts\s+'+tag+r',\s*(r\d+)\b'
    # For the two unconditional init stores, Y still has the startup stack pointer.
    prefix=src[:src.index('L1d3a:')]
    suffix=src[src.index('L1d3a:'):]
    suffix=re.sub(pat,lambda m:f'std     Y+{off}, {m.group(1)}',suffix)
    src=prefix+suffix
(P/'source/micronucleus_t88_block64.S').write_text(src)
print('written',len(src),'bytes')
