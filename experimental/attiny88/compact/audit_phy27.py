"""Audit emitted PHY words, timing repairs and shared-return ABI.

Unchanged RX/TX core instructions and branch destinations are compared with
Pass26. Each intentional difference has a separate raw-word contract below.
This structural audit is complemented by synchronized pin-waveform tests; it
does not establish electrical compliance or received-packet CRC admission.
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

def audit_relocation(before, after):
    """Normalize only separately audited Pass26 -> Pass28 replacements."""
    b, a = before['symbols'], after['symbols']
    bs, ass = b['usb_rx_found_k'], a['usb_rx_found_k']
    be, ae = b['usb_tx_finish_eop'], a['usb_tx_finish_eop']
    bfirst, afirst = b['usb_rx_delay_complete'] + 8, a['usb_rx_delay_complete'] + 6
    old = words(before, b['USB_handler'], b['flash_buffer_append_word'])
    new = words(after, a['USB_handler'], a['flash_buffer_append_word'])
    old_ranges = [(b['USB_handler'], b['USB_handler'] + 2), (bs - 2, bs + 12),
                  (b['usb_rx_sync_confirmed'], bfirst),
                  (b['usb_handler_return'], b['usb_handler_return'] + 2),
                  (b['usb_tx_begin_byte'], b['usb_tx_begin_byte'] + 2), (be - 10, be - 8),
                  (b['usb_rx_handle_data'] + 6, b['usb_rx_handle_data'] + 8),
                  (b['usb_rx_handle_in'], b['usb_rx_handle_in'] + 2),
                  (be, b['flash_buffer_append_word'])]
    new_ranges = [(a['USB_handler'], a['USB_handler'] + 2), (ass - 4, ass + 4),
                  (a['usb_rx_sync_confirmed'], afirst),
                  (a['usb_handler_packet_done'] + 6, a['usb_handler_packet_done'] + 8),
                  (a['usb_tx_begin_byte'], a['usb_tx_begin_byte'] + 2),
                  (ae, a['flash_buffer_append_word'])]
    old = [item for item in old if not any(lo <= item[0] < hi for lo, hi in old_ranges)]
    new = [item for item in new if not any(lo <= item[0] < hi for lo, hi in new_ranges)]
    assert len(old) == len(new)
    remap = {x[0]: y[0] for x, y in zip(old, new)}
    for name in set(b) & set(a):
        remap[b[name]] = a[name]
    flag_sites = {b['usb_rx_decode_bit6'] + 6: 2,
                  b['usb_rx_handle_data'] + 14: 2, b['usb_rx_handle_in'] + 4: 4}
    changed_words = {bfirst + 8: (0xc000, 0x8932),
                     b['usb_rx_handle_data'] + 8: (0x2311, 0x2333),
                     b['usb_rx_handle_in'] + 2: (0x3001, 0x3031)}
    seen_flags, seen_words, branches = set(), set(), 0
    for (pc, word, raw), (npc, nword, nraw) in zip(old, new):
        if pc in changed_words:
            assert (word, nword) == changed_words[pc]
            seen_words.add(pc)
        elif word & 0xf000 in (0xc000, 0xd000):
            assert word & 0xf000 == nword & 0xf000
            assert remap[target(pc, word, 12)] == target(npc, nword, 12)
            branches += 1
        elif word & 0xfc00 in (0xf000, 0xf400):
            assert word & 0xfc00 == nword & 0xfc00
            if pc in flag_sites:
                assert word & 7 == 0 and nword & 7 == flag_sites[pc]
                seen_flags.add(pc)
            else:
                assert word & 7 == nword & 7
            assert remap[target(pc, word, 7)] == target(npc, nword, 7)
            branches += 1
        else:
            assert raw == nraw, (hex(pc), hex(npc), hex(word), hex(nword))
    assert seen_flags == set(flag_sites) and seen_words == set(changed_words)
    return branches


def written_registers(word):
    """AVR destinations/auto-index updates used by the emitted firmware."""
    rd = (word >> 4) & 31
    result = set()
    if word & 0xf000 in (0x4000, 0x5000, 0x6000, 0x7000, 0xe000):
        result.add(16 + ((word >> 4) & 15))
    if word & 0xfc00 in (0x0800, 0x0c00, 0x1800, 0x1c00, 0x2000, 0x2400, 0x2800, 0x2c00):
        result.add(rd)
    if word & 0xfe0f in (0x9400, 0x9401, 0x9402, 0x9403, 0x9405, 0x9406, 0x9407, 0x940a,
                         0x9000, 0x9001, 0x9002, 0x9004, 0x9005, 0x9009, 0x900a,
                         0x900c, 0x900d, 0x900e, 0x900f):
        result.add(rd)
    if word & 0xd208 in (0x8000, 0x8008) or word & 0xf800 == 0xb000 or word & 0xfe08 == 0xf800:
        result.add(rd)
    if word & 0xff00 == 0x0100:
        pair = ((word >> 4) & 15) * 2
        result.update((pair, pair + 1))
    if word & 0xff00 in (0x9600, 0x9700):
        pair = 24 + ((word >> 4) & 3) * 2
        result.update((pair, pair + 1))
    if word & 0xfe0f in (0x9001, 0x9002, 0x9005, 0x9201, 0x9202):
        result.update((30, 31))
    if word & 0xfe0f in (0x9009, 0x900a, 0x9209, 0x920a):
        result.update((28, 29))
    return result


def audit_context_contract(art):
    """Z is immutable inside PHY; every caller preserves the startup Y base."""
    s = art['symbols']
    body = words(art, s['USB_handler'], len(art['bytes']))
    z_writes = [(pc, word) for pc, word, _ in body
                if pc < s['flash_buffer_append_word'] and written_registers(word) & {30, 31}]
    assert z_writes == [(s['USB_handler'], 0x01fe)]
    y_writes = [(pc, word) for pc, word, _ in body
                if pc >= s['flash_buffer_append_word'] and written_registers(word) & {28, 29}]
    assert [word for _, word in y_writes] == [0xe2cc, 0xe0d1, 0x921a]
    # Startup's descending clear is bounded by YL=0. All later foreground
    # instructions preserve Y. Calls are the only external PHY entry points.
    callers = [pc for pc, word, _ in body if word & 0xf000 == 0xd000
               and target(pc, word, 12) == s['USB_handler']]
    assert len(callers) == 2
    assert int.from_bytes(art['bytes'][s['USB_handler'] + 2:s['USB_handler'] + 4], 'little') == 0x95c3
    # With YL=0, INC yields one and defines Z/N/V/S before any flag read.
    # EOR's old flag writes are therefore dead for every incoming SREG value.
    return len(callers)


def flags_and_flow(art,entry):
    """Prove flags changed by ADIW are dead until redefined, including callers.

    Raw words supply control flow. Track the actual return stack across calls;
    explore both input/conditional skip outcomes. Start with all ADIW-written
    flags dirty, and reject any read until its independent definition.
    """
    wordmap={pc:(w,len(raw)) for pc,w,raw in words(art,art['symbols']['bootloader_start']+38,len(art['bytes']))}
    calls=[pc for pc,(w,_) in wordmap.items() if w&0xf000==0xd000 and target(pc,w,12)==art['symbols']['USB_handler']]
    assert calls,'No external PHY caller found'
    todo=[(entry,0x1f,(call+2,)) for call in calls]
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


def audit_candidate(reference, candidate, undefined_symbols):
    """Check exact Pass28 replacements; all other core words remain pinned."""
    assert not undefined_symbols, 'Candidate has unresolved ELF symbols'
    before = dict(reference, bytes=bytes(reference['boot']) + reference['body'])
    after = dict(candidate, bytes=bytes(candidate['boot']) + candidate['body'])
    b, a = before['symbols'], after['symbols']
    start = a['usb_rx_found_k']
    fragment = words(after, start, start + 4)
    assert fragment[0][1] == 0xe1c6 and fragment[1][1] & 0xf000 == 0xd000
    delay = target(fragment[1][0], fragment[1][1], 12)
    assert delay == a['usb_return_polynomial']
    assert after['bytes'][delay:delay + 4] == bytes.fromhex('50 ea 08 95')
    context = a['usb_return_context']
    assert after['bytes'][context:context + 6] == bytes.fromhex('ef 01 50 ea 08 95')
    assert 1 + 3 + 1 + 4 == 9
    seed = words(after, a['usb_rx_sync_confirmed'], a['usb_rx_delay_complete'] + 6)
    assert [word for _, word, _ in seed[:2]] == [0xe020, 0xe140]
    assert seed[2][1] & 0xf000 == 0xd000 and target(seed[2][0], seed[2][1], 12) == delay
    assert 1 + 1 + 3 + 1 + 4 == 10
    timeout = words(after, start - 4, start)
    assert timeout[0][1] == 0x9ada and timeout[1][1] & 0xf000 == 0xc000
    assert target(timeout[1][0], timeout[1][1], 12) == context
    returned = a['usb_handler_packet_done'] + 6
    word = int.from_bytes(after['bytes'][returned:returned + 2], 'little')
    assert word & 0xf000 == 0xc000 and target(returned, word, 12) == context
    assert int.from_bytes(before['bytes'][b['usb_tx_begin_byte']:][:2], 'little') == 0xe365
    assert int.from_bytes(after['bytes'][a['usb_tx_begin_byte']:][:2], 'little') == 0xe36b
    eop = a['usb_tx_finish_eop']
    expected = [0x6002, 0xe056, 0x955a, 0xf7f1, 0xb90b, 0x9ada, 0xb11a, 0x7f19,
                0xc000, 0xc000, 0xc000, 0xb91a, 0x9859, 0x01ef, 0xea50, 0x9508]
    assert [word for _, word, _ in words(after, eop, a['flash_buffer_append_word'])] == expected
    assert 2 + 1 + 1 + 2 + 2 + 2 + 1 == 11
    assert b['flash_buffer_append_word'] - b['USB_handler'] == 492
    assert a['flash_buffer_append_word'] - a['USB_handler'] == 478
    audit_context_contract(after)
    branches = audit_relocation(before, after)
    states = flags_and_flow(after, start + 4)
    for pc, word, raw in words(after, a['bootloader_start'] + 38, len(after['bytes'])):
        if word & 0xd208 in (0x8200, 0x8208):
            q = (word & 7) | ((word >> 7) & 24) | ((word >> 8) & 32)
            assert q != 14, ('input buffer offset written', hex(pc))
        if word & 0xfe0f == 0x9200:
            assert int.from_bytes(raw[2:4], 'little') != 0x10e
    return branches, states


if __name__=='__main__':
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
    sys.path.insert(0,str(root))
    from check_build import build
    for mode,boot in (('NONE',0x1c00),('NONE',0x1b40),('ACTIVE_HIGH',0x1b00),('ACTIVE_LOW',0x1b00)):
        old=build(root/'variants/strict_usb_optimized/micronucleus_t88_pass26.S',mode,boot)
        new=build(root/'source/micronucleus_t88_compact.S',mode,boot)
        undefined=subprocess.check_output(['llvm-nm','--undefined-only',str(new['obj'])],text=True).strip()
        branches,states=audit_candidate(old,new,undefined)
        print('PASS',mode,hex(boot),'PHY492->478, three corrected flag operands, 9/10-cycle shared RX setup, useful RX_LENGTH load, 85-cycle TX byte and 11-cycle J,',branches,'branch targets,',states,'flag-liveness states; private Y=context ABI; immutable PHY Z')
