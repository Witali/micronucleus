# USB implementation history and reuse review

## Scope and reproducibility

Both configured remotes were fetched successfully before the review. At
`2528f97`, the repository is not shallow and has 16 local branches and seven
remote refs, including remote HEAD aliases. The index covers all 916 reachable
commits; 275 touch `experimental/attiny88` or `firmware/usbdrv`. Relevant trees
contain 291 distinct assembly-source blobs, including 91 complete-handler
source revisions. These are source revisions, not 91 independent designs.

The index covers every available branch. Focused semantic review follows the
shared receive/timing commits, streaming prototypes, upstream 16 MHz driver
and the seven relevant commits outside the current ancestry. The existing
[historical wire audit](HISTORICAL_USB_RX.md) supplies exact older-image
counterexamples. This review does not claim new full-suite qualification of
every historical image. The local index and linked-region calculation are
under `C:/Work/MicroNucleus/validation/usb-history-nov01/`, outside the Git
repository.

The maintained read-only indexer is
[`reuse_audit.py`](../tools/historical_usb/reuse_audit.py). Run
`python tools/historical_usb/reuse_audit.py` from the Flash-only directory;
its generated inventory is written under ignored `build/history-reuse/`.
It reads the refs already available locally and performs no fetch or build.

## Common paths already present

| Commit | Existing reuse | Current ancestry |
| --- | --- | --- |
| `ab6ab4f` | Context-pointer reuse, useful work in SYNC delay, preloaded receive length | Included |
| `afb9f9e` | Pointer/PCIF handling and return overhead reductions | Included |
| `b6f32be` | Shared framing, byte storage and receive continuations | Included |
| `91c3814` | Identical receive-tail jumps and rejection branches | Included |
| `7fc2e48` | Shared rejection/ACK layout and overflow ownership guard | Included |
| `d8d035b` | Shared qualified-EOP publication with identical parser timing | Included |

These provide real savings already reflected in the current 1788-byte body.
Their presence in another branch does not provide a second independent saving.
The current waveform failures also show why shared code still needs complete
input/ownership tests after integration.

## Useful earlier architecture

Ancestor `56203ee` introduced the read-only streaming receiver; `b113478` records
its later application-only trial. The maintained source is
[`streaming_rx_v2.inc`](../../block64/prototypes/streaming_crc16/source/streaming_rx_v2.inc).

Its useful principle is a true rolling data byte. Consuming a mandatory stuffed
zero leaves the data byte intact. The next five data symbols cannot require
another stuffed zero, so their continuations omit the redundant history test.
Those available instruction slots perform delayed byte stores and other work.
For example, `stream_cooldown_0_1` and `stream_stuff1_sample` publish the pending
byte while maintaining the physical sample schedule.

This can inform the new receiver's publication/state graph. Copying the whole
implementation would add 40 cooldown sample sites and 512 bytes of CRC tables.
Its recorded waveform results use ideal two-bit EOP and exclude minimum-width
EOP and analog crossover tolerance. The successful historical application
trial therefore does not establish acceptance of the newer mandatory cases.
The current Flash-only experiment keeps its sole numeric incoming DATA CRC16
waiver and does not need those tables.

## Changes outside current ancestry

The seven relevant commits outside this branch are `1f33481`, `e37c3f7`,
`3a8488b`, `bf07c7a`, `5f6c58b`, `defc758` and `9017e07`.

`3a8488b` shares a foreground payload-copy/CRC routine and Flash/EEPROM range
checks. Flash-only has one remaining memory source, so extracting that single
copy into a subroutine provides no duplicate implementation to remove.
Its ACK-acquisition changes precede the existing retry/deadline implementation.
`e37c3f7` adds a SETUP/block CRC probe and a generalized copier; it does not
provide a smaller qualified PHY. `5f6c58b` adds native 64-byte reads and retry
state, which changes the command scope rather than simplifying the current
WRITE4/READ8 contract. The other four commits split/move files or record block
transfer plans. No complete smaller receiver closing the present failures was
identified among these changes.

## Where current bytes went

The public installed v3.0 body and frozen current control were checked against
their recorded SHA256 values before calculating these linked boundaries:

| Linked region | Installed v3.0 | Frozen current control | Change |
| --- | ---: | ---: | ---: |
| Before `USB_handler` | 38 | 38 | 0 |
| `USB_handler` through the byte before `startup` | 494 | 1200 | +706 |
| `startup` and remaining code | 616 | 550 | -66 |
| Total body | 1148 | 1788 | +640 |

The current SHA256 is
`0391cefabee6d7170ff8f3c51fcf1b4a852fce5b3a47f8734aea13b5d1f4698a`;
the installed v3.0 SHA256 is
`e2a771412dfacf7a3ad7575d4ccb526791557c157633637ecf0c7fdbb9096df0`.
The USB region includes RX, TX, framing, token admission, ACK ownership and
acknowledged-write staging. It is not a pure PHY/per-feature size measurement.

Part of the growth implements checks missing from v3.0; part comes from
separate timing-specific repair paths. The maximum-packet terminal section
alone spans 228 linked bytes, from `usb_rx_terminal_early_confirm` to `startup`.
This section performs necessary work and cannot simply be deleted. A common
terminal strategy and better scheduled byte publication are concrete reuse
targets. Corrected SYNC acquisition and complete handling of short EOP and
fractional dribble remain required.

The 1280-byte target still requires 508 body bytes of reduction from this
control. Neither the historical architectures nor the new independently tested
components establish that saving yet. The current
[USB audit](USB_AUDIT_2026_11_01.md) records the open receive failures; size
reductions must preserve its PID/payload/count, stuffing, CRC5, timing and
ownership requirements.
