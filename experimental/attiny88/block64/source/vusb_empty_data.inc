/* Validate the control-IN status OUT without a slow foreground CRC call.
   Entry: decoded R19<4, Y points to RX PID, Z=0x0100, R16=PID,
   R18=preceding token, R17=0 and the receive buffer is free.
   Empty DATA has exactly PID + CRC16(00 00); status always uses DATA1.
   The valid path takes 18 clocks through its final RJMP, before ACK setup.
   No nonempty DATA CRC or general RX waveform validation is implied. */
usb_rx_empty_data:
    cpi     r19, 3
    brne    usb_rx_empty_invalid
    cpi     r16, 0x4b            /* USB DATA1 status packet */
    brne    usb_rx_empty_invalid
    cpi     r18, 0xe1            /* USB OUT token */
    brne    usb_rx_empty_invalid
    ldd     r16, Y+1             /* CRC low byte for an empty payload */
    ldd     r17, Y+2             /* CRC high byte */
    or      r16, r17
    brne    usb_rx_empty_invalid
    std     Z+18, r19            /* Publish three decoded bytes, no payload. */
    std     Z+13, r18            /* Foreground sees a valid status OUT. */
    rjmp    L1c4c                /* Select ACK only after the CRC check. */

usb_rx_empty_invalid:
    rjmp    L1be8                /* No handshake or receive publication. */
