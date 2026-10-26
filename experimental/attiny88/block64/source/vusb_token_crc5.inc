/* Cache the exact EP0 token trailer when SET_ADDRESS is acknowledged.
   Input R18=address<<1, Z=0x0100; preserve R16, Y and Z.
   Scratch R18/R22/R23 and SREG. No per-token CRC loop is needed.
   Fold address bits into the seed: merged_n = CRC_n XOR (address>>n).
   After eleven shifts all token input bits have been consumed (EP0=0).
   Every loop path has equal clocks; the complete helper takes 80 clocks. */
usb_update_token_crc5:
    lsr     r18
    ldi     r23, 0x1f
    eor     r18, r23
    ldi     r23, 0x14            /* Reflected USB CRC5 polynomial. */
    ldi     r22, 11             /* Seven address bits and four zero EP bits. */
usb_token_crc5_bit:
    lsr     r18
    brcc    usb_token_crc5_next
    eor     r18, r23
usb_token_crc5_next:
    dec     r22
    brne    usb_token_crc5_bit
    com     r18
    lsl     r18
    lsl     r18
    lsl     r18
    std     Z+CTX_TOKEN_CRC5, r18
    ret
usb_token_crc5_end:
