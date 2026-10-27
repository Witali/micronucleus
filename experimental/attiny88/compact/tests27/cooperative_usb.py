#!/usr/bin/env python3
"""Execute cooperative EP0 service against minimum-IPD host waveforms.

Real call/data stack bytes, GPIO/PCINT synchronization and EEPROM CPU stalls
are included. Page erase/write CPU halt time is excluded; deferred command
gating and protected SPM operands are checked separately. Check payload/CRC,
observable NVM effects, SETUP replacement and pending RUN progress. Inbound CRC admission and transaction retry limitations
remain outside this timing checkpoint; no USB compliance claim is made.
"""
from functools import lru_cache
from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_candidate import checked_build
from tests27.waveform_model import (Timed, FlashView, SynchronizedPinIO,
                                    Wave, token, data_packet, crc16, J, K, dec)

art = meta = None
_body_directory = TemporaryDirectory(prefix='micronucleus-cooperative-')
_raw_decode = getattr(dec.decode, '__wrapped__', dec.decode)


def configure(artifact):
    """Bind the exact linked body and clear the decoder cache between profiles."""
    global art, meta
    art = artifact
    body = Path(_body_directory.name) / (artifact['mode'] + '_body.bin')
    body.write_bytes(artifact['body'])
    meta = {'name': 'Pass27 cooperative service', 'start': art['boot'],
            'bin': body, 'o': art['obj'], 'symbols': art['symbols'],
            'step_limit': 500000}
    dec.decode = lru_cache(maxsize=16384)(_raw_decode)


class PinIO(SynchronizedPinIO):
    """Keep all PCIF pipeline events when the host appends a new packet."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wave_count = len(self.wave.waves)

    def get(self, address, default=0):
        if len(self.wave.waves) != self.wave_count:
            fresh = SynchronizedPinIO(self.cpu, self.wave)
            self.flag_events = fresh.flag_events
            self.wave_count = len(self.wave.waves)
        return super().get(address, default)


class ByteStack:
 """Expose PUSH/POP on the same byte stack that stores real return PCs."""
 def __init__(self,shared):self.shared=shared
 def append(self,v):self.shared.append(v)
 def pop(self):return self.shared.pop()
class Calls:
 def __init__(self,shared):self.shared=shared
 def append(self,v):
  v//=2;self.shared.extend([v&255,v>>8])
 def pop(self):
  hi=self.shared.pop();lo=self.shared.pop();return (lo|hi<<8)*2
 def __bool__(self):return bool(self.shared)
class CPU(Timed):
 """Extend emitted-opcode execution with NVM stalls and observable events."""
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs);self.raw_stack=[];self.calls=Calls(self.raw_stack);self.push_stack=ByteStack(self.raw_stack);self.peak_stack=0;self.eeprom=bytearray(64);self.nvm_events=[];self.eeprom_events=[]
 def memread(self,address):
  return self.r[address] if address<32 else super().memread(address)
 def memwrite(self,address,value):
  if address<32:self.r[address]=value&255
  else:super().memwrite(address,value)
 def step(self):
  if self.pc==self.labels['usb_setup_capture_fields']:
   assert not self.raw_stack,('SETUP capture retained a return frame',self.raw_stack)
  if self.pc==self.labels['USB_handler']:
   assert self.word(28)==0x100,('PHY requires Y=context',hex(self.pc),self.word(28))
  if self.pc in (self.labels['USB_handler'],self.labels['usb_rx_found_k']):
   assert self.r[29]==1,('PHY requires YH=1',hex(self.pc),self.r[29])
  dec.START=self.base;dec.raw=bytes(self.flash[self.base:]);ins=dec.decode(self.pc)
  if ins.op=='spm':self.nvm_events.append(dict(command=self.io.get(0x37,0),address=self.word(30),word=self.word(0),time=self.t))
  if ins.op in ('bset','bclr'):
   self.setflag(int(ins.operands),ins.op=='bset');self.pc+=2;self.steps+=1;self.t+=1
  else:ins=super().step()
  if ins.op=='sbi' and ins.operands=='0x1f, 0':
   self.io[0x20]=self.eeprom[self.io.get(0x21,0)&63];self.io[0x1f]&=~1;self.t+=4
  if ins.op=='sbi' and ins.operands=='0x1f, 1':
   self.eeprom_events.append((self.io.get(0x21),self.io.get(0x20)))
   self.t+=2
  self.peak_stack=max(self.peak_stack,len(self.raw_stack))
  return ins
class Stream:
 """Append future host packets while preserving earlier pin and flag events."""
 def __init__(self):self.waves=[]
 @property
 def pin_edges(self):return [edge for wave in self.waves for edge in wave.pin_edges]
 def add(self,packet,start):
  wave=Wave(packet,start=start);self.waves.append(wave);return wave
 def level(self,t):
  for wave in reversed(self.waves):
   if t>=wave.start:return wave.level(t)
  return J
 def cell(self,t):
  for i,wave in reversed(list(enumerate(self.waves))):
   if t>=wave.start:return (i,wave.cell(t))
  return 'pre'
 def edge_since(self,start,end):return any(w.edge_since(start,end) for w in self.waves)

def decode_outputs(writes):
 levels=[level for t,level in writes if level]
 logical=[];state=J;ones=0
 for level in levels:
  bit=int(level==state);state=level
  if ones==6:
   assert bit==0;ones=0
  else:logical.append(bit);ones=ones+1 if bit else 0
 assert len(logical)%8==0,(len(logical),writes)
 return bytes(sum(logical[i+j]<<j for j in range(8)) for i in range(0,len(logical),8))

def run(abort=False,first_sop=24,setup=None,memory='flash',_retain_cpu=False):
 """Feed legal minimum-IPD IN/ACK traffic while a foreground reply is built."""
 stream=Stream();stream.add(token(0x69),first_sop)
 cpu=CPU(meta,{'memory':bytearray(0x300),'registers':[0]*32});cpu.flash=FlashView(cpu.flash,cpu.base)
 cpu.r[21]=0xa0;cpu.pc=cpu.labels['usb_tx_prepare_pending_reply'];cpu.r[28]=0;cpu.r[29]=1;cpu.r[14]=0;cpu.r[15]=5;cpu.r[9]=0xc3
 original=bytes([0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88]);cpu.flash.memory[0x500:0x508]=original
 if memory=='eeprom':cpu.r[14]=16;cpu.r[15]=0x80;cpu.eeprom[16:24]=original
 cpu.m[0x10f]=0x5a;cpu.m[0x100]=8
 if setup is not None:
  cpu.r[28]=cpu.r[29]=0;cpu.r[30]=0;cpu.r[31]=1;cpu.r[16]=2;cpu.r[17]=0;cpu.r[20]=0;cpu.flags=2
  cpu.r[4]=0x20 if setup.get('eeprom') else 0;cpu.r[5]=0x80 if setup.get('eeprom') else 1
  dec.START=art['boot'];dec.raw=art['body'];at=art['symbols']['USB_handler'];releases=[]
  while at<art['symbols']['flash_buffer_append_word']:
   ins=dec.decode(at)
   if ins.op=='out' and ins.operands.startswith('0xa,'):releases.append(ins)
   at+=ins.size
  cpu.pc=releases[-1].address+2;cpu.calls.append(cpu.labels['bootloader_process_pending_command'])
  cpu.m[0x112]=11;cpu.m[0x10d]=0x2d;cpu.m[0x116]=0xc3;cpu.m[0x115]=setup.get('config',0)
  request=setup['request'];value=setup.get('value',0);index=setup.get('index',0)
  length=setup.get('length',0)
  cpu.m[0x117:0x11f]=bytes([setup.get('bm',0x40),request,value&255,value>>8,index&255,index>>8,length&255,length>>8])
 cpu.io=PinIO(cpu,stream);cpu.io.cleared_at=-1
 frames=[];writes=[];driving=False;se0=False;j_at=None;injected=False;entries=[];entry_callers=[];data_seen=False;collected=bytearray()
 expected=bytes(2) if abort else b'' if setup is not None else original
 if setup is not None and not abort:
  if setup['request']==6:
   descriptor=setup['value']>>8;offset=20 if descriptor==1 else 2
   expected=art['body'][offset:offset+min(18,setup.get('length',18))] if descriptor in (1,2) else b''
  elif setup['request'] in (0,8,10):
   prepared=bytes(2) if setup['request']==0 else bytes([setup.get('config',0)]) if setup['request']==8 else bytes(1)
   expected=prepared[:setup.get('length',0)]
 for _ in range(300000):
  if cpu.pc==cpu.labels['USB_handler']:
   entries.append(cpu.t)
   site=((cpu.raw_stack[0]|cpu.raw_stack[1]<<8)*2-2) if len(cpu.raw_stack)>=2 else 0
   labels=[(v,k) for k,v in art['symbols'].items() if art['boot']<=v<=site]
   entry_callers.append(dict(site=hex(site),label=max(labels)[1] if labels else None))
  if cpu.pc in [cpu.labels[k] for k in ['usb_service_pending','usb_control_process_received_packet','usb_tx_copy_flash_payload','usb_crc16_shift_bit']]:
   assert cpu.r[1]==0,('zero register at foreground boundary',hex(cpu.pc),cpu.r[1])
  cpu.executing_pc=cpu.pc;ins=cpu.step()
  if ins.op=='out' and ins.operands.startswith('0xa,'):
   now=cpu.io.get(10,0)&6
   if now==6 and not driving:driving=True;writes=[];se0=False;j_at=None
   elif now==0 and driving:
    frame=decode_outputs(writes);assert frame[0]==0x80
    frame=frame[1:];frames.append({'time':cpu.t,'sop':writes[0][0],'j':j_at,'packet':frame.hex(),'pid':frame[0]})
    if frame[0] in (0xc3,0x4b):
     payload=frame[1:-2];assert frame[-2:]==crc16(payload)
     assert payload==expected[len(collected):len(collected)+8],(abort,setup,frames,payload,expected,len(collected))
     assert frame[0]==(0x4b if len(collected)//8%2==0 else 0xc3)
     collected.extend(payload)
     if len(collected)<len(expected):
      ack=stream.add(bytes([0xd2]),j_at+64/3)
      stream.add(token(0x69),ack.boundaries[-2]+64/3)
      driving=False;continue
     data_seen=True;break
    if abort and not injected and frame[0]==0x5a:
     setup_wave=stream.add(token(0x2d),j_at+64/3)
     setup_payload=bytes([0x80,0,0,0,0,0,2,0])
     stream.add(data_packet(setup_payload),setup_wave.boundaries[-2]+64/3)
     injected=True
    else:stream.add(token(0x69),j_at+64/3)
    driving=False
  if ins.op=='out' and ins.operands.startswith('0xb,') and driving:
   level=cpu.io.get(11,0)&6
   if not se0:
    if level==0:se0=True
    else:writes.append((cpu.t,level))
   elif level==J and j_at is None:j_at=cpu.t
  if cpu.t>200000:break
 assert data_seen,(abort,first_sop,'no completed DATA',frames,hex(cpu.pc),cpu.t)
 assert not cpu.raw_stack or len(cpu.raw_stack)<=6
 response_delays=[]
 for frame in frames:
  host=max((w for w in stream.waves if w.start<=frame['sop']),key=lambda w:w.start)
  delay=frame['sop']-host.boundaries[-2]
  assert 64/3-1e-8<=delay<=208/3+1e-8,('response window',setup,abort,first_sop,frame,delay)
  response_delays.append(delay)
 entry_delays=[]
 for when in entries:
  prior=[w for w in stream.waves if w.start<=when]
  if prior:entry_delays.append(when-max(prior,key=lambda w:w.start).start)
 result={'abort':abort,'setup':setup,'memory':memory,'first_sop':first_sop,'frames':frames,'peak_stack_bytes':cpu.peak_stack,'stack_bytes_at_DATA_release':len(cpu.raw_stack),'handler_entries':entries,'handler_entry_callers':entry_callers,'handler_entry_delays':entry_delays,'response_delays':response_delays,'host_packets':[dict(start=w.start,packet=w.packet.hex()) for w in stream.waves],'collected_hex':bytes(collected).hex(),'active_address':cpu.m[0x10c],'pending_address':cpu.m[0x113],'configuration':cpu.m[0x115],'cursor':cpu.word(4),'queued_command':cpu.r[3],'nvm_events':cpu.nvm_events,'eeprom_remaining':cpu.r[2],'eeprom_address':cpu.io.get(0x21),'eeprom_data':cpu.io.get(0x20),'cycles':cpu.t}

 return (result,cpu) if _retain_cpu else result


def check_eeprom_completion(cpu):
    """Acknowledge acceptance may precede worker progress; drain actual starts.

    Each modeled hardware completion clears EEPE and commits its latched byte.
    Firmware still supplies every EEAR/EEDR pair and advances the queue/cursor.
    """
    payload = bytes((0x11, 0x22, 0x33, 0x44))
    started = len(cpu.eeprom_events)
    assert 0 <= started <= 4
    assert cpu.r[2] == 4 - started and cpu.word(4) == 0x8020 + started
    assert bytes(cpu.r[10:10 + cpu.r[2]]) == payload[started:]
    completed = 0

    def complete_hardware_write():
        nonlocal completed
        for address, value in cpu.eeprom_events[completed:]:
            cpu.eeprom[address & 63] = value
        completed = len(cpu.eeprom_events)
        cpu.io[0x1F] = cpu.io.get(0x1F, 0) & ~2

    for iteration in range(5):
        if iteration:
            complete_hardware_write()
            cpu.pc = cpu.labels['bootloader_check_idle_timeout']
        for _ in range(5000):
            if cpu.pc == cpu.labels['bootloader_poll_begin']:
                break
            cpu.executing_pc = cpu.pc
            cpu.step()
        else:
            raise AssertionError('EEPROM worker failed to return to polling')
        assert not cpu.raw_stack and cpu.r[1] == 0
        if cpu.r[2] == 0:
            break
    complete_hardware_write()
    assert cpu.eeprom_events == list(zip(range(0x20, 0x24), payload))
    assert cpu.eeprom[0x20:0x24] == payload and cpu.word(4) == 0x8024
    assert cpu.r[2] == 0


def check_case(**options):
    """Check timing plus real selector, write-data and standard side effects."""
    result, cpu = run(**options, _retain_cpu=True)
    assert max(result['handler_entry_delays']) <= 40 + 1e-8, result
    assert max(result['response_delays']) <= 208 / 3 + 1e-8, result
    setup = options.get('setup')
    if setup is not None and not options.get('abort'):
        request = setup['request']
        if setup.get('bm', 0x40) & 0x60:
            if request in (1, 2):
                assert result['cursor'] == setup['index']
                assert result['queued_command'] == request + 1
                assert [event['command'] for event in result['nvm_events']] == [0x11]
            elif request == 3 and not setup.get('eeprom'):
                assert result['cursor'] == 0x104
                assert [(event['command'], event['address'], event['word'])
                        for event in result['nvm_events']] == [
                            (1, 0x100, 0x2211), (1, 0x102, 0x4433)]
            elif request == 3:
                check_eeprom_completion(cpu)
            elif request == 4:
                assert result['queued_command'] == 4
        elif request == 5:
            assert result['active_address'] == result['pending_address'] == 14
        elif request == 9:
            assert result['configuration'] == 1
    return result


def check_waveforms(artifact):
    """Exercise busy replies, fresh SETUP aborts and minimum-IPD ACK/IN chains."""
    configure(artifact)
    rows = []
    for abort in (False, True):
        for phase in (0, 8, 16, 24, 32, 48, 64, 96, 128):
            rows.append(check_case(abort=abort, first_sop=phase))
    for phase in (0, 24, 64, 128):
        rows.append(check_case(first_sop=phase, memory='eeprom'))
    requests = [dict(request=1, index=0x100), dict(request=1, index=0x8020),
                dict(request=2, index=0x100),
                dict(request=3, value=0x2211, index=0x4433),
                dict(request=3, value=0x2211, index=0x4433, eeprom=True),
                dict(request=4)]
    for setup in requests:
        for phase in (31 / 3, 61 / 3, 64):
            rows.append(check_case(first_sop=phase, setup=setup))
    for request in (0, 5, 8, 9, 10):
        for phase in (31 / 3, 64):
            length = 2 if request == 0 else 1 if request in (8, 10) else 0
            setup = dict(request=request, bm=0x80 if length else 0,
                         value=7 if request == 5 else 1, config=1, length=length)
            rows.append(check_case(first_sop=phase, setup=setup))
    for descriptor in (1, 2, 3):
        for phase in (31 / 3, 61 / 3, 64):
            setup = dict(request=6, bm=0x80, value=descriptor << 8, length=18)
            rows.append(check_case(first_sop=phase, setup=setup))
    for phase in (31 / 3, 61 / 3, 64):
        result = check_case(abort=True, first_sop=phase,
                            setup=dict(request=5, bm=0, value=7))
        assert result['active_address'] == result['pending_address'] == 0
        rows.append(result)
    print('PASS', artifact['mode'], len(rows), 'synchronized minimum-IPD cases;',
          'entry max', max(max(row['handler_entry_delays']) for row in rows),
          'cycles; response max', max(max(row['response_delays']) for row in rows),
          'cycles; stack max', max(row['peak_stack_bytes'] for row in rows), 'bytes')
    return rows


def check_pending_run(artifact):
    """A pending RUN waits for actual poll timeout and for EEPROM readiness."""
    configure(artifact)
    def machine(counter, pending=0, eecr=0):
        cpu = CPU(meta, {'memory': bytearray(0x300), 'registers': [0] * 32})
        cpu.flash = FlashView(cpu.flash, cpu.base)
        cpu.pc = cpu.labels['bootloader_process_pending_command']
        cpu.r[21], cpu.r[28], cpu.r[29], cpu.r[3], cpu.r[2] = 0xA0, 0, 1, 4, pending
        cpu.r[26], cpu.r[27] = counter & 255, counter >> 8
        cpu.m[0x100], cpu.m[0x10F] = 0xFF, 0x5A
        cpu.flash.memory[art['boot'] - 3] = 0
        cpu.io = PinIO(cpu, Stream())
        cpu.io.cleared_at = 0
        cpu.io[0x1F] = eecr
        return cpu
    def until(cpu, label):
        for _ in range(200000):
            if cpu.pc == cpu.labels[label]:
                return
            cpu.executing_pc = cpu.pc
            cpu.step()
        raise AssertionError((label, hex(cpu.pc), cpu.t))
    for counter in (1, 17, 65535):
        cpu = machine(counter)
        until(cpu, 'bootloader_poll_begin')
        assert cpu.r[3] == 4 and not cpu.nvm_events
        # Run the real 5 ms poll countdown from its initialization through
        # SBIW reaching zero; do not synthesize the timeout dispatcher state.
        poll_started = cpu.t
        until(cpu, 'app_jump')
        assert 79000 <= cpu.t - poll_started <= 81000
        assert cpu.word(26) == 0
        assert cpu.r[3] == 4 and cpu.io.get(10) == 0
        assert cpu.m[0x68] == cpu.m[0x6D] == 0
    for pending, eecr in ((4, 0), (0, 2)):
        cpu = machine(0, pending, eecr)
        until(cpu, 'bootloader_poll_begin')
        assert cpu.r[3] == 4 and not cpu.nvm_events
    print('PASS', artifact['mode'], 'pending RUN returns to polling, exits after timeout, and waits for EEPROM')


class Reads(PinIO):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.polls=[]
 def get(self,addr,default=0):
  if addr==0x1b:
   item=(self.cpu.t,self.cpu.executing_pc)
   if not self.polls or item!=self.polls[-1]:self.polls.append(item)
  return super().get(addr,default)
def simulate(request,value,descriptor,length,kind='flash',data=0x55,idle=0,pending=0,eecr=0,rx_staged=True,app_present=False):
 c=CPU(meta,{'memory':bytearray(0x300),'registers':[0]*32});c.flash=FlashView(c.flash,c.base)
 c.r[21]=0xa0;c.pc=c.labels['bootloader_process_pending_command'];c.r[28]=0;c.r[29]=1;c.r[4]=0;c.r[5]=0x80 if kind=='eeprom' else 1
 c.r[6]=idle&255;c.r[7]=idle>>8;c.r[14]=0;c.r[15]=5
 c.flash.memory[0x500:0x508]=bytes([data])*8;c.eeprom[:8]=bytes([data])*8
 c.m[0x100]=0xff;c.m[0x10f]=0x5a;c.m[0x112]=11;c.m[0x10d]=0x2d;c.m[0x115]=1
 if request==0xb0:c.r[4]=0;c.r[5]=0x80 if kind=='eeprom' else 5
 index=0x8020 if kind=='eeprom' else 0x100
 c.m[0x117:0x11f]=bytes([0xc0 if request==0xb0 else 0x80 if request in [0,6,8,10] else 0x40 if request in [1,2,3,4] else 0,request,value,descriptor,index&255,index>>8,length&255,length>>8])
 c.r[2]=pending;c.io=Reads(c,Stream());c.io.cleared_at=0;c.io[0x1f]=eecr
 if not rx_staged:c.m[0x112]=0
 if app_present:c.flash.memory[art['boot']-3]=0
 for _ in range(10000):
  if c.pc in (c.labels['bootloader_poll_begin'],c.labels['app_jump']) and c.steps:break
  c.executing_pc=c.pc;c.step()
 else:raise AssertionError('no-packet path did not return to polling')
 gaps=[]
 for left,right in zip(c.io.polls,c.io.polls[1:]):
  delay=5
  gaps.append(dict(gap_cycles=right[0]-left[0],pending_entry_bound=right[0]-left[0]+delay,previous_pc=hex(left[1]),next_pc=hex(right[1]),request=request,value=value,descriptor=descriptor,length=length,kind=kind,data=data,idle=idle))
 return gaps


def check_setup_stack_guard(artifact):
    """A missing frame-discard POP must fail at actual SETUP field capture."""
    raw = bytearray(artifact['body'])
    at = artifact['symbols']['usb_validate_setup_token'] + 6 - artifact['boot']
    assert raw[at:at + 2] == b'\x2f\x91'  # POP R18
    raw[at:at + 2] = b'\0\0'              # NOP leaves half a return frame.
    configure(dict(artifact, body=bytes(raw)))
    try:
        simulate(6, 0, 1, 18)
    except AssertionError as error:
        assert error.args[0][0] == 'SETUP capture retained a return frame', error
    else:
        raise AssertionError('Missing SETUP frame-discard POP was accepted')
    finally:
        configure(artifact)
    print('PASS', artifact['mode'], 'SETUP frame-discard mutation rejected by byte-stack execution')


def check_poll_gaps(artifact):
    """Bound every modeled no-packet poll interval, including EEPROM stalls."""
    configure(artifact)
    intervals = []
    for request in (0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 255):
        for length in (0, 1, 2, 8, 18, 256):
            for descriptor in ((1, 2, 3) if request == 6 else (0,)):
                intervals.extend(simulate(request, 1, descriptor, length))
    for kind in ('flash', 'eeprom'):
        for byte in range(256):
            intervals.extend(simulate(0xB0, 0, 0, 8, kind, byte))
    for request in (0, 6, 0xB0):
        intervals.extend(simulate(request, 0, 1, 18, idle=1199))
    # No staged SETUP and no pending message is a separate path: a ready
    # EEPROM queue can start a byte before the next ordinary polling window.
    # Cover queue drain, hardware busy, idle expiry and both app-valid states.
    for pending in range(5):
        for eecr in (0, 2):
            for idle in (0, 1199):
                for app_present in (False, True):
                    intervals.extend(simulate(0, 1, 0, 0, pending=pending,
                                              eecr=eecr, idle=idle,
                                              rx_staged=False,
                                              app_present=app_present))
    maximum_gap = max(row['gap_cycles'] for row in intervals)
    # SBI/SBIS observes PCIF rather than the pin. The ATtiny88 clocked PCINT
    # pipeline adds up to three cycles from a physical edge to flag visibility.
    physical_bound = maximum_gap + 5 + 3
    assert physical_bound <= 40, (artifact['mode'], maximum_gap, physical_bound)
    print('PASS', artifact['mode'], len(intervals), 'no-packet PCIF intervals;',
          'max gap', maximum_gap, '+ handler 5 + synchronizer 3 =',
          physical_bound, 'cycles from physical SOP')


def check(artifact):
    check_setup_stack_guard(artifact)
    check_pending_run(artifact)
    check_poll_gaps(artifact)
    check_waveforms(artifact)


def test():
    from host import compact_programmer27 as host
    for mode, version in (('NONE', 0x0300), ('ACTIVE_HIGH', 0x0301), ('ACTIVE_LOW', 0x0302)):
        _name, boot, _size = host.USB_PROFILES[version]
        check(checked_build(mode, boot))


if __name__ == '__main__':
    test()
