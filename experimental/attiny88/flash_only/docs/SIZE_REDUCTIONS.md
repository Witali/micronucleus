# Measured size reductions

All measurements use no LED at BOOT_AT0x1A40. Receiver qualification remains open.

## Reuse EP0 SETUP validation in foreground

Reuse the existing received-length and token validator instead of repeating its length check. This saves six bytes; the valid-SETUP path retains its timing. Non-SETUP service adds seven cycles, covered by the real-IN polling test.

Measured image: 1402 bytes.

## Pack CRC payload termination into the byte counter

Predecrement the packed payload-byte counter and use borrow for termination. Eight increments of32 preserve its low byte-count remainder. This saves two bytes and one cycle per copied byte; empty DATA remains unchanged. Independent emitted-packet CRC tests cover2304 payloads.

Measured image: 1400 bytes.

## Share cold-start and USB-reset control initialization

Cold startup and USB bus reset share the fail-closed control initializer. Startup retains the full context clear and disconnect loop; bus reset adds seven call/return cycles outside packet sampling. Both callers prove R24:R25 zero. Poisoned-state tests exercise1536 unselected-page guards.

Measured image: 1388 bytes.
