"""A differential crossover must not turn an overlong token into dribble.

USB 2.0 Section 7.1.4.1/Table 7-10 permits a short both-low observation at a
transition; it is not EOP. This conservative digital fixture never claims
that the exact AVR board produces every modeled PIN observation.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_usb_crossover import single_crossover


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
                            cpu=h.CPU(art,wire,entry);cpu.m[0x10f]=0x5a;cpu.r[8]=token[2]
                            for _ in range(16000):
                                if cpu.pc==0xfffe:break
                                cpu.step()
                            else:raise AssertionError('Overlong token did not terminate')
                            context=(ones,rate,sign,crossing,fraction,entry)
                            assert not cpu.bus_events,('crossover authorized an overlong token',context,cpu.bus_events[:3])
                            assert cpu.m[0x10f]==0x5a and cpu.r[3]==0,('bad token changed transfer ownership',context)
                            cases+=1
    print('PASS no overlong-token admission through partial/crossover EOP aliases:',cases,'wire cases')


if __name__=='__main__':test()
