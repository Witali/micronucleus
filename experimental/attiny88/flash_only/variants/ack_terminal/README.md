# Shared ACK terminal experiment

This opt-in no-LED variant adds an ACK reader to the existing combined PHY.
Normal DATA and SYNC retain their known receive findings. The host identity
is FFFF and no recognized programming profile or hardware image is added.
The default combined receiver still reproduces its 1788-byte body unchanged.

The measured body is **1986 bytes at 0x1800**, SHA256
`243dc20ad94de7b9fb911aeb79b85f209480cf0be94822ee0db0c54e29d2b549`.
That placement reserves 2048 bytes, leaves the application postscript at
0x17FC..0x17FF and permits 6140 application bytes linked at zero. This remains
an experimental software checkpoint, not a qualified replacement loader.

## Implementation

`ack_receive.inc` contains the separate reader and terminal handler. Small
compile-time hooks in `../combined_rx/vusb_phy.inc` share the existing startup,
normal receive, TX, protocol, Flash and ACK-ownership code.

- PIDbit0 is classified against final SYNC K at the measured acquisition
  phase. A legal SE0/SE1 observation during its zero cannot become an odd PID.
- Six middle bits use a sentinel and three rotating raw-register roles.
  Previous-second versus current-first observations decode permitted erasures
  without a general GPIO-state selector or an expected-line register. This
  bounded eleven-clock loop is specific to the short ACK PID.
- Twenty-three two-clock polls cover the legal final stretch. An opposite
  interval can shrink below four clocks between legal SE1 observations;
  a four-clock pin loop can miss real extra zeros. Three full captures at
  low+3/+5/+7 span four clocks and fit a minimum 670 ns received EOP.
- The shared qualifier uses ordinary jumps and does not add a stack frame.
  Its fixed capture slots also classify the final line and clear the old
  pin-change event. TX-length preloading replaces an existing two-clock
  SYNC delay. These useful operations remove later loads and instructions.
- Fixed physical count and exact middle/final PID checks precede the shared
  ACK handler. Eligibility and recovery J still gate address/cache changes
  and Flash-buffer staging. Incoming DATA CRC16 is the existing sole waiver.

The earlier strict ACK reference was 2002 bytes at the same placement.
Delay-slot work, removal of redundant checks and direct jumps reduce that
body by 16 bytes. The initial larger source's stack-return trick is unnecessary
for this ACK-specific fixed tail bound.

## Validation scope

The current audit records the exact selected-image results and open findings:
[USB audit](../../docs/USB_AUDIT_2026_11_01.md). New gates cover 2484 positive
ACK crossover cases and 4104 extra-zero tail cases. Their independent voltage
witnesses include both permitted single-ended observation states.

The inherited normal DATA/SYNC failures remain mandatory. A full selector run
must keep reporting them; ACK-only results do not qualify the entire loader.
The 1280-byte target is still unachieved.

Build or run the complete, strict selection from the Flash-only directory:

```sh
python build.py --where variants/ack_terminal --boot 0x1800 --require-fit
python verify_receiver.py --source variants/ack_terminal --boot 0x1800 --exhaustive
```
