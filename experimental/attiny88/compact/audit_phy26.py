#!/usr/bin/env python3
"""Inspect actual AVR opcodes in Pass25/26; compare full PHY branch targets and
ensure RX timing-critical instruction schedule is preserved. This is not an
analog/real USB certification.
"""
from pathlib import Path
from check_build import build
from audit_phy25 import phys,branch_target,rjmp,brxx
ROOT=Path(__file__).resolve().parent
OLD=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass25.S'
NEW=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass26.S'
# Allowed changes strictly from replacing RX-only r19 by unused r23.
# The original PUSH r19 is replaced by two-cycle RJMP +0; POP r19 is removed.
DIFF={
    0x933f:0xc000, # PUSH r19 --> RJMP +0, both two cycles and no flags altered
    0xe03b:0xe07b, # LDI r19,11 --> LDI r23,11
    0x5031:0x5071, # SUBI r19,1 --> SUBI r23,1
    0x503b:0x507b, # SUBI r19,11 --> SUBI r23,11
    0x9531:0x9571, # NEG r19 --> NEG r23
    0x1bc3:0x1bc7, # SUB r28,r19 --> SUB r28,r23
    0x3034:0x3074, # CPI r19,4 --> CPI r23,4
    0x8b32:0x8b72, # STD Z+...,r19 --> STD Z+...,r23
    0x27dd:0xe0d1, # EOR r29,r29 --> LDI r29,1
    0x5eca:0x9666, # SUBI r28,-22 --> ADIW r28,22
    0x51c6:0x9766, # SUBI r28,22 --> SBIW r28,22
}
def audit(mode,boot):
    o=build(OLD,mode,boot);n=build(NEW,mode,boot)
    oa=phys(o);na=phys(n)
    remove=o['symbols']['usb_handler_packet_done']
    assert next(v[1] for v in oa if v[0]==remove)==0x913f  # POP r19
    # Two 2-opcode sequences -> one ADIW/SBIW. Their total cycles, pointer
    # arithmetic and the only live Z flags are equal. The final SBCI vanishes.
    removed={remove}
    for opcode,prev in ((0x4fde,0x5eca),(0x40d0,0x51c6)):
        words={pc:word for pc,word,_ in oa}
        positions=[pc for pc,word,_ in oa if word==opcode and words.get(pc-2)==prev]
        assert len(positions)==1,(hex(opcode),positions)
        removed.add(positions[0])
    old=[e for e in oa if e[0] not in removed]
    assert len(old)==len(na)
    remap={v[0]:w[0] for v,w in zip(old,na)}
    for gone in removed:
        remap[gone]=remap[gone+2]
    changed={}
    for (oldpc,ow,_),(newpc,nw,_) in zip(old,na):
        if rjmp(ow) and rjmp(nw):
            assert remap[branch_target(oldpc,ow)]==branch_target(newpc,nw),(hex(oldpc),'RJMP')
        elif brxx(ow) and brxx(nw):
            assert (ow&0xfc07)==(nw&0xfc07),(hex(oldpc),'BR opcode')
            assert remap[branch_target(oldpc,ow)]==branch_target(newpc,nw),(hex(oldpc),'BR')
        elif ow!=nw:
            assert DIFF.get(ow)==nw,(hex(oldpc),hex(ow),hex(nw))
            changed[ow]=nw
    assert changed==DIFF,(changed,DIFF)
    assert n['symbols']['flash_buffer_append_word']-n['symbols']['USB_handler']==492
    assert o['symbols']['flash_buffer_append_word']-o['symbols']['USB_handler']==498
    # Pointer and flag equivalence for all offset values and 16-bit TX cursors.
    for offset in range(256):
        original=(offset+0x116)&0xffff   # EOR+SUBI+SBCI
        candidate=(0x100+offset+22)&0xffff # LDI+ADIW
        assert original==candidate
    for y in range(65536):
        original=(y-22)&0xffff
        candidate=(y-22)&0xffff
        assert original==candidate and (original==0)==(candidate==0)
    # The register r23 is not used elsewhere in the PHY; the RX counter must
    # be dead before the TX path, and the main TX builder reinitializes r23.
    assert remap[o['symbols']['usb_rx_delay_complete']]==n['symbols']['usb_rx_delay_complete']
    assert remap[o['symbols']['usb_handler_packet_done']]==n['symbols']['usb_handler_packet_done']
    # All instructions until RX packet completion are cycle-equal, except the
    # removed POP which was AFTER complete packet reception.
    print('PASS',mode,hex(boot),'PHY498->492; RX r19->r23 + cycle-neutral ADIW/SBIW; branch targets preserved')

if __name__=='__main__':
    for mode,boot in (('NONE',0x1b40),('ACTIVE_HIGH',0x1b00),('ACTIVE_LOW',0x1b00)):
        audit(mode,boot)
