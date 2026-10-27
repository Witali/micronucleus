#!/usr/bin/env python3
"""Synthetic 16 MHz D- edge search to compare removed prologue PUSH timing.
Not physical USB; checks bounded sync edge phase under idealized NRZI SYNC.
"""
from math import floor

def dminus_at(t):
    # SOP starts with K, then USB low-speed SYNC K/J alternating. 16 MHz / 1.5 Mbps.
    # K=0, J=1, all nominal 10+2/3 cycle bit cells. First USB SYNC bits.
    return int(floor(t/(32/3))%2 == 1)

def find_k(jitter,pushes):
    # RCALL already occurred at t=jitter. PHY prologue PUSH=2 cycles each, EOR r28=1.
    t=float(jitter)+4*pushes/2 +1
    for _ in range(256):
        t+=1   # INC r28
        if dminus_at(t)==0:
            t+=1+2 # SBIS no skip (1), BRBC taken (2)
            continue
        t+=2 # SBIS with skip of one-word branch
        # 6 unrolled checks; when K, SBIS1+RJMP2, otherwise SBIS2
        for k in range(6):
            if dminus_at(t)==0:
                return ('found',t,k)
            t+=2
        return ('timeout',t,6)
    return ('no_j',t,256)

def test():
    good=0;worst=0;bad=[]
    # Entry jitter across about one SYNC bit. Model ignores line rise time and electrical noise.
    for jitter in range(0,12):
        a=find_k(jitter,2)
        b=find_k(jitter,0)
        if a[0]=='found' and b[0]=='found':
            good+=1
            worst=max(worst,abs(a[1]-b[1]))
        else:bad.append((jitter,a,b))
    print('SYNC model, nominal 16MHz / 1.5 Mbps:')
    print('  both detect K:',good,'of 12 sampled entry phases')
    print('  worst detection timestamp difference:',worst,'CPU cycles')
    print('  other outcomes:',bad)
    # Later entry phases can lock to different SYNC edges. Never claim physical equivalence.
    later=[j for j in range(12,48) if find_k(j,2)[:2] != find_k(j,0)[:2]]
    print('  later-phase differences needing real USB measurement:',later)
    assert later, 'Unexpected: late-phase sensitivity should be explicitly investigated'
    assert good>=9,(good,bad)

if __name__=='__main__':test()
