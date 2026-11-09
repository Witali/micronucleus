/* V-USB usbdrv/usbdrvasm128.inc derivative, originally 12.8 MHz PLL RX.
 * Copyright: (c) 2008 by OBJECTIVE DEVELOPMENT Software GmbH
 * License: GNU GPL v2 (see LICENSE_GPL-2.0.txt), GNU GPL v3 or proprietary
 * (CommercialLicense.txt in upstream; this derivative is supplied under GPL).
 * Upstream obdev/v-usb commit 801242072fa035e1839e3571df0d9a18e9cec95c,
 * blob 75e119d860697c1cca64d710431eb690973c53ad.
 * Offline 16 MHz port: paid DATA/stuff/byte clocks, +2 phase-read relocation,
 * balanced PID 0/11/21/32 startup, actual two-pin cooperative SYNC guards,
 * explicit R23 LPM destination, and runtime PID-to-EXTRA+6 graph handoff.
 * This frozen input precedes the final handoff rewrite in compose.py.
 */
USB_handler:
    out _SFR_IO_ADDR(GPIOR2), r24
    movw r30, r28
acq128_usb_rx_wait_for_j:
    ldi r16, 0x80
    ldi r19, 0xff
    ldi r20, (1 << USB_PLUS_BIT)
    ldi r22, USB_RX_BUFFER_BYTES
    ldi r28, LOW8(USB_CONTEXT_BASE + CTX_RX_BUFFER)
acq128_usb_sync_seek_high:
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    sbic _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_seek_fall
    rjmp acq128_usb_rx_overflow
acq128_usb_sync_seek_fall:
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    rjmp acq128_usb_rx_overflow
acq128_usb_sync_fall:
    in r23, _SFR_IO_ADDR(PIND)
    andi r23, USB_LINE_MASK
    sbrc r23, USB_PLUS_BIT
    rjmp acq128_usb_sync_rise_0
    in r23, _SFR_IO_ADDR(PIND)
    andi r23, USB_LINE_MASK
    sbrc r23, USB_PLUS_BIT
    rjmp acq128_usb_sync_rise_1
    in r23, _SFR_IO_ADDR(PIND)
    andi r23, USB_LINE_MASK
    sbrc r23, USB_PLUS_BIT
    rjmp acq128_usb_sync_rise_2
    in r23, _SFR_IO_ADDR(PIND)
    andi r23, USB_LINE_MASK
    sbrc r23, USB_PLUS_BIT
    rjmp acq128_usb_sync_rise_3
    in r23, _SFR_IO_ADDR(PIND)
    andi r23, USB_LINE_MASK
    sbrc r23, USB_PLUS_BIT
    rjmp acq128_usb_sync_rise_4
    rjmp acq128_usb_rx_overflow
acq128_usb_sync_rise_0:
    ldd r18, Z+CTX_CONFIGURATION
    eor r18, r16
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbic _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp acq128_usb_sync_fall
    sbrc r23, USB_MINUS_BIT
    rjmp acq128_usb_sync_early_delay
    in r20, _SFR_IO_ADDR(PIND)
    nop
    rjmp pll128_pid_start
acq128_usb_sync_rise_1:
    ldd r18, Z+CTX_CONFIGURATION
    eor r18, r16
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbic _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp acq128_usb_sync_fall
    sbrc r23, USB_MINUS_BIT
    rjmp acq128_usb_sync_early_delay
    in r20, _SFR_IO_ADDR(PIND)
    nop
    rjmp pll128_pid_start
acq128_usb_sync_rise_2:
    ldd r18, Z+CTX_CONFIGURATION
    eor r18, r16
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbic _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp acq128_usb_sync_fall
    sbrc r23, USB_MINUS_BIT
    rjmp acq128_usb_sync_early_delay
    in r20, _SFR_IO_ADDR(PIND)
    nop
    rjmp pll128_pid_start
acq128_usb_sync_rise_3:
    ldd r18, Z+CTX_CONFIGURATION
    eor r18, r16
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbic _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp acq128_usb_sync_fall
    sbrc r23, USB_MINUS_BIT
    rjmp acq128_usb_sync_early_delay
    in r20, _SFR_IO_ADDR(PIND)
    nop
    rjmp pll128_pid_start
acq128_usb_sync_rise_4:
    ldd r18, Z+CTX_CONFIGURATION
    eor r18, r16
    sbis _SFR_IO_ADDR(PIND), USB_PLUS_BIT
    rjmp acq128_usb_sync_fall
    sbic _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp acq128_usb_sync_fall
    sbrc r23, USB_MINUS_BIT
    rjmp acq128_usb_sync_early_delay
    in r20, _SFR_IO_ADDR(PIND)
    nop
    rjmp pll128_pid_start
acq128_usb_sync_early_delay:
    nop
    in r20, _SFR_IO_ADDR(PIND)
    nop
    rjmp pll128_pid_start
acq128_usb_rx_overflow:
    sbi _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp usb_rx_ignore_packet
acq128_usb_rx_found_k:
acq128_usb_rx_sync_confirmed:
acq128_usb_rx_delay_complete:
/* obdev/v-usb8012420 usbdrvasm128.inc GPLv2/GPLv3/commercial.
 * Private16MHz retime and real cooperative entry; old EOP unqualified. */
#define x1 r18
#define x2 r19
#define x3 r20
#define phase x3
#define shift r16
#define cnt r22
#define USBIN 9
#define USBMINUS 1
#define USBPLUS 2
#define USBMASK 6
#define nop2 rjmp .+0
#define ifioclr sbis
#define ifioset sbic
#define ifrclr sbrs
#define ifrset sbrc
#define fix x1
#define data x2
/* Upstream first-three-bit construction, with actual data clocks0/11/21
 * and real phase at28. Bit3 joins at32. No PID value is supplied. */
pll128_pid_start:
    rjmp .+0
    nop
pll128_pid0_sample:
    ifioset USBIN, USBMINUS
    ori shift, 1
    rjmp .+0
    rjmp .+0
    rjmp .+0
    rjmp .+0
    nop
pll128_pid1_sample:
    ifioset USBIN, USBMINUS
    ori shift, 2
    ser x2
    ldi cnt, USB_RX_BUFFER_BYTES
    mov x1, shift
    lsl shift
    rjmp .+0
    rjmp .+0
pll128_pid2_sample:
    ifioset USBIN, USBMINUS
    ori x1, 12
    eor shift, x1
    andi x1, 8
    rjmp .+0
    in phase, USBIN
    brne pll128_start_set
    nop
    rjmp pll128_entryAfterClr
pll128_start_set:
    rjmp pll128_entryAfterSet
pll128_bit7IsSet:
    ifrclr  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 7
    nop

pll128_bit0AfterSet:
    rjmp .+0
    eor     fix, shift
#undef  fix
#define fix     x2
#undef  data
#define data    x1  /* we now have result in data, fix is reset to 0xff */
    ifioclr USBIN, USBMINUS
    rjmp    pll128_bit0IsClr
    andi    shift, (255 ^ (7 << 0))
    breq    pll128_unstuff0s
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit1AfterSet
pll128_unstuff0s:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 0))
    ifioclr USBIN, USBMINUS
    ifioset USBIN, USBPLUS
    rjmp    pll128_bit0IsClr
pll128_se0AndStore:
    st      y+, x1
    rjmp    pll128_eof

pll128_bit0IsClr:
    ifrset  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 0
pll128_bit1AfterClr:
    andi    phase, USBMASK
    ifioset USBIN, USBMINUS
    rjmp    pll128_bit1IsSet
    breq    pll128_se0AndStore
    andi    shift, (255 ^ (7 << 1))
    nop
    nop
    in      phase, USBIN
    breq    pll128_unstuff1c
    rjmp    pll128_bit2AfterClr
pll128_unstuff1c:
    andi    fix, (255 ^ (1 << 1))
    nop2
    nop2
pll128_bit1IsSet:
    ifrclr  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 1
    nop
pll128_bit2AfterSet:
    ifioclr USBIN, USBMINUS
    rjmp    pll128_bit2IsClr
    andi    shift, (255 ^ (7 << 2))
    breq    pll128_unstuff2s
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit3AfterSet
pll128_unstuff2s:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 2))
    nop2
    nop2
pll128_bit2IsClr:
    ifrset  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 2
pll128_bit3AfterClr:
    st      y+, data
pll128_entryAfterClr:
    ifioset USBIN, USBMINUS
    rjmp    pll128_bit3IsSet
    andi    shift, (255 ^ (7 << 3))
    breq    pll128_unstuff3c
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit4AfterClr
pll128_unstuff3c:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 3))
    nop2
    nop2
pll128_bit3IsSet:
    ifrclr  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 3
pll128_bit4AfterSet:
    mov     data, fix
#undef  fix
#define fix     x1
#undef  data
#define data    x2
    ifioclr USBIN, USBMINUS
    rjmp    pll128_bit4IsClr
    andi    shift, (255 ^ (7 << 4))
    breq    pll128_unstuff4s
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit5AfterSet
pll128_unstuff4s:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 4))
    nop2
    nop2
pll128_bit4IsClr:
    ifrset  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 4
pll128_bit5AfterClr:
    ser     data
    ifioset USBIN, USBMINUS
    rjmp    pll128_bit5IsSet
    andi    shift, (255 ^ (7 << 5))
    breq    pll128_unstuff5c
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit6AfterClr
pll128_unstuff5c:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 5))
    nop2
    nop2
pll128_bit5IsSet:
    ifrclr  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 5
pll128_bit6AfterSet:
    subi    cnt, 1
    brcs    pll128_jumpToOverflow
    ifioclr USBIN, USBMINUS
    rjmp    pll128_bit6IsClr
    andi    shift, (255 ^ (3 << 6))
    cpi     shift, 2
    nop
    nop
    in      phase, USBIN
    brlt    pll128_unstuff6s
    rjmp    pll128_bit7AfterSet

pll128_jumpToOverflow:
    rjmp    pll128_overflow

pll128_unstuff6s:
    andi    fix, (255 ^ (1 << 6))
    lpm r23, Z
pll128_bit6IsClr:
    ifrset  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 6
    nop
pll128_bit7AfterClr:
    ifioset USBIN, USBMINUS
    rjmp    pll128_bit7IsSet
    andi    shift, (255 ^ (1 << 7))
    cpi     shift, 4
    nop
    nop
    in      phase, USBIN
    brlt    pll128_unstuff7c
    rjmp    pll128_bit0AfterClr
pll128_unstuff7c:
    andi    fix, (255 ^ (1 << 7))
    nop
    rjmp    pll128_bit7IsSet

pll128_bit7IsClr:
    ifrset  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 7
    nop

pll128_bit0AfterClr:
    rjmp .+0
    eor     fix, shift
#undef  fix
#define fix     x2
#undef  data
#define data    x1  /* we now have result in data, fix is reset to 0xff */
pll128_loop0_sample:
    ifioset USBIN, USBMINUS
    rjmp    pll128_bit0IsSet
    andi    shift, (255 ^ (7 << 0))
    breq    pll128_unstuff0c
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit1AfterClr
pll128_unstuff0c:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 0))
    ifioclr USBIN, USBMINUS
    ifioset USBIN, USBPLUS
    rjmp    pll128_bit0IsSet
    rjmp    pll128_se0AndStore
pll128_bit0IsSet:
    ifrclr  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 0
pll128_bit1AfterSet:
    andi    shift, (255 ^ (7 << 1))
    ifioclr USBIN, USBMINUS
    rjmp    pll128_bit1IsClr
    breq    pll128_unstuff1s
    nop2
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit2AfterSet
pll128_unstuff1s:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 1))
    lpm r23, Z
    nop2
pll128_bit1IsClr:
    ifrset  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 1
    nop
pll128_bit2AfterClr:
    ifioset USBIN, USBMINUS
    rjmp    pll128_bit2IsSet
    andi    shift, (255 ^ (7 << 2))
    breq    pll128_unstuff2c
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit3AfterClr
pll128_unstuff2c:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 2))
    nop2
    nop2
pll128_bit2IsSet:
    ifrclr  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 2
pll128_bit3AfterSet:
    st      y+, data
pll128_entryAfterSet:
    ifioclr USBIN, USBMINUS
    rjmp    pll128_bit3IsClr
    andi    shift, (255 ^ (7 << 3))
    breq    pll128_unstuff3s
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit4AfterSet
pll128_unstuff3s:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 3))
    nop2
    nop2
pll128_bit3IsClr:
    ifrset  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 3
pll128_bit4AfterClr:
    mov     data, fix
#undef  fix
#define fix     x1
#undef  data
#define data    x2
    ifioset USBIN, USBMINUS
    rjmp    pll128_bit4IsSet
    andi    shift, (255 ^ (7 << 4))
    breq    pll128_unstuff4c
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit5AfterClr
pll128_unstuff4c:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 4))
    nop2
    nop2
pll128_bit4IsSet:
    ifrclr  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 4
pll128_bit5AfterSet:
    ser     data
    ifioclr USBIN, USBMINUS
    rjmp    pll128_bit5IsClr
    andi    shift, (255 ^ (7 << 5))
    breq    pll128_unstuff5s
    nop
    nop
    in      phase, USBIN
    rjmp    pll128_bit6AfterSet
pll128_unstuff5s:
    nop
    nop
    in      phase, USBIN
    andi    fix, (255 ^ (1 << 5))
    nop2
    nop2
pll128_bit5IsClr:
    ifrset  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 5
pll128_bit6AfterClr:
    subi    cnt, 1
    brcs    pll128_overflow
    ifioset USBIN, USBMINUS
    rjmp    pll128_bit6IsSet
    andi    shift, (255 ^ (3 << 6))
    cpi     shift, 2
    nop
    nop
    in      phase, USBIN
    brlt    pll128_unstuff6c
    rjmp    pll128_bit7AfterClr
pll128_unstuff6c:
    andi    fix, (255 ^ (1 << 6))
    lpm r23, Z
pll128_bit6IsSet:
    ifrclr  phase, USBMINUS
    lpm r23, Z
    nop
    nop
    in      phase, USBIN
    ori     shift, 1 << 6
pll128_bit7AfterSet:
    ifioclr USBIN, USBMINUS
    rjmp    pll128_bit7IsClr
    andi    shift, (255 ^ (1 << 7))
    cpi     shift, 4
    nop
    nop
    in      phase, USBIN
    brlt    pll128_unstuff7s
    rjmp    pll128_bit0AfterSet
pll128_unstuff7s:
    andi    fix, (255 ^ (1 << 7))
    nop
    rjmp    pll128_bit7IsClr

pll128_eof:
    ret
pll128_overflow:
    ret
#undef x1
#undef x2
#undef x3
#undef phase
#undef shift
#undef cnt
#undef fix
#undef data
