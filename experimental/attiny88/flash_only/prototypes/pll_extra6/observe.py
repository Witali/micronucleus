"""Execute the real PLL prefix and +6 graph without changing runtime state."""
def configure(o,artifact_path):
    import json
    o.ART=o.core.artifact(artifact_path);a=o.ART
    man=json.loads(artifact_path.with_name('manifest.json').read_text())
    o.FIRSTS={a['symbols'][k]:dict(v,name=k) for k,v in man['firsts'].items()}
    o.SHIFTS={a['symbols'][k]:v for k,v in man['shifts'].items()}
    o.EOPS={a['symbols'][k]:dict(v,name=k) for k,v in man['eops'].items()}
    o.REJECTS={a['symbols'][k]:k for k in man['rejects']}
    o.SKIPS={a['symbols'][k]:v for k,v in man.get('physical_skips',{}).items()}
    for k in ('hybrid_bad_pid_line','pll128_eof','pll128_overflow','usb_rx_ignore_packet'):
        o.REJECTS[a['symbols'][k]]=k
    return a

def run(o,packet,wave,entry,capture=False):
    o.bind(o.ART);c=o.h.CPU(o.ART,wave,entry)
    c.r[0]=0xa7;c.r[24:26]=[0xa5,0xb6];c.m[0x115]=0xa0
    initial=c.r[:];memory=bytes(c.m);bits=[(b>>i)&1 for b in packet for i in range(8)]
    count=0;physical=0;history=None;origin=None;handoff=None;errors=[];trace=[];stop=None
    for _ in range(16000):
        if c.pc==0xfffe:stop=dict(kind='unexpected_return');errors.append(stop);break
        if c.pc in o.EOPS or c.pc in o.REJECTS:
            stop=o.EOPS.get(c.pc,dict(kind='reject',name=o.REJECTS.get(c.pc)))
            if c.pc in o.REJECTS:errors.append(dict(kind='reject',name=o.REJECTS[c.pc]))
            if c.pc in o.EOPS and c.t<wave.boundaries[-3]:errors.append(dict(kind='early_eof',time=c.t,eop=wave.boundaries[-3]))
            break
        if c.pc in o.FIRSTS:
            state=o.FIRSTS[c.pc]
            if origin is None:
                origin=c.t;handoff=dict(time=c.t,state=state,registers=c.r[16:24],flags=c.flags)
                count=8;history=c.r[18]
                if history!=packet[0]:errors.append(dict(kind='PID',got=history,wanted=packet[0]))
                assert c.r[20:22]==[o.h.J,o.h.K],('Runtime line constants',c.r[20:22])
                expected=0
                for bit in reversed(bits[:8]):
                    if not bit:break
                    expected+=1
                assert state['run']==expected and state['line']=='K' and state['phase']==2,('Runtime run selection',packet[0],state,expected)
            want=origin+(32*physical+1)//3
            assert abs(c.t-want)<1e-7,('Actual FIRST calendar',state,c.t,want,physical)
            assert state['phase']==(physical+2)%3,('Actual phase',state,physical)
            if capture:trace.append(dict(time=c.t,state=state,bits=count,registers=c.r[16:24]))
            physical+=1
        shift=o.SHIFTS.get(c.pc);physical+=o.SKIPS.get(c.pc,0)
        c.step()
        if shift is not None:
            want=bits[count] if count<len(bits) else 1
            if want!=shift and len(errors)<8:errors.append(dict(kind='bit',position=count,got=shift,wanted=want,time=c.t))
            history=(history>>1)|(shift<<7)
            assert c.r[18]==history,('True decoded history',c.r[18],history,count)
            count+=1
        for reg in [0,*range(2,16),24,25]:assert c.r[reg]==initial[reg],('Protected register',reg)
        assert c.r[30:32]==initial[30:32],'Context Z preservation'
        assert not c.flag(6),'SREG.T preservation from actual entry'
        assert bytes(c.m)==memory and not c.bus_events,'Component SRAM/bus-drive mutation'
    else:stop=dict(kind='instruction_bound');errors.append(stop)
    if origin is None:errors.append(dict(kind='missing_handoff'))
    if count<len(bits) or count>len(bits)+6:errors.append(dict(kind='count',got=count,wanted=len(bits)))
    sample=next((s for s in c.io.samples if s[1]==c.labels['pll128_pid0_sample']),None)
    if sample is None or sample[3]!=8:errors.append(dict(kind='wrong_pid_cell',sample=sample))
    result=dict(errors=errors,stop=stop,bits=count,time=c.t,origin=origin,handoff=handoff,first_sample=sample)
    if capture:result.update(trace=trace,samples=c.io.samples)
    return result
