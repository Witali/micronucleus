/* Opt-in receive publication after the ACK transmitter has released USB.
 * Include immediately after L1be8, before its existing ACK-window handling.
 *
 * Entry contract:
 *   Z=0x0100; TX preserves Z, R24, R25 and R27.
 *   R27=0 on every post-SYNC nonpublication/drop path. The generated
 *   receiver replaces a setup NOP with LDI R27,0 before sampling the PID.
 *   R27=1 only after the ordinary CRC, token and free-buffer gates passed;
 *   R24 then holds the preceding token and R25 the complete packet count.
 *   The generated publish sites use MOVW R24,R18 / LDI R27,1, then ACK TX.
 *   Y is disposable here: handshake TX no longer leaves it at 0x0100.
 *
 * Commit occurs before the handler can acquire another packet. Early SYNC
 * failure exits directly through L1bf0 and never reaches this include.
 * Cost: seven clocks for a pending packet, three clocks otherwise. The
 * timed NRZI transmitter is unchanged; caller/re-entry timing needs its
 * own back-to-back waveform test with hardware-style PCIFR semantics.
 */
stream_publication_check:
    tst     r27
    breq    stream_publication_done
stream_publication_commit:
    std     Z+18, r25
    std     Z+13, r24
    clr     r27
stream_publication_done:
