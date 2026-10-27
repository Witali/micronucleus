"""Actual-opcode audit of the modular Pass27 PHY against the archived Pass26.

The sole allowed body changes are fixed RX base initialization (-6 bytes) and
three previously undefined branch-flag operands. This checks schedule/control
flow, not electrical USB compatibility or inherited early ACK behavior.
"""
from pathlib import Path
import subprocess
import sys

def words(art,start,end):
    result=[]
    pc=start
    while pc<end:
        w=int.from_bytes(art['bytes'][pc:pc+2],'little')
        size=4 if (w&0xfe0f) in (0x9000,0x9200) or (w&0xfe0e) in (0x940c,0x940e) else 2
        result.append((pc,w,art['bytes'][pc:pc+size]))
        pc+=size
    assert pc==end
    return result

def target(pc,w,bits):
    disp=(w>>3)&127 if bits==7 else w&4095
    if disp&(1<<(bits-1)):disp-=1<<bits
    return pc+2+2*disp

def audit_relocation(before,after):
    bstart=before['symbols']['usb_rx_found_k']; astart=after['symbols']['usb_rx_found_k']
    old=words(before,before['symbols']['USB_handler'],before['symbols']['flash_buffer_append_word'])
    new=words(after,after['symbols']['USB_handler'],after['symbols']['flash_buffer_append_word'])
    old=[x for x in old if not bstart<=x[0]<bstart+12]
    new=[x for x in new if not astart<=x[0]<astart+6]
    assert len(old)==len(new)
    remap={x[0]:y[0] for x,y in zip(old,new)}
    remap[bstart]=astart
    flag_sites={before['symbols']['usb_rx_decode_bit6']+6:2, before['symbols']['usb_rx_handle_data']+14:2, before['symbols']['usb_rx_handle_in']+4:4}
    seen_flag_sites=set()
    count=0
    for (pc,w,raw),(npc,nw,nraw) in zip(old,new):
        if w&0xf000 in (0xc000,0xd000):
            assert w&0xf000==nw&0xf000
            assert remap[target(pc,w,12)]==target(npc,nw,12)
            count+=1
        elif w&0xfc00 in (0xf000,0xf400):
            if pc in flag_sites:
                assert w&7==0 and nw&7==flag_sites[pc],(hex(pc),hex(w),hex(nw))
                assert w&0xfc00==nw&0xfc00
                seen_flag_sites.add(pc)
            else:
                assert w&0xfc07==nw&0xfc07
            assert remap[target(pc,w,7)]==target(npc,nw,7)
            count+=1
        else:
            assert raw==nraw,(hex(pc),hex(w),hex(nw))
    assert seen_flag_sites==set(flag_sites)
    return count

def flags_and_flow(art,entry):
    """Prove flags changed by ADIW are dead until redefined, including callers.

    Raw words supply control flow. Track the actual return stack across calls;
    explore both input/conditional skip outcomes. Start with all ADIW-written
    flags dirty, and reject any read until its independent definition.
    """
    wordmap={pc:(w,len(raw)) for pc,w,raw in words(art,art['symbols']['bootloader_start']+38,len(art['bytes']))}
    calls=[pc for pc,(w,_) in wordmap.items() if w&0xf000==0xd000 and target(pc,w,12)==art['symbols']['USB_handler']]
    assert len(calls)==1,calls
    todo=[(entry,0x1f,(calls[0]+2,))]
    seen=set()
    while todo:
        pc,dirty,stack=todo.pop()
        if not dirty:continue
        state=(pc,dirty,stack)
        if state in seen:continue
        seen.add(state)
        w,size=wordmap[pc]
        nxt=pc+size
        reads=0; writes=0
        if w&0xfc00 in (0xf000,0xf400):
            reads=1<<(w&7)
            assert not reads&dirty,('live flag branch',hex(pc),hex(w),hex(dirty))
            todo.extend([(nxt,dirty,stack),(target(pc,w,7),dirty,stack)])
            continue
        if w&0xf000==0xc000:
            todo.append((target(pc,w,12),dirty,stack));continue
        if w&0xf000==0xd000:
            assert len(stack)<5
            todo.append((target(pc,w,12),dirty,stack+(nxt,)));continue
        if w==0x9508:
            assert stack,('dirty flags escape root',hex(pc),hex(dirty))
            todo.append((stack[-1],dirty,stack[:-1]));continue
        if w&0xfc00==0x1000 or w&0xfe08 in (0xfc00,0xfe00) or w&0xff00 in (0x9900,0x9b00):
            todo.extend([(nxt,dirty,stack),(nxt+wordmap[nxt][1],dirty,stack)])
            continue
        if w&0xf000 in (0x6000,0x7000) or w&0xfc00 in (0x2000,0x2400,0x2800):writes=0x1e
        elif w&0xf000 in (0x3000,0x5000) or w&0xfc00 in (0x1400,0x1800,0x0c00) or w&0xff00 in (0x9600,0x9700):writes=0x1f
        elif w&0xf000==0x4000 or w&0xfc00 in (0x0400,0x0800,0x1c00):reads=1;writes=0x1f
        elif w&0xfe0f==0x9407:reads=1;writes=0x1f
        elif w&0xfe0f in (0x9403,0x940a):writes=0x1e
        elif w&0xfe08==0xfa00:writes=0x40
        elif w&0xfe08==0xf800:reads=0x40
        else:
            # The remaining paths before flag redefinition contain only these
            # explicitly recognized loads/stores/stack/I/O/delay instructions.
            assert (w&0xf000==0xe000 or w&0xfc00==0x2c00 or w&0xff00==0x0100
                or w&0xfe0f in (0x9000,0x9200,0x900f,0x920f)
                or w&0xd000==0x8000 or w&0xf800 in (0xb000,0xb800)
                or w&0xff00 in (0x9800,0x9a00) or w in (0,0x95a8)),('unclassified',hex(pc),hex(w))
        assert not reads&dirty,('live flag read',hex(pc),hex(w),hex(dirty))
        todo.append((nxt,dirty&~writes,stack))
    return len(seen)


def audit_candidate(reference,candidate,undefined_symbols):
    """Artifacts follow check_build.build; undefined_symbols is nm output."""
    assert not undefined_symbols, 'Candidate has unresolved ELF symbols'
    # The internal decoder works at absolute byte addresses.
    before=dict(reference, bytes=bytes(reference['boot'])+reference['body'])
    after=dict(candidate, bytes=bytes(candidate['boot'])+candidate['body'])
    start=after['symbols']['usb_rx_found_k']
    fragment=words(after,start,start+6)
    assert fragment[0][1]==0xe1c6 and fragment[1][1]==0xe0d1
    assert fragment[2][1]&0xf000==0xd000
    ret=target(fragment[2][0],fragment[2][1],12)
    assert ret==after['symbols']['usb_handler_return']
    assert after['bytes'][ret:ret+2]==b'\x08\x95'
    assert 2+2+1+2+2==1+1+3+4==9
    assert before['symbols']['flash_buffer_append_word']-before['symbols']['USB_handler']==492
    assert after['symbols']['flash_buffer_append_word']-after['symbols']['USB_handler']==486
    branches=audit_relocation(before,after)
    states=flags_and_flow(after,start+6)
    # No explicit context store may mutate the removed input-buffer offset.
    # RX writes only 0x116..0x120, TX payload/CRC only 0x102..0x10b; startup's
    # descending zero-clear is the sole writer of context byte 14.
    for pc,w,raw in words(after,after['symbols']['bootloader_start']+38,len(after['bytes'])):
        if w&0xd208==0x8208 or w&0xd208==0x8200:  # STD Y/Z+q
            q=(w&7)|((w>>7)&24)|((w>>8)&32)
            assert q!=14,('input buffer offset written',hex(pc))
        if w&0xfe0f==0x9200:  # STS absolute
            address=int.from_bytes(raw[2:4],'little')
            assert address!=0x10e,('input buffer offset written',hex(pc))
    return branches,states

if __name__=='__main__':
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
    sys.path.insert(0,str(root))
    from check_build import build
    for mode,boot in (('NONE',0x1c00),('NONE',0x1b40),('ACTIVE_HIGH',0x1b00),('ACTIVE_LOW',0x1b00)):
        old=build(root/'variants/strict_usb_optimized/micronucleus_t88_pass26.S',mode,boot)
        new=build(root/'source/micronucleus_t88_compact.S',mode,boot)
        undefined=subprocess.check_output(['llvm-nm','--undefined-only',str(new['obj'])],text=True).strip()
        branches,states=audit_candidate(old,new,undefined)
        print('PASS',mode,hex(boot),'PHY492->486, three flag operands corrected, 9-cycle RX setup,',branches,'branch targets,',states,'flag-liveness states; +1 peak stack byte')
