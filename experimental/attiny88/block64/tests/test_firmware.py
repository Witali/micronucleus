from __future__ import annotations
import random, subprocess, sys, pathlib, pytest
from avr_sim import *
ROOT=pathlib.Path(__file__).resolve().parent.parent
BLOCK=64

@pytest.fixture(scope='module')
def firmware():
    raw=(ROOT/'build/block64.full.bin').read_bytes()
    assert raw[:BOOT]==bytes(BOOT)
    assert len(raw)<=8192
    result=bytearray([0xff]*8192)
    result[BOOT:len(raw)]=raw[BOOT:]
    return bytes(result)

def make(fw):return CPU(image=fw)

def prepare(cpu, address, length, memtype, request=0x11, request_type=0x40):
    cpu.set_setup(request, address, length, memtype, request_type)
    cpu.run_from('block_write_setup',stop_at=['L1df8','block_reject'], execute_ret=True,count=3000)
    assert cpu.mem[MEM_STATE]==1, (cpu.mem[MEM_STATE],hex(address),length,memtype)

def usb_crc(data):
    crc=0xffff
    for b in data:
        crc^=b
        for _ in range(8):crc=((crc>>1)^0xa001) if (crc&1) else (crc>>1)
    return ((~crc)&0xffff).to_bytes(2,'little')

def out(cpu, payload, pid, corrupt=False):
    cpu.mem[0x0116]=pid
    cpu.mem[0x0117:0x0117+len(payload)]=payload
    checksum=bytearray(usb_crc(payload))
    if corrupt:checksum[0]^=0x40
    cpu.mem[0x0117+len(payload):0x0117+len(payload)+2]=checksum
    cpu.r[24]=len(payload)
    cpu.run_from('block_accept_out', count=2000, execute_ret=True)

def service(cpu):
    cpu.run_from('block_memory_service',count=2000)

@pytest.mark.parametrize('memtype', [0,1])
def test_range_validation(firmware, memtype):
    c=make(firmware)
    maxaddr=BOOT if not memtype else 64
    for addr,length in [(0,1),(0,64),(maxaddr-64,64),(maxaddr-1,1),(maxaddr,1),(maxaddr-63,64),(0,0),(0,65),(maxaddr+1,1),(0xffff,1),(0xffff,64)]:
        c.set_setup(0x10,addr,length,memtype)
        c.run_from('block_validate_range',count=160)
        expected=1<=length<=64 and 0<=addr and addr+length<=maxaddr
        assert c.flag(0)==expected,(memtype,hex(addr),length,c.flag(0),expected)

@pytest.mark.parametrize('memtype', [0,1])
def test_invalid_index(firmware, memtype):
    c=make(firmware)
    for mt in [2,3,0x100,0xffff]:
        c.set_setup(0x10,addr=0,length=8,memtype=mt)
        c.run_from('block_validate_range',count=170)
        assert not c.flag(0)

def test_flash_read_setup_direct_pointer(firmware):
    c=make(firmware)
    for addr,sz in [(0,1),(60,64),(BOOT-64,64),(BOOT-1,1)]:
        c.set_setup(0x10,addr,sz,0,0xc0)
        c.run_from('block_read_setup',stop_at=['L1f22','block_reject'],count=500,execute_ret=True)
        assert c.pc==c.labels['L1f22']
        assert (c.r[19]<<8)|c.r[18]==addr
        assert c.r[24]==sz

def test_eeprom_read_snapshot_64(firmware):
    rng=random.Random(121)
    eeprom=bytes(rng.randrange(256) for _ in range(64))
    for start,length in [(0,64),(0,1),(12,28),(63,1)]:
        c=CPU(firmware,eeprom)
        c.set_setup(0x10,start,length,1,0xc0)
        c.run_from('block_read_setup',stop_at=['L1f22','block_reject'],count=1700,execute_ret=True)
        assert c.pc==c.labels['L1f22']
        assert (c.r[19]<<8)|c.r[18]==0x8140
        assert c.r[24]==length
        assert c.mem[0x0140:0x0140+length]==eeprom[start:start+length]

def test_write_flash_partial_and_repeat_pid(firmware):
    rng=random.Random(678)
    image=bytearray(firmware)
    initial=bytes(rng.randrange(256) for _ in range(64))
    image[0x0100:0x0140]=initial
    c=make(bytes(image))
    data=bytes(range(1,37))
    prepare(c,0x100+7,len(data),0)
    assert c.mem[MEM_INDEX]==7
    assert c.mem[MEM_BUFFER:MEM_BUFFER+64]==initial
    chunks=[data[i:i+8] for i in range(0,len(data),8)]
    for idx,chunk in enumerate(chunks):
        pid=(0x4b if idx%2==0 else 0xc3)
        out(c,chunk,pid)
        # Repeated packet with identical DATA PID must not advance pointer.
        if idx==0:
            saved=(c.mem[MEM_INDEX],c.mem[MEM_REMAIN])
            out(c,chunk,pid)
            assert (c.mem[MEM_INDEX],c.mem[MEM_REMAIN])==saved
    assert c.mem[MEM_STATE]==3
    assert c.mem[MEM_REMAIN]==0
    service(c)
    assert c.flash[0x0100:0x0140]==initial[:7]+data+initial[7+len(data):]
    assert c.mem[MEM_STATUS]==0 and c.mem[MEM_STATE]==4
    assert c.mem[0x0100]==0 # ZLP status ready
    assert [x[0] for x in c.spm_oplog].count('load')==32
    assert [x for x in c.spm_oplog if x[0]=='write']==[('write',0x0100)]

def test_flash_64_byte_page_and_reset_protection(firmware):
    c=make(firmware)
    prepare(c,0,64,0)
    for i in range(8): out(c,bytes(range(i*8,i*8+8)),0x4b if i%2==0 else 0xc3)
    assert c.mem[MEM_STATE]==3
    service(c)
    expected=(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
    assert c.flash[:2]==expected
    assert c.flash[2:64]==bytes(range(2,64))
    assert c.spm_oplog[0]==('erase',0)

def test_write_eeprom_64_bytes_one_usb_transfer(firmware):
    eep=bytes([0xFF]*64);c=CPU(firmware,eep)
    prepare(c,0,64,1)
    for i in range(8):
        out(c,bytes([(i*8+j)*3&255 for j in range(8)]),0x4b if i%2==0 else 0xc3)
    assert c.mem[MEM_STATE]==2
    for step in range(65): service(c)
    assert c.mem[MEM_STATUS]==0 and c.mem[MEM_STATE]==4
    assert c.eeprom==bytes((i*3)&255 for i in range(64))
    assert len(c.eeprom_oplog)==64
    assert c.mem[0x0100]==0

def test_eeprom_partial_from_last_address(firmware):
    c=make(firmware)
    prepare(c,60,4,1)
    out(c,b'abcd',0x4b)
    for _ in range(5):service(c)
    assert bytes(c.eeprom[60:64])==b'abcd'

def test_flash_write_cross_page_rejected(firmware):
    c=make(firmware)
    for adr,count in [(0x3f,2),(0x1e,60),(BOOT-30,31)]:
        c.set_setup(0x11,adr,count,0,0x40)
        c.run_from('block_write_setup',stop_at=['L1df8','block_reject'],count=300,execute_ret=True)
        assert c.pc==c.labels['block_reject']

def test_bootloader_region_not_writable(firmware):
    c=make(firmware)
    for addr in [BOOT,BOOT+1,8191,65535]:
        c.set_setup(0x11,addr,1,0,0x40)
        c.run_from('block_write_setup',stop_at=['L1df8','block_reject'],execute_ret=True,count=400)
        assert c.pc==c.labels['block_reject']

def test_usb_bit_code_crc_binary_identical(firmware):
    source=ROOT/'reference/previous_bulk8_1344.S'
    base_obj=ROOT/'build/previous_bulk8.o'
    base_bin=ROOT/'build/previous_bulk8.full.bin'
    subprocess.run(['clang','-target','avr','-mmcu=attiny88','-c','-x','assembler-with-cpp',str(source),'-o',str(base_obj)],check=True)
    subprocess.run(['llvm-objcopy','-O','binary','-j','.text',str(base_obj),str(base_bin)],check=True)
    bs=syms(base_obj); ns=syms()
    old=base_bin.read_bytes();new=(ROOT/'build/block64.full.bin').read_bytes()
    assert old[bs['usb_crc16_append']:bs['USB_handler']]==new[ns['usb_crc16_append']:ns['USB_handler']]
    assert old[bs['USB_handler']:bs['usb_program_page']]==new[ns['USB_handler']:ns['main']]

def test_correct_version_and_layout(firmware):
    assert firmware[BOOT+8]==0xe1
    assert firmware[BOOT+0x28:BOOT+0x2a]==b'\x00\x03'
    assert firmware[BOOT+2:BOOT+4]==bytes([(BOOT-4)>>8,(BOOT-4)&255])
    assert firmware[BOOT:BOOT+2]!=b'\xff\xff'
    assert len(firmware)==8192

@pytest.mark.parametrize('memory_source', ['ram','flash'])
def test_eight_usb_tx_data_packets_for_64_byte_read(firmware,memory_source):
    c=make(firmware)
    original=bytes((i*17+13)&255 for i in range(64))
    if memory_source=='flash':
        start=0x200
        c.flash[start:start+64]=original
        pointer=start
    else:
        c.mem[MEM_BUFFER:MEM_BUFFER+64]=original
        pointer=0x8140
    c.mem[0x0100]=64  # 64-byte reply remaining
    c.mem[0x0101]=0xc3
    c.mem[0x010f]=0x5a
    c.mem[0x0110]=pointer&255
    c.mem[0x0111]=pointer>>8
    produced=b''
    for i in range(8):
        c.mem[0x010f]=0x5a  # USB handler sent previous DATA packet, now idle
        c.run_from('L1dfc',stop_at=['L1e64'],count=6000,execute_ret=True)
        assert c.mem[0x010f]==12,('TX packet length',i)
        produced+=bytes(c.mem[0x0102:0x010a])
        assert c.mem[0x0100]==64-(i+1)*8
    assert produced==original
    assert c.mem[0x0101]==0xc3 # 8 toggles restore DATA0 for next packet


def test_usb_standard_scratch_reply_does_not_read_flash(firmware):
    c=make(firmware)
    c.mem[0x0102:0x0104]=b'\x5a\xa5'
    c.mem[0x0100]=2
    c.mem[0x0101]=0xc3
    c.mem[0x010f]=0x5a
    c.mem[0x0110]=0x0a
    c.mem[0x0111]=0x81
    c.run_from('L1dfc',stop_at=['L1e64'],count=3000,execute_ret=True)
    assert c.mem[0x0102:0x0104]==b'\x5a\xa5'
    assert c.mem[0x010f]==6


def test_randomized_flash_page_rmw(firmware):
    rng=random.Random(6701)
    for _ in range(70):
        page=rng.randrange(0,BOOT//64)
        offset=rng.randrange(0,64)
        count=rng.randrange(1,65-offset)
        base=page*64
        original=bytes(rng.randrange(256) for _ in range(64))
        incoming=bytes(rng.randrange(256) for _ in range(count))
        image=bytearray(firmware)
        image[base:base+64]=original
        c=make(bytes(image))
        prepare(c,base+offset,count,0)
        for packet_i,packet_start in enumerate(range(0,count,8)):
            chunk=incoming[packet_start:packet_start+8]
            out(c,chunk,0x4b if packet_i%2==0 else 0xc3)
        assert c.mem[MEM_STATE]==3
        service(c)
        expected=bytearray(original)
        expected[offset:offset+count]=incoming
        if page==0:
            expected[:2]=(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
        assert bytes(c.flash[base:base+64])==bytes(expected), (page,offset,count)


def test_randomized_eeprom_writes(firmware):
    rng=random.Random(861)
    for _ in range(30):
        addr=rng.randrange(0,64)
        length=rng.randrange(1,65-addr)
        original=bytes(rng.randrange(256) for _ in range(64))
        data=bytes(rng.randrange(256) for _ in range(length))
        c=CPU(firmware,original)
        prepare(c,addr,length,1)
        for packet_i,packet_start in enumerate(range(0,length,8)):
            out(c,data[packet_start:packet_start+8],0x4b if packet_i%2==0 else 0xc3)
        for _ in range(length+1):service(c)
        assert c.eeprom==original[:addr]+data+original[addr+length:]
        assert c.mem[MEM_STATUS]==0


def test_bad_usb_data_crc_is_not_programmed(firmware):
    c=make(firmware)
    prepare(c,0x100,8,0)
    before=bytes(c.mem[MEM_BUFFER:MEM_BUFFER+64])
    out(c,bytes(range(8)),0x4b,corrupt=True)
    assert c.mem[MEM_REMAIN]==8
    assert c.mem[MEM_INDEX]==0
    assert c.mem[MEM_BUFFER:MEM_BUFFER+64]==before
    assert c.mem[MEM_STATE]==1
    # A subsequent correctly checksummed retry is accepted.
    out(c,bytes(range(8)),0x4b)
    assert c.mem[MEM_REMAIN]==0
    assert c.mem[MEM_STATE]==3


def test_static_instruction_decoder_and_branch_boundaries(firmware):
    c=make(firmware)
    sym=c.labels
    start=sym['startup']
    end=len((ROOT/'build/block64.full.bin').read_bytes())
    instructions=[]
    pc=start
    while pc<end:
        ins=c.decode(pc)
        assert not ins.unknown,(hex(pc),ins)
        instructions.append(ins)
        pc+=ins.size
    assert pc==end
    valid_targets={ins.address for ins in instructions}
    for ins in instructions:
        if ins.target is None:continue
        if ins.target>=start:
            assert ins.target in valid_targets,(hex(ins.address),hex(ins.target))
        else:
            # Only intentional exception: final RJMP to the four-byte
            # application postscript, outside the bootloader.
            assert ins.address==sym['app_jump'] and ins.target==BOOT-4,(hex(ins.address),hex(ins.target))
    assert len(instructions)>650


def test_status_report_and_run_request(firmware):
    c=make(firmware)
    c.mem[MEM_STATUS]=0
    c.r[25]=0x12
    c.run_from('block_status',stop_at=['L1f34'],count=100)
    assert c.r[24]==1 and c.mem[0x0102]==0
    c.mem[MEM_STATE]=4
    c.run_from('block_run',stop_at=['L1de2'],count=100)
    assert c.mem[MEM_STATE]==5 and c.r[24]==0
