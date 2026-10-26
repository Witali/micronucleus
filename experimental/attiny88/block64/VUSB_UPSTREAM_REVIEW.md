# Official V-USB comparison

Reviewed on 2026-10-26 against official `obdev/v-usb` master commit
`801242072fa035e1839e3571df0d9a18e9cec95c`. This comparison concerns the
bundled `firmware/usbdrv` sources and the 16 MHz streaming-CRC investigation;
it does not replace the maintained Block64 receiver.

## What is old or specialized locally

The bundled `usbdrv.h` defines `USBDRV_VERSION` as `20121206`. The local
`usbdrvasm16.inc` explicitly records a May 2020 modification converting the
interrupt handler into a plain `USB_handler` function to save space.

After removing comments and normalizing whitespace, comparison with the
official 16 MHz module shows these differences:

- The official entry is `USB_INTR_VECTOR`, with interrupt register/SREG
  preservation. The local entry uses the Micronucleus function convention.
- Local dummy PUSH/POP instructions retain timing where the original saved
  registers. Several corresponding register restores are omitted locally.
- The local synchronization prefix clears YL explicitly.
- Optional official SOF counter and hook code is absent locally.

The sampled-bit receive loop and transmit core have no new upstream
16 MHz RX-CRC implementation to transplant. A wholesale file replacement
would also change the entry/exit convention and stack contract; it is not
a safe library-version-only change.

The bundled 18 MHz CRC module has an even smaller normalized difference:
the entry label and optional SOF hook/counter. Its streaming CRC algorithm
and timing core match the reviewed official module.

## What current upstream supports

The official [clock dispatcher](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm.S)
selects `usbdrvasm18-crc.inc` when `USB_CFG_CHECK_CRC` is enabled, and accepts
only `USB_CFG_CLOCK_KHZ == 18000` in that branch. Other frequencies cause
an explicit assembler preprocessing error. The ordinary 16000 branch
selects `usbdrvasm16.inc` with CRC checking disabled.

Therefore, upgrading to this upstream revision does not provide RX CRC16
at the board's confirmed 16 MHz oscillator frequency. The official
[18 MHz CRC receiver](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm18-crc.inc)
remains a useful algorithmic reference, while the
[16 MHz receiver](https://github.com/obdev/v-usb/blob/801242072fa035e1839e3571df0d9a18e9cec95c/usbdrv/usbdrvasm16.inc)
provides the fractional-cycle synchronization and unstuffing reference.
Twelve clocks per bit at 18 MHz cannot be copied into a receiver with
10 2/3 nominal clocks per bit at 16 MHz.

## Timing consequences

The [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification),
section 7.1.18.1, measures response spacing from the SE0-to-J transition
ending EOP to the next J-to-K transition starting SOP. The detachable-cable
maximum is 6.5 low-speed bit times, or 69 1/3 nominal CPU clocks at 16 MHz.
An EOP-sample-to-transmit count alone is not this measurement.

Section 7.1.11 permits a low-speed function transmitter frequency error of
1.5%; host and hub transmitters have a 0.05% clock accuracy requirement.
These frequency limits, input-edge jitter and sample placement are separate
parts of the timing analysis. Individual integer CPU instruction intervals
cannot each approximate a 10 2/3-clock bit to 1%; the schedule must distribute
10/11-clock intervals and measure the resulting sample phase.

The standalone streaming prototype must pass actual-opcode checks for
CRC, complete packet turnaround, all synchronization phases, stuffing and
legal transition-free EOP tails before a hardware trial. An ordinary-packet
pass does not excuse an EOP/dribble failure. No board programming or
installed bootloader change is part of this comparison.
