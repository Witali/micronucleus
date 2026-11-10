# Shared ACK receiver baseline

This no-LED variant adds an ACK reader to the existing combined PHY and is
the default selection of `verify_receiver.py` and `verify.sh`.
Normal DATA and SYNC retain their known receive findings. The host identity
is FFFF and no recognized programming profile or hardware image is added.
The smaller combined base receiver currently measures 1766 bytes.

The measured body is **1934 bytes at 0x1800**, SHA256
`4f0b3ca3c10f2e68d9b730a99f44bf4653b14e11b48870ca178d346aa5541497`.
That placement reserves 2048 bytes, leaves the application postscript at
0x17FC..0x17FF and permits 6140 application bytes linked at zero. This remains
an experimental software checkpoint, not a qualified replacement loader.

Before the pending-address reduction, a placement measurement at 0x1840 was
1952 bytes, fitting a
1984-byte region (31 pages). It leaves the postscript at 0x183C..0x183F and
6204 application bytes. This is a separate unknown-profile measurement with
its own limited checks, recorded in the November 3 report below.

## Implementation

`ack_receive.inc` contains the separate reader and terminal handler. Small
compile-time hooks in `../combined_rx/vusb_phy.inc` share the existing startup,
normal receive, TX, protocol, Flash and ACK-ownership code.

- PIDbit0 is classified against final SYNC K at the measured acquisition
  phase. A legal SE0/SE1 observation during its zero cannot become an odd PID.
- Six middle bits use a sentinel and one loop with a copied raw SECOND.
  Previous-second versus current-first observations decode permitted erasures
  without a general GPIO-state selector or an expected-line register. A cold
  FIRST-SE0 continuation preserves early EOP rejection and exactly funds the
  copy while retaining the normal sample clocks. This
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
body to 1986 bytes. A single middle loop and shared cold rejection jump save
30 more bytes; the shared TX/context changes save another four. The initial
larger source's stack-return trick is unnecessary
for this ACK-specific fixed tail bound.

## Validation scope

The [November 10 compact transfer](../../docs/COMPACT_USB_TRANSFER_2026_11_10.md)
records the size-neutral atomic full-K confirmation: 85 SYNC cases repaired,
zero new failing contexts across the complete frozen 67-group comparison.
The full gate still exits 1 with 62/67 passing; 59 SYNC and the four other
mandatory finding groups remain open.

The current audit records the exact selected-image results and open findings:
[USB audit](../../docs/USB_AUDIT_2026_11_01.md). New gates cover 2484 positive
ACK crossover cases and 4104 extra-zero tail cases. Their independent voltage
witnesses include both permitted single-ended observation states.

The inherited normal DATA/SYNC failures remain mandatory. A full selector run
must keep reporting them; ACK-only results do not qualify the entire loader.
The 1280-byte target is still unachieved.

The [November 9 full inventory](../../docs/USB_RX_EOP_2026_11_09.md#ack-correctness-baseline)
records all 65 original groups, the additional fractional-DATA gate, and the
separately reviewed forbidden-host-handshake fixture correction. Five
mandatory receive/admission groups still fail; this is not a release.

Three additional gates check 41148 premature raw PID prefixes, 162 empty PIDs
and 252 truncated ACK-to-next-SETUP exchanges. Omitting the early EOP check
saved more bytes but failed 12 of those recovery cases; that shortcut was
rejected. Exact current results and the component-versus-composed distinction
are in the [November 3 record](../../docs/USB_SIZE_2026_11_03.md).

Build or run the complete, strict selection from the Flash-only directory:

```sh
python build.py --where variants/ack_terminal --boot 0x1800 --require-fit
python verify_receiver.py --source variants/ack_terminal --boot 0x1800 --exhaustive
```
