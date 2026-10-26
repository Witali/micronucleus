/* Standalone measured CRC candidates. NOT integrated into any USB receiver.
 * Input/output: R24=CRC low, R25=CRC high; input byte R20 is preserved.
 * Scratch: R18, R19, Z and SREG. R0/R1 and all other registers are preserved.
 * The uncomplemented reflected A001 state uses seed FFFF and residual B001.
 *
 * crc_nibble_update uses the requested 32-byte, 16-entry word table. Low
 * entries must begin at page offset 00 and high entries at offset 10.
 * crc_fold_update is a DIFFERENT 16-byte parity-table experiment.
 * The *_preloaded entries require ZH to already select their table page.
 * Page-aligned placement is favorable; alignment padding is not table data.
 */
#ifndef CRC_NIBBLE_TABLE_PAGE
#define CRC_NIBBLE_TABLE_PAGE 0x10
#endif
#ifndef CRC_FOLD_TABLE_PAGE
#define CRC_FOLD_TABLE_PAGE 0x11
#endif

crc_nibble_update:
    ldi     r31, CRC_NIBBLE_TABLE_PAGE
crc_nibble_update_preloaded:
    eor     r24, r20
    /* First nibble: table index, then CRC>>4 XOR the table word. */
    mov     r30, r24
    andi    r30, 0x0f
    lpm     r18, Z
    ori     r30, 0x10
    lpm     r19, Z
    /* Six instructions shift a 16-bit value right by four. */
    swap    r24
    swap    r25
    eor     r24, r25
    andi    r24, 0x0f
    eor     r24, r25
    andi    r25, 0x0f
    eor     r24, r18
    eor     r25, r19
    /* Second nibble. A full byte was XORed before the first step. */
    mov     r30, r24
    andi    r30, 0x0f
    lpm     r18, Z
    ori     r30, 0x10
    lpm     r19, Z
    swap    r24
    swap    r25
    eor     r24, r25
    andi    r24, 0x0f
    eor     r24, r25
    andi    r25, 0x0f
    eor     r24, r18
    eor     r25, r19
crc_nibble_update_return:
    ret
crc_nibble_update_end:

/* The following two candidates derive from AVR-LibC util/crc16.h's
 * _crc16_update. The original R0 temporary is mapped to R19 here.
 * Its copyright and redistribution notice is retained below.
 *
 * Copyright (c) 2002, 2003, 2004 Marek Michalkiewicz
 * Copyright (c) 2005, 2007 Joerg Wunsch
 * Copyright (c) 2013 Dave Hylands
 * Copyright (c) 2013 Frederic Nadeau
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright
 *   notice, this list of conditions and the following disclaimer.
 * * Redistributions in binary form must reproduce the above copyright
 *   notice, this list of conditions and the following disclaimer in the
 *   documentation and/or other materials provided with the distribution.
 * * Neither the name of the copyright holders nor the names of contributors
 *   may be used to endorse or promote products derived from this software
 *   without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

crc_fold_update:
    ldi     r31, CRC_FOLD_TABLE_PAGE
crc_fold_update_preloaded:
    eor     r24, r20
    mov     r30, r24
    swap    r30
    eor     r30, r24
    andi    r30, 0x0f
    lpm     r18, Z
    mov     r19, r24
    mov     r24, r25
    lsr     r18
    ror     r19
    ror     r18
    mov     r25, r19
    eor     r24, r18
    lsr     r19
    ror     r18
    eor     r25, r19
    eor     r24, r18
crc_fold_update_return:
    ret
crc_fold_update_end:

crc_avrlibc_update:
    eor     r24, r20
    mov     r18, r24
    swap    r18
    eor     r18, r24
    mov     r19, r18
    lsr     r18
    lsr     r18
    eor     r18, r19
    mov     r19, r18
    lsr     r18
    eor     r18, r19
    andi    r18, 0x07
    mov     r19, r24
    mov     r24, r25
    lsr     r18
    ror     r19
    ror     r18
    mov     r25, r19
    eor     r24, r18
    lsr     r19
    ror     r18
    eor     r25, r19
    eor     r24, r18
crc_avrlibc_update_return:
    ret
crc_avrlibc_update_end:
