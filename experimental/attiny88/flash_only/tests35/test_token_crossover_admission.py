"""A differential crossover must not turn an overlong token into dribble.

USB 2.0 Section 7.1.4.1/Table 7-10 permits a short both-low observation at a
transition; it is not EOP. This conservative digital fixture never claims
that the exact AVR board produces every modeled PIN observation.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_usb_crossover import single_crossover
from tests35.rx_jitter_patterns import interval_errors
from tests35.test_rx_crossover_asymmetric import signal_witnesses


def receive(art, wire, entry, token):
    """Run the physical handler with a real cached endpoint-zero CRC5."""
    cpu=h.CPU(art,wire,entry);cpu.m[0x10f]=0x5a;cpu.r[8]=token[2]
    for _ in range(16000):
        if cpu.pc==0xfffe:
            return cpu
        cpu.step()
    raise AssertionError('Overlong token did not terminate')


def check_adjacent(art):
    """Separate legal pulses cannot terminate a valid three-byte prefix."""
    bind(art)
    signal_witnesses()
    token=h.token(0x69)
    packet=token+b'\x00'
    prefix=len(h.Wave(token).bits)
    failures=[]
    cases=0
    for rate in (1499250,1500000,1500750):
        for sign in (-1,0,1):
            for entry in (5,8,16,24,32,38):
                def pristine():
                    return h.Wave(packet,rate=rate,
                                  jitter=lambda index,line:sign*(.55 if line==h.J else -.55))
                wire=pristine()
                interval_errors(wire)
                assert wire.bits[prefix:prefix+2]==[0,0]
                # Both complete analog transitions settle to the rails;
                # their +250/-250 ns tails do not overlap.
                assert (wire.boundaries[prefix+1]-wire.boundaries[prefix])*62.5>500
                control=receive(art,wire,entry,token)
                assert not control.bus_events and control.m[0x10f]==0x5a and control.r[3]==0
                wire=pristine()
                single_crossover(wire,prefix+1,width=3.36,fraction=20/21)
                single_crossover(wire,prefix,width=3.36,fraction=1/21)
                cpu=receive(art,wire,entry,token)
                if cpu.bus_events or cpu.m[0x10f]!=0x5a or cpu.r[3]!=0:
                    failures.append(dict(rate=rate,sign=sign,entry=entry,
                                         true_eop=wire.boundaries[-3],events=cpu.bus_events,
                                         tx_length=cpu.m[0x10f],pending=cpu.r[3]))
                cases+=1
    assert cases==54
    return dict(bytes=art['size'],sha256=art['sha256'],cases=cases,
                pristine_controls=54,failures=failures)


def test():
    art=h.build();bind(art);cases=0
    token=h.token(0x69)
    prefix=len(h.Wave(token).bits)
    for ones in range(1,9):
        packet=token+bytes([(1<<ones)-1])
        for rate in (1499250,1500000,1500750):
            for sign in (-1,0,1):
                jitter=lambda index,line:sign*0.55*(1 if line==h.K else -1)
                plain=h.Wave(packet,rate=rate,jitter=jitter)
                crossings=[None]+[index for index in range(prefix,len(plain.bits))
                                   if plain.levels[index]!=plain.levels[index-1]]
                for crossing in crossings:
                    for fraction in ((0,) if crossing is None else (0,0.5,1)):
                        wire=h.Wave(packet,rate=rate,jitter=jitter)
                        if crossing is not None:wire=single_crossover(wire,crossing,width=3.36,fraction=fraction)
                        for entry in (5,8.25,16.5,24.75,32,38.25):
                            cpu=receive(art,wire,entry,token)
                            context=(ones,rate,sign,crossing,fraction,entry)
                            assert not cpu.bus_events,('crossover authorized an overlong token',context,cpu.bus_events[:3])
                            assert cpu.m[0x10f]==0x5a and cpu.r[3]==0,('bad token changed transfer ownership',context)
                            cases+=1
    assert cases==5454
    adjacent=check_adjacent(art)
    import json
    output=h.ROOT/'build'/('adjacent-token-'+art['sha256'][:16]+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(adjacent,indent=2)+'\n')
    assert not adjacent['failures'],('adjacent pulses authorized an overlong token',adjacent['failures'][:3])
    print('PASS no overlong-token admission:',cases,'single-pulse;',
          adjacent['cases'],'adjacent-pulse;',adjacent['pristine_controls'],'pristine cases')


if __name__=='__main__':test()
