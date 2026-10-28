# Standard-request size allowances

These reductions follow the USB 2.0 specification rather than introducing
additional protocol waivers. See the specification link in PROTOCOL.md.

- Section 8.5.3.1 permits any payload length for a control-read status inquiry.
  Accept DATA1 status with complete packet overhead; the fixed zero-payload
  test is unnecessary. Keep direction ownership and packet-length admission.
- Section 9.4.7 leaves a nonzero upper wValue byte in SET_CONFIGURATION
  undefined. Use the low configuration byte and retain its 0/1 range check.
- Section 9.4.6 leaves SET_ADDRESS values above 127 undefined. Retain the
  received address byte rather than spending an instruction masking it.
- Section 9.3.1 ignores D7 when wLength is zero. Canonicalize only that case
  for dispatch and retain an IN status stage, including for read requests.

Removing the three unnecessary checks saves eight code bytes. Correct
zero-length direction dispatch costs six bytes, so this correction changes
the no-LED image from 1410 to 1408 bytes at the same placement. The linked
wire tests cover status, reset, read completion and 16 zero-length/retry
sequences. The known receiver dribble failure remains open.
