"""Raw-wire fixtures using the shared linked AVR/GPIO execution adapter."""
from functools import lru_cache
from tests35.ep0_model import CPU,build,Wave,token,data_packet,J,K,dec,raw_decode


@lru_cache(maxsize=65536)
def image_decode(base,body,pc):
    assert dec.START==base and dec.raw==body
    return raw_decode(pc)


def cached_decode(pc):return image_decode(dec.START,dec.raw,pc)


def complete_frame_entries(art):
    """Observe complete framing before authorization, including private DATA.

    Some samplers dispatch DATA separately to keep its ACK turnaround short.
    Neither entry by itself proves live recovery J or accepted control state.
    """
    return {art['symbols'][name] for name in
            ('usb_rx_framing_valid', 'usb_rx_data_live_j')
            if name in art['symbols']}


def probe(art,packet,entry=8,address=0,cache=0x10,period=None,wave=None):
    dec.decode=cached_decode
    wave=wave or Wave(packet,start=0,**({'rate':16_000_000/period} if period is not None else {}))
    cpu=CPU(art,wave,entry)
    cpu.m[0x10f]=0x5A
    cpu.m[0x10c]=address;cpu.r[8]=cache
    checkpoints={name:[] for name in ['usb_rx_end_packet','usb_rx_handle_in','usb_rx_handle_setup_or_out','usb_rx_ignore_packet','usb_return_context']}
    at={cpu.labels[name]:name for name in checkpoints}
    for _ in range(10000):
        if cpu.pc==0xFFFE:break
        if cpu.pc in at:checkpoints[at[cpu.pc]].append(dict(time=cpu.t,r=cpu.r[16:24],Y=cpu.word(28)))
        cpu.step()
    else:raise AssertionError('PHY did not return')
    first_k=next((time for time,io,value in cpu.bus_events if io==11 and value&6==4),None)
    return dict(packet=bytes(packet).hex(),checkpoints=checkpoints,context=bytes(cpu.m[0x100:0x12C]).hex(),rx=bytes(cpu.m[0x116:0x121]).hex(),cycles=cpu.t,peak=cpu.peak,bus=cpu.bus_events,response=None if first_k is None else first_k-wave.boundaries[-2])



def eop_wave(packet,width,rate=1_500_000,recovery=J,jitter=None):
    wave=Wave(packet,start=0,rate=rate,jitter=jitter)
    end=wave.boundaries[-3]
    wave.boundaries[-2]=end+width;wave.boundaries[-1]=end+width+wave.period
    wave.levels[-2:]=[recovery,recovery];wave.end=wave.boundaries[-1]
    wave.pin_edges=[];last=J
    for time,level in zip(wave.boundaries,wave.levels):
        if (last^level)&4:wave.pin_edges.append(time)
        last=level
    return wave

def bits_wave(packet,stuff_error=None,tail=()):
    wave=Wave(packet)
    bits=[];ones=0;stuff=[]
    for byte in bytes([0x80])+bytes(packet):
      for bitn in range(8):
       bit=byte>>bitn&1;bits.append(bit);ones=ones+1 if bit else 0
       if ones==6:stuff.append(len(bits));bits.append(0);ones=0
    if stuff_error is not None:bits[stuff_error]=1
    bits.extend(tail)
    wave.bits=bits;wave.boundaries=[];wave.levels=[];wave.labels=[];level=J
    for index,bit in enumerate(bits):
      if bit==0:level=K if level==J else J
      wave.boundaries.append(index*wave.period);wave.levels.append(level);wave.labels.append(index)
    end=len(bits)*wave.period;wave.boundaries.extend([end,end+2*wave.period,end+3*wave.period]);wave.levels.extend([0,J,J]);wave.labels.extend(['SE0','EOP_J','idle']);wave.end=end+3*wave.period
    wave.pin_edges=[];previous=J
    for t,level in zip(wave.boundaries,wave.levels):
      if (previous^level)&4:wave.pin_edges.append(t)
      previous=level
    return wave,stuff

def from_bits(bits,rate=1500000,width=64/3):
    wave=Wave(b'');wave.period=16000000/rate;wave.bits=bits;wave.boundaries=[];wave.levels=[];wave.labels=[];level=J
    for index,bit in enumerate(bits):
      if bit==0:level=K if level==J else J
      wave.boundaries.append(index*wave.period);wave.levels.append(level);wave.labels.append(index)
    end=len(bits)*wave.period;wave.boundaries.extend([end,end+width,end+width+wave.period]);wave.levels.extend([0,J,J]);wave.labels.extend(['SE0','EOP_J','idle']);wave.end=end+width+wave.period
    wave.pin_edges=[];previous=J
    for t,level in zip(wave.boundaries,wave.levels):
      if (previous^level)&4:wave.pin_edges.append(t)
      previous=level
    return wave
