"""First emitted PC-line/run receiver with an actual +6 GPIO observation.

The graph is continuous and selects all line/run transitions itself. It is a
debugging candidate: two recovered-erasure continuations explicitly reject
until their prefetched next-cell schedules are implemented. No byte stores,
counting or packet admission are claimed by this initial graph.
"""
from pathlib import Path
import itertools,json,sys,random,math
HERE=Path(__file__).resolve().parent
serial=itertools.count()
meta={'entries':{},'firsts':{},'shifts':{},'eops':{},'rejects':{},'states':{},'physical_skips':{}}
second_done=set();different_done=set()
secondary_diff_done=set();pending_zero_diff_done=set()
def sem(p,line,run):return f'rx_p{p}_{line}_r{run}'
def tag(name,kind,reason=None):
    if kind=='eop':meta['eops'][name]=reason
    else:meta['rejects'][name]=reason
    return [name+':','    ret']
def inst(s):return '    '+s
def pending_secondary(name,p,line,depth,first_fallback=True):
    """Retire a previous prefetched ONE's retained SECOND/EXTRA evidence.

    The new FIRST remains on the physical grid. R22 holds the new SECOND
    so the previous SECOND remains available until its conditional gate.
    Phase0 imports Z from a paid previous-cell ANDI. Phases1/2 mask it at1.
    """
    other='K' if line=='J' else 'J';const=20 if line=='J' else 21
    opp=21 if line=='J' else 20;n=next(serial)
    oldzero=name+'_previous_second_zero';newzero=name+'_new_second_zero'
    key=(p,line,first_fallback)
    shared=f'ps_shared_p{p}_{line}_f{int(first_fallback)}'
    different=shared+'_different';firstzero=shared+'_first_zero'
    eof=shared+'_eop';secondary_eof=name+'_secondary_eop';reject=shared+'_unfunded'
    emit_diff=key not in secondary_diff_done
    secondary_diff_done.add(key)
    meta['states'][name]={'phase':p,'line':line,'run':1,'clone_depth':depth,'pending_secondary':True}
    meta['firsts'][name]={'phase':p,'line':line,'run':1,'pending_secondary':True}
    pre=[];childprefix=[];body=[name+':',inst('in r16, 9')]
    if p:
        body += [inst('andi r17, 6'),inst('in r22, 9'),inst('breq '+oldzero),
                 inst('andi r16, 6'),inst(f'cpse r16, r{const}'),inst('rjmp '+different),
                 inst('in r19, 9'),name+'_shift_one:',inst('asr r18'),
                 inst('andi r22, 6'),inst('breq '+newzero)]
    else:
        body += [inst('breq '+oldzero),inst('in r22, 9'),inst('andi r16, 6'),
                 inst(f'cpse r16, r{const}'),inst('rjmp '+different),
                 inst('in r19, 9'),inst('andi r22, 6'),inst('breq '+newzero),
                 name+'_shift_one:',inst('asr r18')]
    meta['shifts'][name+'_shift_one']=1
    child=sem((p+1)%3,line,2)+'_after_pending_one_'+str(n)
    cp,cb=cell(child,(p+1)%3,line,2,depth+1,False);childprefix+=cp;body+=cb
    if emit_diff:
        # FIRST different reaches8 (phase1/2),7 (phase0). IN/CPSE/RJMP
        # preserved Z from this FIRST's mask; the old EXTRA is still retained.
        pre += [different+':',inst('breq '+firstzero),name+'_shift_zero:',inst('lsr r18'),inst('nop')]
        meta['shifts'][name+'_shift_zero']=0
        child=sem((p+1)%3,other,0)+'_after_pending_zero_'+str(n)
        cp,cb=cell(child,(p+1)%3,other,0,depth+1,False);childprefix+=cp;pre+=cb
        pre += [firstzero+':']
        if first_fallback:pre += [inst('andi r19, 6'),inst('breq '+eof)]
        pre += [inst('andi r22, 6'),inst('breq '+eof),inst('rjmp '+reject)]
        pre += tag(eof,'eop',{'kind':'pending_secondary','phase':p,'run':1})
    # Previous SECOND low and EXTRA recovered opposite proves this physical
    # symbol is DATA zero. It was observed early, so do not require a clean
    # present FIRST; a future-edge excursion may already touch it.
    tail = [oldzero+':',inst('andi r19, 6'),inst('breq '+secondary_eof),
            inst(f'cpse r19, r{opp}'),inst('rjmp '+reject),
            name+'_shift_previous_future_zero:',inst('lsr r18'),inst('nop')]
    if not p:tail += [inst('nop')]
    meta['shifts'][name+'_shift_previous_future_zero']=0
    child=sem((p+1)%3,other,0)+'_after_previous_future_zero_'+str(n)
    cp,cb=cell(child,(p+1)%3,other,0,depth+1,False);childprefix+=cp;tail+=cb
    # Current SECOND low. Phase1/2 already shifted the current ONE at8;
    # phase0 branched before its shift, so it is retired explicitly here.
    newrows = [newzero+':',inst('andi r19, 6'),inst('breq '+secondary_eof),
            inst(f'cpse r19, r{opp}'),inst('rjmp '+reject)]
    if not p:
        newrows += [name+'_shift_late_one:',inst('asr r18')]
        meta['shifts'][name+'_shift_late_one']=1
    newrows += [name+'_shift_future_zero:',inst('lsr r18')]
    meta['shifts'][name+'_shift_future_zero']=0
    elapsed=16 if not p else 17
    target=(21,22,21)[p];jump=target-2
    newrows += [inst('nop')]*(jump-elapsed)
    skip=name+'_consumed_future_symbol'
    newrows += [skip+':',inst('rjmp '+sem((p+2)%3,other,0))]
    meta['physical_skips'][skip]=1
    if emit_diff:pre += tag(reject,'reject','pending-secondary recovered FIRST continuation not yet funded')
    body += tag(secondary_eof,'eop',{'kind':'pending_secondary','phase':p,'run':1})
    body += newrows+tail
    return childprefix+pre,body
def pending_zero(name,p,line,depth):
    """Capture the next cell while a nonmatching prefetched FIRST is pending.

    The previous FIRST's zero flag is live on entry. If it is nonzero, that
    previous DATA zero is retired at3 after both current reads are captured.
    Current DATA zero retires at9; current ONE uses a retained-secondary gate.
    """
    n=next(serial);other='K' if line=='J' else 'J';const=20 if line=='J' else 21
    key=(p,line)
    shared=f'pz_shared_p{p}_{line}'
    prevzero=name+'_previous_first_zero';different=shared+'_different'
    firstzero=shared+'_first_zero';eof=shared+'_eop';reject=shared+'_unfunded'
    previous_eof=name+'_previous_first_eop'
    emit_diff=key not in pending_zero_diff_done
    pending_zero_diff_done.add(key)
    meta['states'][name]={'phase':p,'line':line,'run':0,'clone_depth':depth,'pending_previous_zero':True}
    meta['firsts'][name]={'phase':p,'line':line,'run':0,'pending_previous_zero':True}
    pre=[];childprefix=[]
    body=[name+':',inst('in r22, 9'),inst('breq '+prevzero),inst('in r17, 9'),
          name+'_shift_previous_zero:',inst('lsr r18'),inst('andi r22, 6'),
          inst(f'cpse r22, r{const}'),inst('rjmp '+different),
          inst('in r19, 9'),inst('sec'),name+'_shift_one:',inst('ror r18')]
    if p:body += [inst('andi r17, 6') if p==2 else inst('nop')]
    meta['shifts'][name+'_shift_previous_zero']=0
    meta['shifts'][name+'_shift_one']=1
    child=name+'_pending_secondary'
    cp,cb=pending_secondary(child,(p+1)%3,line,depth+1,first_fallback=p!=0)
    childprefix+=cp;body+=cb
    if emit_diff:
        pre += [different+':',inst('breq '+firstzero),name+'_shift_zero:',inst('lsr r18')]
        if p:pre += [inst('nop')]
        meta['shifts'][name+'_shift_zero']=0
        child=sem((p+1)%3,other,0)+'_after_pending_pair_zero_'+str(n)
        cp,cb=cell(child,(p+1)%3,other,0,depth+1,False);childprefix+=cp;pre+=cb
        pre += [firstzero+':',inst('andi r19, 6'),inst('breq '+eof),
                inst('andi r17, 6'),inst('breq '+eof),inst('rjmp '+reject)]
        pre += tag(eof,'eop',{'kind':'pending_zero_pair','phase':p,'run':0})
    pre += [prevzero+':',inst('andi r17, 6'),inst('breq '+previous_eof),inst('rjmp '+reject)]
    pre += tag(previous_eof,'eop',{'kind':'pending_zero_pair','phase':p,'run':0})
    if emit_diff:pre += tag(reject,'reject','pending-zero recovered FIRST continuation not yet funded')
    return childprefix+pre,body
def cell(name,p,line,run,depth=0,allow_prefetch=True):
    assert depth<32,(name,p,line,run)
    n=next(serial);other='K' if line=='J' else 'J';const=20 if line=='J' else 21
    np=(p+1)%3;next_run=run+1 if run<6 else 0
    meta['states'][name]={'phase':p,'line':line,'run':run,'clone_depth':depth}
    meta['firsts'][name]={'phase':p,'line':line,'run':run}
    own=[];childprefix=[];body=[]
    category=0 if run==0 else 6 if run==6 else 1
    coldname=f'cold_p{p}_{line}_r{category}'
    different=coldname+'_different';zero=coldname+'_first_zero'
    second=f'cold_p{p}_{line}_s{int(run==5)}_second_zero'
    second_eop=second+'_eop';first_eop=coldname+'_first_eop'
    unrecovered=coldname+'_unfunded';missing=name+'_missing_stuff'
    veneer=name+'_second_veneer'
    # Every conditional target is an actual timed path, not a host callback.
    body=[name+':',inst('in r16, 9'),inst('andi r16, 6'),inst('in r17, 9'),
          inst(f'cpse r16, r{const}'),inst('rjmp '+different)]
    if run==6:
        body += tag(missing,'reject','mandatory symbol has unchanged NRZI line')
    else:
        body += [inst('andi r17, 6'),inst('in r19, 9'),inst('breq '+veneer)]
        if run==0:
            body += [inst('sec'),name+'_shift_one:',inst('ror r18')]
            meta['shifts'][name+'_shift_one']=1
            if p:body += [inst('nop')]
            child=sem(np,line,1)+'_inline_'+str(n)
            cp,cb=cell(child,np,line,1,depth+1,allow_prefetch);childprefix+=cp;body+=cb
        else:
            body += [name+'_shift_one:',inst('asr r18')]
            meta['shifts'][name+'_shift_one']=1
            if p:body += [inst('rjmp '+sem(np,line,next_run))]
            else:
                body += [inst('nop')]
                child=sem(np,line,next_run)+'_inline_'+str(n)
                cp,cb=cell(child,np,line,next_run,depth+1,allow_prefetch);childprefix+=cp;body+=cb
    if run!=6 and second not in second_done:
        second_done.add(second)
        own += [second+':',inst('andi r19, 6'),inst('breq '+second_eop)]
        # The cold veneer enters at +11. SECOND at +2 was SE0 but EXTRA
        # at +6 has recovered. FIRST equalled the old canonical line, so
        # there was no current edge: this transient proves the NEXT symbol
        # is a transition. Its +6 recovered opposite line validates that
        # zero early. Consume it as DATA or mandatory zero, then rejoin at
        # the physical grid two symbols after this cell.
        own += [inst(f'cpse r19, r{21 if line=="J" else 20}'),inst('rjmp '+unrecovered),
                inst('sec'),name+'_shift_recovered_one:',inst('ror r18')]
        meta['shifts'][name+'_shift_recovered_one']=1
        elapsed=17
        if run!=5:
            own += [name+'_shift_future_zero:',inst('lsr r18')]
            meta['shifts'][name+'_shift_future_zero']=0
            elapsed=18
        target_clock=(21,22,21)[p]
        jump_clock=target_clock-2
        own += [inst('nop')]*(jump_clock-elapsed)
        skip=name+'_consumed_future_symbol'
        own += [skip+':',inst('rjmp '+sem((p+2)%3,other,0))]
        meta['physical_skips'][skip]=1
        own += tag(second_eop,'eop',{'kind':'second_extra','phase':p,'run':run})

    if run!=6:body += [veneer+':',inst('rjmp '+second)]
    if different in different_done:return childprefix+own,body
    different_done.add(different)
    name=coldname;run=category

    # Z from FIRST's ANDI survives CPSE and RJMP, so no redundant CPI is used.
    own += [different+':',inst('breq '+zero)]
    if run==6:
        if p:
            own += [inst('nop'),inst('nop'),inst('rjmp '+sem(np,other,0))]
        else:
            own += [inst('nop'),inst('rjmp '+sem(np,other,0))]
    else:
        own += [name+'_shift_zero:',inst('lsr r18')]
        meta['shifts'][name+'_shift_zero']=0
        if p:
            own += [inst('nop'),inst('rjmp '+sem(np,other,0))]
        else:
            own += [inst('rjmp '+sem(np,other,0))]

    own += tag(first_eop,'eop',{'kind':'first_extra_or_pair','phase':p,'run':run})
    own += [zero+':']
    # The previous +6 sample exists only when the previous physical symbol
    # was DATA one. Run zero follows DATA zero or a mandatory zero.
    if run==6:
        own += [inst('andi r19, 6'),inst('breq '+first_eop)]
        nextfirst=name+'_prefetched_first';nextextra=name+'_prefetched_extra'
        ndiff=name+'_prefetched_different';neop=name+'_prefetched_eop'
        nsecond=name+'_prefetched_second_zero'
        delayed_diff=[]
        if p==0:
            own += [nextfirst+':',inst('in r16, 9'),inst('andi r17, 6'),
                    inst('in r17, 9'),inst('breq '+first_eop)]
            if run==6:own += [inst('andi r16, 6')]
            else:
                own += [name+'_shift_first_recovered_zero:',inst('lsr r18')]
                meta['shifts'][name+'_shift_first_recovered_zero']=0
            own += [inst('andi r17, 6'),nextextra+':',inst('in r19, 9'),
                    inst(f'cpse r16, r{21 if line=="J" else 20}'),inst('rjmp '+ndiff),
                    inst('breq '+nsecond),name+'_shift_prefetched_one:',inst('asr r18')]
            target=21
        else:
            own += [inst('andi r17, 6'),nextfirst+':',inst('in r16, 9'),
                    inst('breq '+first_eop),inst('in r17, 9')]
            if run==6:own += [inst('andi r16, 6')]
            else:
                own += [name+'_shift_first_recovered_zero:',inst('lsr r18')]
                meta['shifts'][name+'_shift_first_recovered_zero']=0
            own += [inst(f'cpse r16, r{21 if line=="J" else 20}'),inst('rjmp '+ndiff),
                    nextextra+':',inst('in r19, 9'),inst('andi r17, 6'),
                    inst('breq '+nsecond),name+'_shift_prefetched_one:',inst('asr r18')]
            target=22 if p==1 else 21
            if p==1:own += [inst('nop')]
        meta['firsts'][nextfirst]={'phase':np,'line':other,'run':0,'pending_previous_zero':run!=6}
        meta['shifts'][name+'_shift_prefetched_one']=1
        child=sem((p+2)%3,other,1)+'_after_first_prefetch_'+str(n)
        cp,cb=cell(child,(p+2)%3,other,1,depth+1,False);childprefix+=cp;own+=cb
        # A prefetched new FIRST/SECOND pair can already be true EOF after
        # the just-recovered zero. Opposite/nonzero DATA remains an explicit
        # safe rejection until its pending-zero continuation is emitted.
        if p:
            # Different leaves the CPSE/RJMP at +18 with Z still from
            # FIRST's ANDI14. A real opposite/SE1 FIRST proves DATA zero;
            # retire it at19 and keep the next FIRST at21/22 unchanged.
            nfirstzero=name+'_prefetched_first_zero'
            own += [ndiff+':',inst('breq '+nfirstzero),
                    name+'_shift_prefetched_zero:',inst('lsr r18')]
            meta['shifts'][name+'_shift_prefetched_zero']=0
            if p==1:own += [inst('rjmp '+sem((p+2)%3,line,0))]
            else:
                own += [inst('nop')]
                child=sem((p+2)%3,line,0)+'_after_first_prefetch_zero_'+str(n)
                cp,cb=cell(child,(p+2)%3,line,0,depth+1,False);childprefix+=cp;own+=cb
            own += [nfirstzero+':',inst('andi r17, 6'),inst('breq '+neop),
                    inst('rjmp '+unrecovered)]
        else:
            child=name+'_mandatory_pending_zero'
            cp,cb=pending_zero(child,(p+2)%3,line,depth+1)
            # Different reaches20. FIRST is already masked but the last Z
            # came from SECOND15; refresh that FIRST flag in the one paid
            # clock before the next physical FIRST21.
            delayed_diff=cp+[ndiff+':',inst('tst r16')]+cb
        own += tag(neop,'eop',{'kind':'prefetched_pair','phase':np,'run':0})
        # The mandatory zero retires no DATA shift and the preceding six
        # ones prove R18.MSB=1. ASR20 therefore replaces SEC/ROR19/20,
        # funding a SECOND-zero test without moving FIRST/SECOND/EXTRA.
        # In particular, a fractional terminal one can put EOP across only
        # its SECOND and EXTRA reads; those observations must be consumed.
        own += [nsecond+':',inst('andi r19, 6'),inst('breq '+neop),
                inst(f'cpse r19, r{const}'),inst('rjmp '+unrecovered),
                name+'_shift_prefetched_recovered_one:',inst('asr r18'),
                name+'_shift_prefetched_future_zero:',inst('lsr r18'),
                inst('nop'),inst('nop'),inst('nop')]
        meta['shifts'][name+'_shift_prefetched_recovered_one']=1
        meta['shifts'][name+'_shift_prefetched_future_zero']=0
        skip=name+'_prefetched_consumed_future_symbol'
        own += [skip+':',inst('rjmp '+sem(p,line,0))]
        meta['physical_skips'][skip]=1
        own += delayed_diff
    elif 1<=run<=5:
        own += [inst('andi r19, 6'),inst('breq '+first_eop)]
        nf=name+'_data_next_first';nx=name+'_data_next_extra';nd=name+'_data_next_different'
        ne=name+'_data_next_eop'
        if p==0:
            own += [nf+':',inst('in r16, 9'),inst('andi r17, 6'),inst('in r17, 9'),
                    inst('breq '+first_eop),name+'_shift_current_zero:',inst('lsr r18'),
                    inst('andi r16, 6'),nx+':',inst('in r19, 9'),
                    inst(f'cpse r16, r{21 if line=="J" else 20}'),inst('rjmp '+nd),
                    inst('sec'),name+'_shift_next_one:',inst('ror r18')]
        else:
            own += [inst('andi r17, 6'),nf+':',inst('in r16, 9'),
                    inst('breq '+first_eop),inst('in r17, 9'),
                    name+'_shift_current_zero:',inst('lsr r18'),inst('sec'),
                    inst('andi r16, 6'),nx+':',inst('in r19, 9'),
                    inst(f'cpse r16, r{21 if line=="J" else 20}'),inst('rjmp '+nd),
                    name+'_shift_next_one:',inst('ror r18')]
            if p==1:own += [inst('andi r17, 6')]
        meta['firsts'][nf]={'phase':np,'line':other,'run':0,'pending_previous_zero':True}
        meta['shifts'][name+'_shift_current_zero']=0
        meta['shifts'][name+'_shift_next_one']=1
        child=name+'_pending_secondary'
        cp,cb=pending_secondary(child,(p+2)%3,other,depth+1);childprefix+=cp;own+=cb
        child=name+'_pending_zero'
        cp,cb=pending_zero(child,(p+2)%3,line,depth+1)
        # All paths in the preceding SAME/pending-secondary graph end in
        # explicit transfers. Put this alternative's cold prefix here so
        # its live-flag BREQ1 target remains near the timed entry.
        own += cp+[nd+':']
        if p in (0,1):own += [inst('nop')]
        own += cb
    elif run==0 and p==0:
        own += [inst('andi r17, 6'),inst('breq '+first_eop)]
        nf=name+'_zero0_next_first';nx=name+'_zero0_next_extra';nd=name+'_zero0_next_different'
        nz=name+'_zero0_next_first_zero';ne=name+'_zero0_next_eop';ns=name+'_zero0_next_second_zero'
        own += [nf+':',inst('in r16, 9'),inst('andi r16, 6'),inst('in r17, 9'),
                name+'_zero0_shift_current:',inst('lsr r18'),
                inst(f'cpse r16, r{21 if line=="J" else 20}'),inst('rjmp '+nd),
                nx+':',inst('in r19, 9'),inst('andi r17, 6'),inst('breq '+ns),
                inst('sec'),name+'_zero0_shift_next_one:',inst('ror r18')]
        meta['firsts'][nf]={'phase':1,'line':other,'run':0,'pending_previous_zero':True}
        meta['shifts'][name+'_zero0_shift_current']=0
        meta['shifts'][name+'_zero0_shift_next_one']=1
        child=sem(2,other,1)+'_after_zero0_one_'+str(n)
        cp,cb=cell(child,2,other,1,depth+1,False);childprefix+=cp;own+=cb
        own += [nd+':',inst('andi r16, 6'),inst('breq '+nz),
                name+'_zero0_shift_next_zero:',inst('lsr r18'),inst('nop')]
        meta['shifts'][name+'_zero0_shift_next_zero']=0
        child=sem(2,line,0)+'_after_zero0_zero_'+str(n)
        cp,cb=cell(child,2,line,0,depth+1,False);childprefix+=cp;own+=cb
        own += [nz+':',inst('andi r17, 6'),inst('breq '+ne),inst('rjmp '+unrecovered)]
        own += tag(ne,'eop',{'kind':'prefetched_pair','phase':1,'run':0})
        # This local second-zero branch is at+18, so the cold handler is+20.
        # Its recovered +6 read proves a third physical zero transition.
        own += [ns+':',inst('andi r19, 6'),inst('breq '+ne),
                inst(f'cpse r19, r{20 if line=="J" else 21}'),inst('rjmp '+unrecovered),
                inst('sec'),name+'_zero0_shift_late_one:',inst('ror r18'),
                name+'_zero0_shift_future_zero:',inst('lsr r18'),
                inst('nop'),inst('nop'),inst('nop')]
        meta['shifts'][name+'_zero0_shift_late_one']=1
        meta['shifts'][name+'_zero0_shift_future_zero']=0
        skip=name+'_zero0_consumed_future_symbol'
        own += [skip+':',inst('rjmp '+sem(0,line,0))]
        meta['physical_skips'][skip]=1
    else:
        own += [inst('andi r17, 6'),inst('breq '+first_eop)]
        if p and run!=6:
            own += [name+'_shift_recovered_zero:',inst('lsr r18')]
            meta['shifts'][name+'_shift_recovered_zero']=0
            child=sem(np,other,0)+'_after_recovered_'+str(n)
            cp,cb=cell(child,np,other,0,depth+1,allow_prefetch);childprefix+=cp;own+=cb
        else:own += [inst('rjmp '+unrecovered)]
    own += tag(unrecovered,'reject','recovered-erasure prefetch continuation not yet funded')
    # Prefixes may contain deep fallthrough children; the owning cold blocks
    # remain directly before the cell's FIRST to retain short AVR branches.
    return childprefix+own,body

out=['/* Debugging candidate; explicit safe rejects mark unfinished cold paths. */',
     '    .text','    .org BOOT_AT','    .global bootloader_start','bootloader_start:',
     'USB_handler:',inst('rjmp '+sem(0,'K',1))]
run_blocks={}
root_blocks={}
for run in (range(7) if '--original-order' in sys.argv else (1,2,3,0,4,5,6)):
    run_blocks[run]=[]
    for line in ('J','K'):
        for p in range(3):
            name=sem(p,line,run);meta['entries'][name]={'phase':p,'line':line,'run':run}
            pre,body=cell(name,p,line,run)
            run_blocks[run]+=pre+body
            root_blocks[name]=pre+body

# Split only after a real unconditional transfer, then keep every conditional
# branch's source-to-target interval in one cluster. This changes placement,
# never a fallthrough, an instruction, or a GPIO clock. The old root ownership
# grouping could accumulate all mutually called cold handlers in one huge
# indivisible chunk, which prevented a nonwrapping layout unnecessarily.
atoms=[];part=[];previous_instruction=''
for rows in root_blocks.values():
    for row in rows:
        part.append(row)
        if row.startswith('    '):
            text=row.strip()
            if (text=='ret' or text.startswith('rjmp ')) and not previous_instruction.startswith(('cpse ','sbrc ','sbrs ')):
                atoms.append(part);part=[]
            previous_instruction=text
    if part:atoms.append(part);part=[]
atomic_labels={row[:-1]:i for i,rows in enumerate(atoms) for row in rows if row.endswith(':')}
intervals=[]
for i,rows in enumerate(atoms):
    for row in rows:
        if row.strip().startswith('breq '):
            j=atomic_labels[row.split()[-1]];intervals.append((min(i,j),max(i,j)))
for start,end in sorted(intervals):
    if not 'merged' in globals():merged=[]
    if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
    else:merged.append((start,end))
clustered={};i=0;index=0
for start,end in merged:
    while i<start:clustered[f'cluster_{index}']=atoms[i];index+=1;i+=1
    clustered[f'cluster_{index}']=[row for atom in atoms[start:end+1] for row in atom]
    index+=1;i=end+1
while i<len(atoms):clustered[f'cluster_{index}']=atoms[i];index+=1;i+=1
root_blocks=clustered

# Choose a placement that needs no program-counter wrap in the unchanged
# independent executor. Hardware wrap within the8KiB device is legal; this
# is a model-coverage constraint, not an ATtiny88 instruction restriction.
labels={};refs=[];sizes={}
for group,rows in root_blocks.items():
    pc=0
    for row in rows:
        if row.endswith(':'):labels[row[:-1]]=(group,pc)
        elif row.startswith('    '):
            if row.startswith('    rjmp '):refs.append((group,pc,row.split()[-1]))
            pc+=1
    sizes[group]=pc
def score(order):
    starts={};at=1
    for group in order:starts[group]=at;at+=sizes[group]
    boot_target=labels[sem(0,'K',1)]
    span=starts[boot_target[0]]+boot_target[1]-1
    cost=max(0,span-2047)**2+max(0,-2048-span)**2
    for group,pc,target in refs:
        tg,off=labels[target]
        span=starts[tg]+off-starts[group]-pc-1
        cost+=max(0,span-2047)**2+max(0,-2048-span)**2
    return cost
preferred=tuple(root_blocks)
layout=preferred if score(preferred)==0 else None
if layout is None:
    rng=random.Random(61009);current=list(preferred);current_score=score(current)
    best=current[:];best_score=current_score
    for trial in range(80000):
        proposal=current[:];a,b=rng.sample(range(len(proposal)),2)
        if trial%3:proposal[a],proposal[b]=proposal[b],proposal[a]
        else:proposal.insert(b,proposal.pop(a))
        value=score(proposal)
        temperature=40000*(1-(trial%20000)/20000)+1
        if value<current_score or rng.random()<math.exp(min(0,(current_score-value)/temperature)):
            current,current_score=proposal,value
        if value<best_score:best,best_score=proposal[:],value
        if value==0:layout=tuple(proposal);break
        if trial%20000==19999:current,current_score=best[:],best_score
assert layout is not None,('No nonwrapping root-block layout found',best_score,sum(sizes.values())*2)
meta['block_layout']=layout
for group in layout:out+=root_blocks[group]
out+=['usb_control_process_received_packet:','bootloader_poll_begin:','bootloader_start_application:',inst('ret')]
(HERE/'extra6-mandatory-zero.S').write_text('\n'.join(out)+'\n')
(HERE/'extra6-mandatory-zero-manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps(dict(source=str(HERE/'extra6-mandatory-zero.S'),states=len(meta['states']))))
