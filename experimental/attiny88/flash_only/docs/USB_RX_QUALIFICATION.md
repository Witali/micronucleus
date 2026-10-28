# Receiver admission and minimum-gap transactions

The active strict receiver still rejects an ACK with one legal extra final
one bit. The raw dribble regression remains mandatory. A smaller image or a
passing complete-byte packet corpus does not close that finding.

The additional `tests35.test_ack_followup` regression checks a full exchange:
SELECT, WRITE4, its IN-status ACK, and the following SETUP. Its host schedules
the next SETUP from the ACK's physical recovery-J boundary plus exactly two
host bit periods. Receiver return time does not determine this interval.

The test requires both old words to load exactly once, at 0x80/0x82 with data
0x1122/0x3344, cursor 0x84, one eligible old ACK, and R1 restored to zero. It also
requires the following raw SETUP, its shadow fields and its ACK to be correct.
Completing the previous write while losing the next request is a failure.

```sh
python3 -m tests35.test_ack_followup
USB_PHY_EXHAUSTIVE=1 python3 -m tests35.test_ack_followup
```

The default matrix has 225 exchanges; the expanded matrix has 1485. Both vary
all 0..4 legal final-one ACK extensions, three host rates and three observed
EOP widths: 10.72 clocks, two host bits and 24 clocks at 16 MHz. The expanded
matrix covers 33 quarter-clock ACK phases. Final ones are appended after
encoding; a new stuffed symbol must not be invented at the end of the run.
Receiver-observed EOP limits and legal dribble are defined in the
[USB2.0 specification](https://www.usb.org/document-library/usb-20-specification).

One rejected 1490-byte scratch receiver at 0x1A00 passed its raw-packet corpus
but failed 433 of 1485 such exchanges, all at the short 10.72-clock EOP. Its hash
was `d75e806765b2c29c38bdd32a83db64ddc7403c7e7de812f0f998bc873a1e1a05`.
It finished the previous word loads correctly, but classified the ACK late
enough to observe the next packet's SYNC instead of the ACK's recovery J.
This is why the transaction-level regression is an independent admission gate.

ACK recovery evidence must not authorize Flash work before framing and ACK
eligibility are proven. IN/DATA response paths must still reject sustained
SE0 or missing recovery J. Increasing the host gap is not a protocol fix.
These opcode/GPIO tests do not establish analog or physical USB compliance.
