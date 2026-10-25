# MH-Tiny88 application smoke test

This bare-metal application targets ATtiny88 at 16 MHz. It drives only the onboard active-high LED on PD0, following the repository's `t88_default` configuration. The repeating pattern is three 120 ms flashes (180 ms off between flashes), one 800 ms flash, then a 1500 ms pause: a 3.2-second cycle.

Build with Python 3, AVR-GCC, AVR libc, and AVR binutils:

```sh
python3 build.py
```

The output is `build/blink.hex`, limited to at most 1024 Flash bytes. Upload it as an ordinary application through the existing stock bootloader:

```sh
micronucleus --run --timeout 30 build/blink.hex
```

This replaces the previous application. Micronucleus patches RESET and its application postscript; the sample contains no self-programming or EEPROM writes. The board's bootloader and fuses are preserved. No USB application protocol is implemented, so loss of bootloader communication after starting the application is expected and does not by itself prove that the LED loop runs correctly.

Observe at least three complete patterns to confirm execution. Then power-cycle/reconnect the board, allow the bootloader window to expire, and check that the same pattern starts again. To upload another application, run the uploader first and reconnect/reset the board while it waits.

The stock Micronucleus 2.2 protocol does not provide application Flash readback, so uploader success is not an independent byte-for-byte memory verification. Record upload, LED observation, and restart checks separately in the hardware test record.
