"""Exhaustive relative-control-flow comparison of the relaid-out dispatcher."""
import unittest, random
from emulator_diff_test import Sim, BASE, OPT, randcase

class DispatcherDifferential(unittest.TestCase):
    def test_every_command_byte_idle_state(self):
        rng=random.Random(0x151A88)
        counts={}
        for cmd in range(256):
            for idle in (0,1,0x100,0xffff):
                seed=randcase(rng,(cmd+idle)%1200)
                seed['registers'][3]=cmd
                seed['registers'][28]=idle&255
                seed['registers'][29]=idle>>8
                sims=(Sim(BASE,seed),Sim(OPT,seed))
                outcomes=[]
                for x in sims:
                    x.pc=x.labels['L1d7e']
                    for _ in range(100):
                        if x.pc==x.labels['L1d9c']:
                            outcomes.append('dispatch');break
                        if x.pc==x.labels['L1eac']:
                            outcomes.append('exit');break
                        x.step()
                    else:self.fail(f'did not terminate {cmd=}, {idle=}: {hex(x.pc)}')
                self.assertEqual(outcomes[0],outcomes[1],(cmd,idle))
                self.assertEqual(sims[0].m,sims[1].m,(cmd,idle,'SRAM'))
                self.assertEqual(sims[0].flags,sims[1].flags,(cmd,idle,'SREG'))
                self.assertEqual(sims[0].r,sims[1].r,(cmd,idle,'registers'))
                self.assertEqual(sims[0].io,sims[1].io,(cmd,idle,'I/O'))
                counts[outcomes[0]]=counts.get(outcomes[0],0)+1
        self.assertEqual(sum(counts.values()),1024)

if __name__=='__main__':unittest.main()
