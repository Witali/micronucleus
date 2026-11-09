"""Keep actual PLL PID timing and choose +6 line/run roots in runtime code."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
name='build'
base=HERE/'inputs/pll128-balanced.inc'
text=base.read_text().split('legacy_USB_handler:')[0]
# The final raw SET predecessor cannot be a valid complemented PID.
text=text.replace('pll128_bit0AfterSet:\n','pll128_bit0AfterSet:\n    rjmp hybrid_bad_pid_line\n',1)
# Startup has a paid one-clock slot, and R21 is otherwise unused by PLL.
needle='pll128_pid_start:\n    rjmp .+0\n    nop\n'
assert text.count(needle)==1
text=text.replace(needle,'pll128_pid_start:\n    rjmp .+0\n    ldi r21, 4\n')
# CLR after real bit6 zero reaches run1; unchanged bit6 uses actual inverse
# PID5 to choose run2/run3 before bit7, without altering its sample clock.
needle='''    andi    shift, (255 ^ (3 << 6))
    cpi     shift, 2
    nop
    nop
    in      phase, USBIN
    brlt    pll128_unstuff6c
    rjmp    pll128_bit7AfterClr
'''
assert text.count(needle)==1
def final_one(label,run):
    return f'''{label}:
    ifioset USBIN, USBMINUS
    rjmp hybrid_bad_pid_line
    andi shift, (255 ^ (1 << 7))
    eor r18, r16
    ldi r20, 2
    nop
    in r19, USBIN
    nop
    rjmp rx_p2_K_r{run}
'''
replacement='''    andi shift, (255 ^ (3 << 6))
    cpi shift, 32
    nop
    nop
    in phase, USBIN
    brcs hybrid_run3_pad
    nop
    nop
'''+final_one('hybrid_pid7_run2',2)+'''hybrid_run3_pad:
    nop
'''+final_one('hybrid_pid7_run3',3)
text=text.replace(needle,replacement)
start=text.index('pll128_bit7AfterClr:\n')
end=text.index('pll128_unstuff7c:\n',start)
text=text[:start]+final_one('pll128_bit7AfterClr',1)+text[end:]
# A last logical zero does not need the previous +6 sample. Retire phase
# capture and complete the PID early enough to pay a real RJMP to run0.
start=text.index('pll128_bit7IsClr:\n')
end=text.index('pll128_bit0AfterClr:\n',start)
text=text[:start]+'''pll128_bit7IsClr:
    ifrset phase, USBMINUS
    lpm r23, Z
    ori shift, 1 << 7
    eor r18, r16
    ldi r20, 2
    rjmp rx_p2_K_r0

'''+text[end:]
# No valid PID should reenter the old DATA loop.
text=text.replace('pll128_bit0AfterClr:\n','pll128_bit0AfterClr:\n    rjmp hybrid_bad_pid_line\n',1)
source=HERE/'inputs/extra6.S'
graph=source.read_text();graph=graph[graph.index('rx_p1_J_r2_inline_0_second_zero:'):]
graph=graph[:graph.index('usb_control_process_received_packet:')]
stub='''hybrid_bad_pid_line:
usb_rx_ignore_packet:
    ret
'''
out=HERE/name;out.mkdir(exist_ok=True)
phy=text+stub+graph
(out/'vusb_phy.inc').write_text(phy)
def wsl(p):return p.relative_to(HERE).as_posix()
(out/'candidate.S').write_text(f'''#include "../inputs/source/device_attiny88.inc"
#include "../inputs/source/compact_protocol.inc"
    .text
    .org BOOT_AT
    .global bootloader_start
bootloader_start:
    rjmp USB_handler
#include "vusb_phy.inc"
usb_control_process_received_packet:
bootloader_poll_begin:
bootloader_start_application:
    ret
''')
(out/'manifest.json').write_bytes((HERE/'inputs/extra6-manifest.json').read_bytes())
(out/'source.json').write_text(json.dumps(dict(boot=0x800,
    phy_sha256=hashlib.sha256((out/'vusb_phy.inc').read_bytes()).hexdigest(),
    pll_prefix_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),
    decoder_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    scope='Actual balanced PLL PID through timed runtime run selection into frozen +6 graph. Component only; no packet publication/framing.'),indent=2)+'\n')
print(name)
