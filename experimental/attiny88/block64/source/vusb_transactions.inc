/* Host handshakes have no address or CRC field. Accept exactly one ACK byte,
   only after our own DATA transmission and within its bounded SOP window. */
usb_host_ack:
    ldd     r18, Z+CTX_TX_ACK_WINDOW
    std     Z+CTX_TX_ACK_WINDOW, r1
    cpi     r19, 1
    brne    usb_host_ack_done
    tst     r18
    breq    usb_host_ack_done
    ldd     r16, Z+15
    ldi     r18, EP0_NAK
    std     Z+15, r18
    /* An aborted SET_ADDRESS was reset by the next validated SETUP. */
    ldd     r18, Z+19
    add     r18, r18
    ldd     r17, Z+12
    cp      r17, r18
    breq    usb_host_address_unchanged
    std     Z+12, r18
    /* SET_ADDRESS has a 2 ms host recovery interval. Cache once here,
       rather than computing CRC5 in every timing-critical token response. */
    rcall   usb_update_token_crc5
usb_host_address_unchanged:
    /* DATA-stage ACKs cannot authorize memory operations or application exit. */
    cpi     r16, 4
    brne    usb_host_ack_done
    ldd     r18, Z+CTX_CONTROL_OWNER
    tst     r18
    breq    usb_host_ack_done
    ori     r18, OWNER_ACKED
    std     Z+CTX_CONTROL_OWNER, r18
usb_host_ack_done:
    rjmp    L1be8

/* A validated new SETUP aborts the previous unacknowledged control transfer.
   Already ACKed Flash/RUN is committed. EEPROM already writing is allowed to
   finish, but loses ownership of the previous transfer's status response. */
usb_abort_unacknowledged_control:
    ldd     r18, Y+CTX_CONTROL_OWNER
    sbrc    r18, 7
    ret
    std     Y+CTX_CONTROL_OWNER, r1
    ldd     r18, Y+57
    cpi     r18, ST_WRITE_EEPROM
    breq    usb_control_abort_done
    cpi     r18, ST_RUN
    brlo    usb_control_abort_done
    std     Y+57, r1
    ldi     r18, RESULT_FAIL
    std     Y+56, r18
usb_control_abort_done:
    ret

/* A CRC-valid DATA1 empty OUT completes a control read even if the host's
   last IN ACK was lost. It never acknowledges an outstanding mutation. */
usb_control_read_status:
    ldd     r18, Y+CTX_CONTROL_OWNER
    tst     r18
    breq    usb_control_read_complete
    sbrs    r18, 7
    rjmp    L1df8
usb_control_read_complete:
    std     Y+CTX_TX_ACK_WINDOW, r1
    ldi     r18, EP0_NAK
    std     Y+15, r18
    ldi     r18, EMPTY_MESSAGE
    std     Y+0, r18
    rjmp    L1df8
