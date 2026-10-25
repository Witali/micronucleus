/* Original Micronucleus t88_default 16 MHz - derived from official precompiled firmware.
 * Independent readable assembler reconstruction. Binary-equivalent reference build.
 * Copyright original Micronucleus contributors; GPL-2.0-or-later.
 */
.section .text
/* Edit BOOT_AT only after the build audits that the loader fits in flash. */
#ifndef BOOT_AT
#define BOOT_AT 0x1b00
#endif
.org BOOT_AT
.global bootloader_start
bootloader_start:
    rjmp startup
/* Micronucleus device-info and USB descriptors in program memory. */
    .byte ((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff), 0x40, 0x05, 0x93, 0x11, 0x00, 0x00  /* device config: user flash, page, write delay, signature */
    .byte 0x09, 0x02, 0x12, 0x00, 0x01, 0x01, 0x00, 0x80  /* 1a4a */
    .byte 0x32, 0x09, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00  /* 1a52 */
    .byte 0x00, 0x00, 0x12, 0x01, 0x10, 0x01, 0xff, 0x00  /* 1a5a */
    .byte 0x00, 0x08, 0xd0, 0x16, 0x53, 0x07, 0x06, 0x02  /* 1a62 */
    .byte 0x00, 0x00, 0x00, 0x01  /* 1a6a */

startup:
    eor     r1, r1                           /* 0x1a6e: 2411 */
    out     0x3f, r1                         /* 0x1a70: be1f */
    ldi     r28, 0xff                        /* 0x1a72: efcf */
    ldi     r29, 0x02                        /* 0x1a74: e0d2 */
    out     0x3d, r28                        /* 0x1a76: bfcd */
    out     0x3e, r29                        /* 0x1a78: bfde */
    /* Removed 0x1a7a: ldi     r18, 0x01 (size-optimized, see CHANGES.md) */
    ldi     r26, 0x00                        /* 0x1a7c: e0a0 */
    ldi     r27, 0x01                        /* 0x1a7e: e0b1 */
    /* Removed 0x1a80: rjmp    L1a84 (size-optimized, see CHANGES.md) */

L1a82:
    st      X+, r1                           /* 0x1a82: 921d */

L1a84:
    cpi     r26, 0x2c                        /* 0x1a84: 32ac */
    /* Removed 0x1a86: cpc     r27, r18 (size-optimized, see CHANGES.md) */
    brbc    1, L1a82                         /* 0x1a88: f7e1 */
    rjmp    main                             /* 0x1a8a: c130 */

usb_crc16_append:
    movw    r26, r24                         /* 0x1a8c: 01dc */
    ldi     r24, 0x00                        /* 0x1a8e: e080 */
    ldi     r25, 0x00                        /* 0x1a90: e090 */
    ldi     r20, 0x01                        /* 0x1a92: e041 */
    ldi     r21, 0xa0                        /* 0x1a94: ea50 */
    com     r22                              /* 0x1a96: 9560 */
    ldi     r19, 0x00                        /* 0x1a98: e030 */
    rjmp    L1aae                            /* 0x1a9a: c009 */

L1a9c:
    ld      r18, X+                          /* 0x1a9c: 912d */
    eor     r24, r18                         /* 0x1a9e: 2782 */

L1aa0:
    ror     r25                              /* 0x1aa0: 9597 */
    ror     r24                              /* 0x1aa2: 9587 */
    brbs    0, L1aaa                         /* 0x1aa4: f010 */
    eor     r24, r20                         /* 0x1aa6: 2784 */
    eor     r25, r21                         /* 0x1aa8: 2795 */

L1aaa:
    subi    r19, 0xe0                        /* 0x1aaa: 5e30 */
    brbs    0, L1aa0                         /* 0x1aac: f3c8 */

L1aae:
    subi    r22, 0xff                        /* 0x1aae: 5f6f */
    brbs    0, L1a9c                         /* 0x1ab0: f3a8 */
    st      X+, r24                          /* 0x1ab2: 938d */
    st      X+, r25                          /* 0x1ab4: 939d */
    ret                                      /* 0x1ab6: 9508 */

USB_handler:
    push    r28                              /* 0x1ab8: 93cf */
    push    r29                              /* 0x1aba: 93df */
    eor     r28, r28                         /* 0x1abc: 27cc */

L1abe:
    inc     r28                              /* 0x1abe: 95c3 */
    sbis    0x9, 1                           /* 0x1ac0: 9b49 */
    brbc    1, L1abe                         /* 0x1ac2: f7e9 */

L1ac4:
    sbis    0x9, 1                           /* 0x1ac4: 9b49 */
    rjmp    L1ade                            /* 0x1ac6: c00b */
    sbis    0x9, 1                           /* 0x1ac8: 9b49 */
    rjmp    L1ade                            /* 0x1aca: c009 */
    sbis    0x9, 1                           /* 0x1acc: 9b49 */
    rjmp    L1ade                            /* 0x1ace: c007 */
    sbis    0x9, 1                           /* 0x1ad0: 9b49 */
    rjmp    L1ade                            /* 0x1ad2: c005 */
    sbis    0x9, 1                           /* 0x1ad4: 9b49 */
    rjmp    L1ade                            /* 0x1ad6: c003 */
    sbis    0x9, 1                           /* 0x1ad8: 9b49 */
    rjmp    L1ade                            /* 0x1ada: c001 */
    rjmp    L1bf0                            /* 0x1adc: c089 */

L1ade:
    push    r0                               /* 0x1ade: 920f */
    lds     r28, 0x010e                      /* 0x1ae0: 91c0 010e */
    eor     r29, r29                         /* 0x1ae4: 27dd */
    subi    r28, 0xea                        /* 0x1ae6: 5eca */
    sbci    r29, 0xfe                        /* 0x1ae8: 4fde */
    pop     r0                               /* 0x1aea: 900f */
    ldi     r22, 0x55                        /* 0x1aec: e565 */
    sbis    0x9, 1                           /* 0x1aee: 9b49 */
    rjmp    L1af8                            /* 0x1af0: c003 */
    push    r0                               /* 0x1af2: 920f */
    pop     r0                               /* 0x1af4: 900f */
    rjmp    L1ac4                            /* 0x1af6: cfe6 */

L1af8:
    push    r16                              /* 0x1af8: 930f */
    pop     r16                              /* 0x1afa: 910f */
    push    r16                              /* 0x1afc: 930f */
    ldi     r18, 0x00                        /* 0x1afe: e020 */
    ldi     r20, 0x10                        /* 0x1b00: e140 */
    pop     r16                              /* 0x1b02: 910f */
    in      r16, 0x9                         /* 0x1b04: b109 */
    andi    r16, 0x06                        /* 0x1b06: 7006 */
    bst     r16, 1                           /* 0x1b08: fb01 */
    bld     r18, 7                           /* 0x1b0a: f927 */
    push    r19                              /* 0x1b0c: 933f */
    ldi     r21, 0x00                        /* 0x1b0e: e050 */
    ldi     r19, 0x0b                        /* 0x1b10: e03b */
    rjmp    L1b86                            /* 0x1b12: c039 */

L1b14:
    andi    r17, 0x06                        /* 0x1b14: 7016 */
    ori     r20, 0x40                        /* 0x1b16: 6440 */
    andi    r18, 0x7f                        /* 0x1b18: 772f */
    mov     r16, r17                         /* 0x1b1a: 2f01 */
    subi    r21, 0xff                        /* 0x1b1c: 5f5f */
    rjmp    L1b5c                            /* 0x1b1e: c01e */

L1b20:
    ori     r20, 0x80                        /* 0x1b20: 6840 */
    in      r17, 0x9                         /* 0x1b22: b119 */
    andi    r17, 0x06                        /* 0x1b24: 7016 */
    andi    r18, 0x7f                        /* 0x1b26: 772f */
    subi    r21, 0x02                        /* 0x1b28: 5052 */
    rjmp    L1b6a                            /* 0x1b2a: c01f */

L1b2c:
    ori     r20, 0x40                        /* 0x1b2c: 6440 */
    in      r16, 0x9                         /* 0x1b2e: b109 */
    andi    r18, 0x7f                        /* 0x1b30: 772f */
    andi    r16, 0x06                        /* 0x1b32: 7006 */
    brbs    1, L1baa                         /* 0x1b34: f1d1 */
    subi    r21, 0xff                        /* 0x1b36: 5f5f */
    rjmp    L1b3a                            /* 0x1b38: c000 */

L1b3a:
    rjmp    L1b82                            /* 0x1b3a: c023 */

L1b3c:
    ori     r20, 0x20                        /* 0x1b3c: 6240 */
    in      r17, 0x9                         /* 0x1b3e: b119 */
    andi    r18, 0x7f                        /* 0x1b40: 772f */
    andi    r17, 0x06                        /* 0x1b42: 7016 */
    brbs    1, L1baa                         /* 0x1b44: f191 */
    subi    r21, 0xff                        /* 0x1b46: 5f5f */
    rjmp    L1b4a                            /* 0x1b48: c000 */

L1b4a:
    rjmp    L1b96                            /* 0x1b4a: c025 */

L1b4c:
    andi    r16, 0x06                        /* 0x1b4c: 7006 */
    eor     r17, r16                         /* 0x1b4e: 2710 */
    subi    r21, 0x01                        /* 0x1b50: 5051 */
    brbc    2, L1b58                         /* 0x1b52: f412 */
    subi    r21, 0xfd                        /* 0x1b54: 5f5d */
    nop                                      /* 0x1b56: 0000 */

L1b58:
    subi    r17, 0x01                        /* 0x1b58: 5011 */
    ror     r18                              /* 0x1b5a: 9527 */

L1b5c:
    cpi     r18, 0xfc                        /* 0x1b5c: 3f2c */
    in      r17, 0x9                         /* 0x1b5e: b119 */
    brbc    0, L1b14                         /* 0x1b60: f6c8 */
    andi    r17, 0x06                        /* 0x1b62: 7016 */
    eor     r16, r17                         /* 0x1b64: 2701 */
    subi    r16, 0x01                        /* 0x1b66: 5001 */
    ror     r18                              /* 0x1b68: 9527 */

L1b6a:
    cpi     r18, 0xfc                        /* 0x1b6a: 3f2c */
    brbc    0, L1b20                         /* 0x1b6c: f6c8 */
    eor     r20, r18                         /* 0x1b6e: 2742 */
    st      Y+, r20                          /* 0x1b70: 9349 */

L1b72:
    in      r16, 0x9                         /* 0x1b72: b109 */
    andi    r16, 0x06                        /* 0x1b74: 7006 */
    eor     r17, r16                         /* 0x1b76: 2710 */
    andi    r20, 0x3f                        /* 0x1b78: 734f */
    subi    r17, 0x01                        /* 0x1b7a: 5011 */
    ror     r18                              /* 0x1b7c: 9527 */
    cpi     r18, 0xfc                        /* 0x1b7e: 3f2c */
    brbc    0, L1b2c                         /* 0x1b80: f6a8 */

L1b82:
    lsr     r20                              /* 0x1b82: 9546 */
    lsr     r20                              /* 0x1b84: 9546 */

L1b86:
    in      r17, 0x9                         /* 0x1b86: b119 */
    andi    r17, 0x06                        /* 0x1b88: 7016 */
    brbs    1, L1baa                         /* 0x1b8a: f079 */
    eor     r16, r17                         /* 0x1b8c: 2701 */
    subi    r16, 0x01                        /* 0x1b8e: 5001 */
    ror     r18                              /* 0x1b90: 9527 */
    cpi     r18, 0xfc                        /* 0x1b92: 3f2c */
    brbc    0, L1b3c                         /* 0x1b94: f698 */

L1b96:
    subi    r22, 0xab                        /* 0x1b96: 5a6b */
    brbs    0, L1b72                         /* 0x1b98: f360 */
    subi    r19, 0x01                        /* 0x1b9a: 5031 */
    in      r16, 0x9                         /* 0x1b9c: b109 */
    brbc    0, L1b4c                         /* 0x1b9e: f6b0 */
    rjmp    L1ba2                            /* 0x1ba0: c000 */

L1ba2:
    ldi     r17, 0x04                        /* 0x1ba2: e014 */
    out     0x1b, r17                        /* 0x1ba4: bb1b */

L1ba6:
    eor     r16, r16                         /* 0x1ba6: 2700 */
    rjmp    L1be4                            /* 0x1ba8: c01d */

L1baa:
    subi    r19, 0x0b                        /* 0x1baa: 503b */
    neg     r19                              /* 0x1bac: 9531 */
    sub     r28, r19                         /* 0x1bae: 1bc3 */
    sbci    r29, 0x00                        /* 0x1bb0: 40d0 */
    ldi     r17, 0x04                        /* 0x1bb2: e014 */
    out     0x1b, r17                        /* 0x1bb4: bb1b */
    ldd     r16, Y+0                         /* 0x1bb6: 8108 */
    cpi     r16, 0xc3                        /* 0x1bb8: 3c03 */
    brbs    1, L1bf6                         /* 0x1bba: f0e9 */
    cpi     r16, 0x4b                        /* 0x1bbc: 340b */
    brbs    1, L1bf6                         /* 0x1bbe: f0d9 */
    lds     r18, 0x010c                      /* 0x1bc0: 9120 010c */
    ldd     r17, Y+1                         /* 0x1bc4: 8119 */
    add     r17, r17                         /* 0x1bc6: 0f11 */
    cpse    r17, r18                         /* 0x1bc8: 1312 */
    rjmp    L1ba6                            /* 0x1bca: cfed */
    cpi     r16, 0x69                        /* 0x1bcc: 3609 */
    brbs    1, L1c14                         /* 0x1bce: f111 */
    cpi     r16, 0x2d                        /* 0x1bd0: 320d */
    brbs    1, L1bd8                         /* 0x1bd2: f011 */
    cpi     r16, 0xe1                        /* 0x1bd4: 3e01 */
    brbc    1, L1ba6                         /* 0x1bd6: f739 */

L1bd8:
    ldi     r28, 0x0a                        /* 0x1bd8: e0ca */

L1bda:
    in      r17, 0x1b                        /* 0x1bda: b31b */
    sbrc    r17, 2                           /* 0x1bdc: fd12 */
    rjmp    L1be4                            /* 0x1bde: c002 */
    dec     r28                              /* 0x1be0: 95ca */
    brbc    1, L1bda                         /* 0x1be2: f7d9 */

L1be4:
    sts     0x0114, r16                      /* 0x1be4: 9300 0114 */

L1be8:
    pop     r19                              /* 0x1be8: 913f */
    in      r28, 0x1b                        /* 0x1bea: b3cb */
    sbrc    r28, 2                           /* 0x1bec: fdc2 */
    rjmp    L1abe                            /* 0x1bee: cf67 */

L1bf0:
    pop     r29                              /* 0x1bf0: 91df */
    pop     r28                              /* 0x1bf2: 91cf */
    ret                                      /* 0x1bf4: 9508 */

L1bf6:
    lds     r18, 0x0114                      /* 0x1bf6: 9120 0114 */
    and     r18, r18                         /* 0x1bfa: 2322 */
    brbs    1, L1be8                         /* 0x1bfc: f3a9 */
    lds     r17, 0x0112                      /* 0x1bfe: 9110 0112 */
    and     r17, r17                         /* 0x1c02: 2311 */
    brbc    1, L1c48                         /* 0x1c04: f509 */
    cpi     r19, 0x04                        /* 0x1c06: 3034 */
    brbs    2, L1c4c                         /* 0x1c08: f10a */
    sts     0x0112, r19                      /* 0x1c0a: 9330 0112 */
    sts     0x010d, r18                      /* 0x1c0e: 9320 010d */
    rjmp    L1c4c                            /* 0x1c12: c01c */

L1c14:
    lds     r16, 0x0112                      /* 0x1c14: 9100 0112 */
    cpi     r16, 0x01                        /* 0x1c18: 3001 */
    brbc    4, L1c48                         /* 0x1c1a: f4b4 */
    ldi     r16, 0x5a                        /* 0x1c1c: e50a */
    lds     r19, 0x010f                      /* 0x1c1e: 9130 010f */
    sbrc    r19, 4                           /* 0x1c22: fd34 */
    rjmp    L1c4e                            /* 0x1c24: c014 */
    sts     0x010f, r16                      /* 0x1c26: 9300 010f */
    ldi     r28, 0x01                        /* 0x1c2a: e0c1 */
    ldi     r29, 0x01                        /* 0x1c2c: e0d1 */
    rjmp    L1c56                            /* 0x1c2e: c013 */

L1c30:
    eor     r16, r21                         /* 0x1c30: 2705 */
    ldi     r17, 0x00                        /* 0x1c32: e010 */
    rjmp    L1c36                            /* 0x1c34: c000 */

L1c36:
    nop                                      /* 0x1c36: 0000 */
    out     0xb, r16                         /* 0x1c38: b90b */
    rjmp    L1c70                            /* 0x1c3a: c01a */

L1c3c:
    eor     r16, r21                         /* 0x1c3c: 2705 */
    ldi     r17, 0x00                        /* 0x1c3e: e010 */
    adc     r18, r18                         /* 0x1c40: 1f22 */
    rjmp    L1c7e                            /* 0x1c42: c01d */

L1c44:
    ldi     r17, 0x00                        /* 0x1c44: e010 */
    rjmp    L1c8a                            /* 0x1c46: c021 */

L1c48:
    ldi     r20, 0x5a                        /* 0x1c48: e54a */
    rjmp    L1c50                            /* 0x1c4a: c002 */

L1c4c:
    ldi     r19, 0xd2                        /* 0x1c4c: ed32 */

L1c4e:
    mov     r20, r19                         /* 0x1c4e: 2f43 */

L1c50:
    ldi     r28, 0x14                        /* 0x1c50: e1c4 */
    ldi     r29, 0x00                        /* 0x1c52: e0d0 */
    ldi     r19, 0x02                        /* 0x1c54: e032 */

L1c56:
    in      r17, 0xa                         /* 0x1c56: b11a */
    ori     r17, 0x06                        /* 0x1c58: 6016 */
    sbi     0xb, 1                           /* 0x1c5a: 9a59 */
    in      r16, 0xb                         /* 0x1c5c: b10b */
    out     0xa, r17                         /* 0x1c5e: b91a */
    ldi     r21, 0x06                        /* 0x1c60: e056 */
    ldi     r18, 0x80                        /* 0x1c62: e820 */

L1c64:
    ldi     r22, 0x35                        /* 0x1c64: e365 */

L1c66:
    sbrs    r18, 0                           /* 0x1c66: ff20 */
    eor     r16, r21                         /* 0x1c68: 2705 */
    out     0xb, r16                         /* 0x1c6a: b90b */
    ror     r18                              /* 0x1c6c: 9527 */
    ror     r17                              /* 0x1c6e: 9517 */

L1c70:
    cpi     r17, 0xfc                        /* 0x1c70: 3f1c */
    brbc    0, L1c30                         /* 0x1c72: f6f0 */
    lsr     r22                              /* 0x1c74: 9566 */
    brbc    0, L1c66                         /* 0x1c76: f7b8 */
    brbc    1, L1c66                         /* 0x1c78: f7b1 */
    sbrs    r18, 0                           /* 0x1c7a: ff20 */
    eor     r16, r21                         /* 0x1c7c: 2705 */

L1c7e:
    out     0xb, r16                         /* 0x1c7e: b90b */
    ror     r18                              /* 0x1c80: 9527 */
    ror     r17                              /* 0x1c82: 9517 */
    cpi     r17, 0xfc                        /* 0x1c84: 3f1c */
    brbc    0, L1c3c                         /* 0x1c86: f6d0 */
    ror     r18                              /* 0x1c88: 9527 */

L1c8a:
    ror     r17                              /* 0x1c8a: 9517 */
    sbrs    r17, 7                           /* 0x1c8c: ff17 */
    eor     r16, r21                         /* 0x1c8e: 2705 */
    nop                                      /* 0x1c90: 0000 */
    cpi     r17, 0xfc                        /* 0x1c92: 3f1c */
    out     0xb, r16                         /* 0x1c94: b90b */
    brbc    0, L1c44                         /* 0x1c96: f6b0 */
    ld      r18, Y+                          /* 0x1c98: 9129 */
    dec     r19                              /* 0x1c9a: 953a */
    brbc    1, L1c64                         /* 0x1c9c: f719 */
    andi    r16, 0xf9                        /* 0x1c9e: 7f09 */
    lds     r17, 0x0113                      /* 0x1ca0: 9110 0113 */
    add     r17, r17                         /* 0x1ca4: 0f11 */
    subi    r28, 0x16                        /* 0x1ca6: 51c6 */
    sbci    r29, 0x00                        /* 0x1ca8: 40d0 */
    out     0xb, r16                         /* 0x1caa: b90b */
    brbs    1, L1cb2                         /* 0x1cac: f011 */
    sts     0x010c, r17                      /* 0x1cae: 9310 010c */

L1cb2:
    ldi     r17, 0x04                        /* 0x1cb2: e014 */
    out     0x1b, r17                        /* 0x1cb4: bb1b */
    ori     r16, 0x02                        /* 0x1cb6: 6002 */
    in      r17, 0xa                         /* 0x1cb8: b11a */
    andi    r17, 0xf9                        /* 0x1cba: 7f19 */
    mov     r20, r16                         /* 0x1cbc: 2f40 */
    andi    r20, 0xf9                        /* 0x1cbe: 7f49 */
    ldi     r21, 0x04                        /* 0x1cc0: e054 */

L1cc2:
    dec     r21                              /* 0x1cc2: 955a */
    brbc    1, L1cc2                         /* 0x1cc4: f7f1 */
    out     0xb, r16                         /* 0x1cc6: b90b */
    out     0xa, r17                         /* 0x1cc8: b91a */
    out     0xb, r20                         /* 0x1cca: b94b */
    rjmp    L1be8                            /* 0x1ccc: cf8d */

usb_program_page:
    movw    r30, r4                          /* 0x1cce: 01f2 */
    sbiw    r30, 0                           /* 0x1cd0: 9730 */
    brbc    1, L1cd8                         /* 0x1cd2: f411 */
    ldi     r24, ((0xc000 + (BOOT_AT / 2) - 1) & 0xff)  /* original at 0x1cd4 */
    ldi     r25, ((0xc000 + (BOOT_AT / 2) - 1) >> 8)    /* original at 0x1cd6 */

L1cd8:
    ldi     r18, 0x01                        /* 0x1cd8: e021 */
    movw    r0, r24                          /* 0x1cda: 010c */
    sts     0x0057, r18                      /* 0x1cdc: 9320 0057 */
    spm                                      /* 0x1ce0: 95e8 */
    eor     r1, r1                           /* 0x1ce2: 2411 */
    movw    r24, r30                         /* 0x1ce4: 01cf */
    adiw    r24, 2                           /* 0x1ce6: 9602 */
    movw    r4, r24                          /* 0x1ce8: 012c */
    ret                                      /* 0x1cea: 9508 */

main:
    wdr                                      /* 0x1cec: 95a8 */
    lds     r24, 0x0060                      /* 0x1cee: 9180 0060 */
    ori     r24, 0x18                        /* 0x1cf2: 6188 */
    sts     0x0060, r24                      /* 0x1cf4: 9380 0060 */
    sts     0x0060, r1                       /* 0x1cf8: 9210 0060 */
    sbi     0xa, 1                           /* 0x1cfc: 9a51 */
    ldi     r24, 0xb8                        /* 0x1cfe: eb88 */
    ldi     r25, 0x0b                        /* 0x1d00: e09b */

L1d02:
    ldi     r30, 0x90                        /* 0x1d02: e9e0 */
    ldi     r31, 0x01                        /* 0x1d04: e0f1 */

L1d06:
    sbiw    r30, 1                           /* 0x1d06: 9731 */
    brbc    1, L1d06                         /* 0x1d08: f7f1 */
    sbiw    r24, 1                           /* 0x1d0a: 9701 */
    brbc    1, L1d02                         /* 0x1d0c: f7d1 */
    cbi     0xa, 1                           /* 0x1d0e: 9851 */
    ldi     r24, 0x5a                        /* 0x1d10: e58a */
    sts     0x010f, r24                      /* 0x1d12: 9380 010f */
    ldi     r24, 0xff                        /* 0x1d16: ef8f */
    sts     0x0100, r24                      /* 0x1d18: 9380 0100 */
    lds     r24, 0x006d                      /* 0x1d1c: 9180 006d */
    ori     r24, 0x04                        /* 0x1d20: 6084 */
    sts     0x006d, r24                      /* 0x1d22: 9380 006d */
    lds     r24, 0x0068                      /* 0x1d26: 9180 0068 */
    ori     r24, 0x04                        /* 0x1d2a: 6084 */
    sts     0x0068, r24                      /* 0x1d2c: 9380 0068 */
    /* Removed 0x1d30: sbi     0xa, 0 (size-optimized, see CHANGES.md) */
    mov     r7, r1                           /* 0x1d32: 2c71 */
    mov     r3, r1                           /* 0x1d34: 2c31 */
    mov     r5, r1                           /* 0x1d36: 2c51 */
    mov     r4, r1                           /* 0x1d38: 2c41 */

L1d3a:
    ldi     r28, 0xd5                        /* 0x1d3a: edc5 */
    ldi     r29, 0x14                        /* 0x1d3c: e1d4 */
    ldi     r24, 0x64                        /* 0x1d3e: e684 */

L1d40:
    in      r25, 0x9                         /* 0x1d40: b199 */
    andi    r25, 0x06                        /* 0x1d42: 7096 */
    brbs    1, L1d48                         /* 0x1d44: f009 */
    ldi     r24, 0x64                        /* 0x1d46: e684 */

L1d48:
    subi    r24, 0x01                        /* 0x1d48: 5081 */
    brbc    1, L1d54                         /* 0x1d4a: f421 */
    sts     0x0113, r1                       /* 0x1d4c: 9210 0113 */
    sts     0x010c, r1                       /* 0x1d50: 9210 010c */

L1d54:
    sbis    0x1b, 2                          /* 0x1d54: 9bda */
    rjmp    L1e98                            /* 0x1d56: c0a0 */
    rcall   USB_handler                      /* 0x1d58: deaf */
    ldi     r24, 0x04                        /* 0x1d5a: e084 */
    out     0x1b, r24                        /* 0x1d5c: bb8b */

L1d5e:
    wdr                                      /* 0x1d5e: 95a8 */
    ldi     r18, 0x02                        /* 0x1d60: e022 */
    cpse    r3, r18                          /* 0x1d62: 1232 */
    rjmp    L1d7e                            /* 0x1d64: c00c */
    ldi     r30, (BOOT_AT & 0xff)                       /* original at 0x1d66 */
    ldi     r31, (BOOT_AT >> 8)                         /* original at 0x1d68 */

L1d6a:
    subi    r30, 0x40                        /* 0x1d6a: 54e0 */
    sbc     r31, r1                          /* 0x1d6c: 09f1 */
    ldi     r24, 0x03                        /* 0x1d6e: e083 */
    sts     0x0057, r24                      /* 0x1d70: 9380 0057 */
    spm                                      /* 0x1d74: 95e8 */
    sbiw    r30, 0                           /* 0x1d76: 9730 */
    brbc    1, L1d6a                         /* 0x1d78: f7c1 */
    mov     r5, r1                           /* 0x1d7a: 2c51 */
    mov     r4, r1                           /* 0x1d7c: 2c41 */

L1d7e:
    mov     r24, r3                          /* 0x1d7e: 2d83 */
    cpi     r24, 0x40                        /* 0x1d80: 3480 */
    brbs    1, L1d86                         /* 0x1d82: f009 */
    rjmp    L1ea0                            /* 0x1d84: c08d */

L1d86:
    movw    r30, r4                          /* 0x1d86: 01f2 */
    sbiw    r30, 2                           /* 0x1d88: 9732 */
    cpi     r30, (BOOT_AT & 0xff)                       /* original at 0x1d8a */
    ldi     r24, (BOOT_AT >> 8)                         /* original at 0x1d8c */
    cpc     r31, r24                         /* 0x1d8e: 07f8 */
    brbc    0, L1d9a                         /* 0x1d90: f420 */
    andi    r30, 0xc0   /* AUDIT FIX: zero SPM Page Write PCWORD bits, 64-byte Flash page */
    ldi     r24, 0x05                        /* 0x1d92: e085 */
    sts     0x0057, r24                      /* 0x1d94: 9380 0057 */
    spm                                      /* 0x1d98: 95e8 */

L1d9a:
    mov     r3, r1                           /* 0x1d9a: 2c31 */

L1d9c:
    /* Y=0x0100 is a base pointer for usbdrv SRAM globals during command/packet handling. */
    ldi     r28, 0x00
    ldi     r29, 0x01
    ldd     r24, Y+18   /* 1d9c: SRAM compact access */
    subi    r24, 0x03                        /* 0x1da0: 5083 */
    sbrc    r24, 7                           /* 0x1da2: fd87 */
    rjmp    L1dfc                            /* 0x1da4: c02b */
    ldd     r25, Y+13   /* 1da6: SRAM compact access */
    cpi     r25, 0x2d                        /* 0x1daa: 329d */
    brbc    1, L1df8                         /* 0x1dac: f529 */
    cpi     r24, 0x08                        /* 0x1dae: 3088 */
    brbc    1, L1df8                         /* 0x1db0: f519 */
    ldi     r24, 0xc3                        /* 0x1db2: ec83 */
    std     Y+1, r24   /* 1db4: SRAM compact access */
    ldi     r24, 0x5a                        /* 0x1db8: e58a */
    std     Y+15, r24   /* 1dba: SRAM compact access */
    ldd     r24, Y+23   /* 1dbe: SRAM compact access */
    andi    r24, 0x60                        /* 0x1dc2: 7680 */
    ldd     r25, Y+24   /* 1dc4: SRAM compact access */
    and     r24, r24                         /* 0x1dc8: 2388 */
    brbc    1, L1dce                         /* 0x1dca: f409 */
    rjmp    L1f0c                            /* 0x1dcc: c09f */

L1dce:
    mov     r7, r1                           /* 0x1dce: 2c71 */
    cpse    r25, r1                          /* 0x1dd0: 1191 */
    rjmp    L1ec0                            /* 0x1dd2: c076 */
    ldi     r24, ((BOOT_AT + 2) & 0xff)                 /* original at 0x1dd4 */
    ldi     r25, ((BOOT_AT + 2) >> 8)                   /* original at 0x1dd6 */
    std     Y+17, r25   /* 1dd8: SRAM compact access */
    std     Y+16, r24   /* 1ddc: SRAM compact access */
    ldi     r24, 0x08                        /* 0x1de0: e088 */

L1de2:
    ldd     r25, Y+30   /* 1de2: SRAM compact access */
    cpse    r25, r1                          /* 0x1de6: 1191 */
    rjmp    L1df4                            /* 0x1de8: c005 */
    ldd     r25, Y+29   /* 1dea: SRAM compact access */
    cp      r25, r24                         /* 0x1dee: 1798 */
    brbc    0, L1df4                         /* 0x1df0: f408 */
    mov     r24, r25                         /* 0x1df2: 2f89 */

L1df4:
    std     Y+0, r24   /* 1df4: SRAM compact access */

L1df8:
    std     Y+18, r1   /* 1df8: SRAM compact access */

L1dfc:
    ldd     r24, Y+15   /* 1dfc: SRAM compact access */
    sbrs    r24, 4                           /* 0x1e00: ff84 */
    rjmp    L1e64                            /* 0x1e02: c030 */
    ldd     r24, Y+0   /* 1e04: SRAM compact access */
    cpi     r24, 0xff                        /* 0x1e08: 3f8f */
    brbs    1, L1e64                         /* 0x1e0a: f161 */
    mov     r23, r24                                    /* original at 0x1e0c */
    cpi     r24, 0x09                        /* 0x1e0e: 3089 */
    brbs    0, L1e14                         /* 0x1e10: f008 */
    ldi     r23, 0x08                                   /* original at 0x1e12 */

L1e14:
    mov     r25, r24                         /* 0x1e14: 2f98 */
    sub     r25, r23                                    /* original at 0x1e16 */
    std     Y+0, r25   /* 1e18: SRAM compact access */
    ldd     r25, Y+1   /* 1e1c: SRAM compact access */
    ldi     r18, 0x88                        /* 0x1e20: e828 */
    eor     r25, r18                         /* 0x1e22: 2792 */
    std     Y+1, r25   /* 1e24: SRAM compact access */
    and     r24, r24                         /* 0x1e28: 2388 */
    brbs    1, L1e4c                         /* 0x1e2a: f081 */
    ldd     r30, Y+16   /* 1e2c: SRAM compact access */
    ldd     r31, Y+17   /* 1e30: SRAM compact access */
    ldi     r26, 0x02                        /* 0x1e34: e0a2 */
    ldi     r27, 0x01                        /* 0x1e36: e0b1 */
    mov     r24, r23                                    /* original at 0x1e38 */

L1e3a:
    lpm     r25, Z                           /* 0x1e3a: 9194 */
    st      X+, r25                          /* 0x1e3c: 939d */
    adiw    r30, 1                           /* 0x1e3e: 9631 */
    subi    r24, 0x01                        /* 0x1e40: 5081 */
    brbc    1, L1e3a                         /* 0x1e42: f7d9 */
    std     Y+17, r31   /* 1e44: SRAM compact access */
    std     Y+16, r30   /* 1e48: SRAM compact access */

L1e4c:
    mov     r22, r23                                    /* original at 0x1e4c */
    ldi     r24, 0x02                        /* 0x1e4e: e082 */
    ldi     r25, 0x01                        /* 0x1e50: e091 */
    rcall   usb_crc16_append                 /* 0x1e52: de1c */
    subi    r23, 0xfc                                   /* original at 0x1e54 */
    cpi     r23, 0x0c                                   /* original at 0x1e56 */
    brbs    1, L1e60                         /* 0x1e58: f019 */
    ldi     r24, 0xff                        /* 0x1e5a: ef8f */
    std     Y+0, r24   /* 1e5c: SRAM compact access */

L1e60:
    std     Y+15, r23                                   /* original at 0x1e60 */

L1e64:
    movw    r24, r6                          /* 0x1e64: 01c3 */
    adiw    r24, 1                           /* 0x1e66: 9601 */
    movw    r6, r24                          /* 0x1e68: 013c */
    cpi     r24, 0xb0                        /* 0x1e6a: 3b80 */
    ldi     r18, 0x04                        /* 0x1e6c: e024 */
    cpc     r25, r18                         /* 0x1e6e: 0792 */
    brbc    1, L1e7c                         /* 0x1e70: f429 */
    ldi     r30, ((BOOT_AT - 3) & 0xff)                 /* original at 0x1e72 */
    ldi     r31, ((BOOT_AT - 3) >> 8)                   /* original at 0x1e74 */
    lpm     r30, Z                           /* 0x1e76: 91e4 */
    cpi     r30, 0xff                        /* 0x1e78: 3fef */
    brbc    1, L1eac                         /* 0x1e7a: f4c1 */

L1e7c:
    /* Removed 0x1e7c: andi    r24, 0x4c (size-optimized, see CHANGES.md) */
    /* Removed 0x1e7e: brbc    1, L1e82 (size-optimized, see CHANGES.md) */
    /* Removed 0x1e80: rjmp    L1f82 (size-optimized, see CHANGES.md) */

L1e82:
    /* Removed 0x1e82: cbi     0xb, 0 (size-optimized, see CHANGES.md) */

L1e84:
    sbis    0x1b, 2                          /* 0x1e84: 9bda */
    rjmp    L1d3a                            /* 0x1e86: cf59 */
    ldi     r24, 0x1c                        /* 0x1e88: e18c */

L1e8a:
    sbis    0x9, 1                           /* 0x1e8a: 9b49 */
    ldi     r24, 0x1c                        /* 0x1e8c: e18c */
    subi    r24, 0x01                        /* 0x1e8e: 5081 */
    brbc    1, L1e8a                         /* 0x1e90: f7e1 */
    ldi     r24, 0x04                        /* 0x1e92: e084 */
    out     0x1b, r24                        /* 0x1e94: bb8b */
    rjmp    L1d3a                            /* 0x1e96: cf51 */

L1e98:
    sbiw    r28, 1                           /* 0x1e98: 9721 */
    brbs    1, L1e9e                         /* 0x1e9a: f009 */
    rjmp    L1d40                            /* 0x1e9c: cf51 */

L1e9e:
    rjmp    L1d5e                            /* 0x1e9e: cf5f */

L1ea0:
    cpi     r24, 0x04                        /* 0x1ea0: 3084 */
    brbs    1, L1ea6                         /* 0x1ea2: f009 */
    rjmp    L1d9a                            /* 0x1ea4: cf7a */

L1ea6:
    or      r28, r29                         /* 0x1ea6: 2bcd */
    brbs    1, L1eac                         /* 0x1ea8: f009 */
    rjmp    L1d9c                            /* 0x1eaa: cf78 */

L1eac:
    /* Removed 0x1eac: cbi     0xb, 0 (size-optimized, see CHANGES.md) */
    out     0xa, r1                          /* 0x1eae: b81a */
    sts     0x0068, r1                       /* 0x1eb0: 9210 0068 */
    sts     0x006d, r1                       /* 0x1eb4: 9210 006d */
    in      r24, 0x34                        /* 0x1eb8: b784 */
    out     0x1e, r24                        /* 0x1eba: bb8e */
    out     0x34, r1                         /* 0x1ebc: be14 */
app_jump:
    .word (0xc000 | (((bootloader_start - 4 - app_jump - 2)/2) & 0x0fff)) /* relative RJMP into application postscript */

L1ec0:
    cpi     r25, 0x01                        /* 0x1ec0: 3091 */
    brbc    1, L1ee2                         /* 0x1ec2: f479 */
    cp      r4, r1                           /* 0x1ec4: 1441 */
    cpc     r5, r1                           /* 0x1ec6: 0451 */
    brbc    1, L1ece                         /* 0x1ec8: f411 */

L1eca:
    ldi     r24, 0x00                        /* 0x1eca: e080 */
    rjmp    L1de2                            /* 0x1ecc: cf8a */

L1ece:
    ldd     r24, Y+27   /* 1ece: SRAM compact access */
    andi    r24, 0xc0                        /* 0x1ed2: 7c80 */
    mov     r4, r24                          /* 0x1ed4: 2e48 */
    ldd     r5, Y+28   /* 1ed6: SRAM compact access */
    ldi     r24, 0x11                        /* 0x1eda: e181 */
    out     0x37, r24                        /* 0x1edc: bf87 */
    spm                                      /* 0x1ede: 95e8 */
    rjmp    L1eca                            /* 0x1ee0: cff4 */

L1ee2:
    cpi     r25, 0x03                        /* 0x1ee2: 3093 */
    brbc    1, L1f06                         /* 0x1ee4: f481 */
    ldd     r24, Y+25   /* 1ee6: SRAM compact access */
    ldd     r25, Y+26   /* 1eea: SRAM compact access */
    rcall   usb_program_page                 /* 0x1eee: deef */
    ldd     r24, Y+27   /* 1ef0: SRAM compact access */
    ldd     r25, Y+28   /* 1ef4: SRAM compact access */
    rcall   usb_program_page                 /* 0x1ef8: deea */
    mov     r24, r4                          /* 0x1efa: 2d84 */
    andi    r24, 0x3f                        /* 0x1efc: 738f */
    brbc    1, L1eca                         /* 0x1efe: f729 */
    ldi     r25, 0x40                        /* 0x1f00: e490 */
    mov     r3, r25                          /* 0x1f02: 2e39 */
    rjmp    L1de2                            /* 0x1f04: cf6e */

L1f06:
    andi    r25, 0x3f                        /* 0x1f06: 739f */
    mov     r3, r25                          /* 0x1f08: 2e39 */
    rjmp    L1eca                            /* 0x1f0a: cfdf */

L1f0c:
    ldd     r18, Y+25   /* 1f0c: SRAM compact access */
    std     Y+10, r1   /* 1f10: SRAM compact access */
    cpse    r25, r1                          /* 0x1f14: 1191 */
    rjmp    L1f2c                            /* 0x1f16: c00a */
    std     Y+11, r1   /* 1f18: SRAM compact access */
    ldi     r18, 0x0a                        /* 0x1f1c: e02a */
    ldi     r19, 0x01                        /* 0x1f1e: e031 */
    ldi     r24, 0x02                        /* 0x1f20: e082 */

L1f22:
    std     Y+17, r19   /* 1f22: SRAM compact access */
    std     Y+16, r18   /* 1f26: SRAM compact access */
    rjmp    L1de2                            /* 0x1f2a: cf5b */

L1f2c:
    cpi     r25, 0x05                        /* 0x1f2c: 3095 */
    brbc    1, L1f3a                         /* 0x1f2e: f429 */
    std     Y+19, r18   /* 1f30: SRAM compact access */

L1f34:
    ldi     r18, 0x0a                        /* 0x1f34: e02a */
    ldi     r19, 0x01                        /* 0x1f36: e031 */
    rjmp    L1f22                            /* 0x1f38: cff4 */

L1f3a:
    cpi     r25, 0x06                        /* 0x1f3a: 3096 */
    brbc    1, L1f62                         /* 0x1f3c: f491 */
    ldd     r24, Y+26   /* 1f3e: SRAM compact access */
    cpi     r24, 0x01                        /* 0x1f42: 3081 */
    brbc    1, L1f56                         /* 0x1f44: f441 */
    ldi     r24, ((BOOT_AT + 0x1c) & 0xff)              /* original at 0x1f46 */
    ldi     r25, ((BOOT_AT + 0x1c) >> 8)                /* original at 0x1f48 */

L1f4a:
    std     Y+17, r25   /* 1f4a: SRAM compact access */
    std     Y+16, r24   /* 1f4e: SRAM compact access */
    ldi     r24, 0x12                        /* 0x1f52: e182 */
    rjmp    L1de2                            /* 0x1f54: cf46 */

L1f56:
    cpi     r24, 0x02                        /* 0x1f56: 3082 */
    brbs    1, L1f5c                         /* 0x1f58: f009 */
    rjmp    L1eca                            /* 0x1f5a: cfb7 */

L1f5c:
    ldi     r24, ((BOOT_AT + 0x0a) & 0xff)              /* original at 0x1f5c */
    ldi     r25, ((BOOT_AT + 0x0a) >> 8)                /* original at 0x1f5e */
    rjmp    L1f4a                            /* 0x1f60: cff4 */

L1f62:
    cpi     r25, 0x08                        /* 0x1f62: 3098 */
    brbs    1, L1f7a                         /* 0x1f64: f051 */
    cpi     r25, 0x09                        /* 0x1f66: 3099 */
    brbc    1, L1f70                         /* 0x1f68: f419 */
    std     Y+21, r18   /* 1f6a: SRAM compact access */
    rjmp    L1f34                            /* 0x1f6e: cfe2 */

L1f70:
    ldi     r24, 0x01                        /* 0x1f70: e081 */
    cpi     r25, 0x0a                        /* 0x1f72: 309a */
    brbs    1, L1f34                         /* 0x1f74: f2f9 */
    ldi     r24, 0x00                        /* 0x1f76: e080 */
    rjmp    L1f34                            /* 0x1f78: cfdd */

L1f7a:
    ldi     r18, 0x15                        /* 0x1f7a: e125 */
    ldi     r19, 0x01                        /* 0x1f7c: e031 */
    ldi     r24, 0x01                        /* 0x1f7e: e081 */

main_tail:
    rjmp    L1f22                            /* 0x1f80: cfd0 */

L1f82:
    /* Removed 0x1f82: sbi     0xb, 0 (size-optimized, see CHANGES.md) */
    /* Removed 0x1f84: rjmp    L1e84 (size-optimized, see CHANGES.md) */
