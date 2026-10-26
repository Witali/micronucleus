/* Host handshakes have no address or CRC field. Accept exactly one ACK byte,
   only after our own DATA transmission and within its bounded SOP window. */
usb_host_ack:
    ldd     r18, Z+CTX_TX_ACK_WINDOW
    std     Z+CTX_TX_ACK_WINDOW, r1
    cpi     r19, 1
    brne    usb_host_ack_done
    tst     r18
    breq    usb_host_ack_done
    ldi     r18, EP0_NAK
    std     Z+15, r18
    /* An aborted SET_ADDRESS was reset by the next validated SETUP. */
    ldd     r18, Z+19
    add     r18, r18
    std     Z+12, r18
usb_host_ack_done:
    rjmp    L1be8
