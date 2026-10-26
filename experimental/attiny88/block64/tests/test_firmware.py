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
    assert cpu.mem[MEM_STATE]==ST_RECEIVE, (cpu.mem[MEM_STATE],hex(address),length,memtype)

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

def prepare_status_zlp(cpu):
    """Execute the REAL inline EP0 status-queue path in the compact build.

    Earlier tests called the removed block_note_status_prepared subroutine
    directly; test the actual call site instead of testing a dead helper.
    """
    cpu.r[28],cpu.r[29]=0,1
    cpu.r[23]=4  # zero USB payload + SYNC/PID/CRC framing bytes
    cpu.run_from('L1e60',stop_at=['L1e64'],count=100)

def usb_status_and_spm(cpu,operation):
    """Simulate hardware sending USB status, followed by 5ms quiet poll.

    The behavioral test deliberately checks NO SPM occurs before both phases.
    """
    assert cpu.mem[MEM_STATE]==ST_FLASH_WAIT_PREP
    previous=list(cpu.spm_oplog)
    service(cpu)
    assert cpu.spm_oplog==previous
    # ZLP has now been prepared by the regular TX packetizer.
    cpu.mem[0x0100]=0xff
    cpu.mem[0x010f]=4
    prepare_status_zlp(cpu)
    assert cpu.mem[MEM_STATE]==ST_SPM_WAIT_SENT
    service(cpu)
    assert cpu.spm_oplog==previous
    cpu.run_from('block_spm_after_quiet',execute_ret=True,count=500)
    assert cpu.spm_oplog==previous  # Not yet actually sent.
    cpu.mem[0x010f]=0x5a  # USB_handler has emitted status DATA1 ZLP.
    cpu.run_from('block_spm_after_quiet',execute_ret=True,count=1200)
    assert cpu.mem[MEM_STATE]==ST_DONE
    assert cpu.mem[MEM_STATUS]==0
    assert cpu.mem[0x0100]==0xff  # Must not schedule another status transfer.
    assert cpu.spm_oplog!=previous
    assert cpu.spm_oplog[-1][0]==operation

def erase_flash(cpu,address):
    cpu.set_setup(0x14,address,0,0,0x40)
    cpu.run_from('block_erase_setup',stop_at=['L1df8','block_reject'],execute_ret=True,count=500)
    assert cpu.mem[MEM_STATE]==ST_FLASH_WAIT_PREP
    assert cpu.mem[MEM_PROGRESS]==1
    usb_status_and_spm(cpu,'erase')

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

def test_write_flash_full_page_no_rmw_and_repeat_pid(firmware):
    rng=random.Random(678)
    image=bytearray(firmware)
    initial=bytes(rng.randrange(256) for _ in range(64))
    image[0x100:0x140]=initial
    c=make(bytes(image))
    erase_flash(c,0x100)
    assert c.flash[0x100:0x140]==bytes([0xff]*64)
    prepare(c,0x100,64,0)
    assert c.mem[MEM_INDEX]==0
    assert c.mem[MEM_BUFFER:MEM_BUFFER+64]==bytes(64) # no preload of old Flash
    assert not c.lpm_oplog # Flash setup did not read the page
    data=bytes((i*3+1)&255 for i in range(64))
    for idx in range(8):
        payload=data[idx*8:idx*8+8]; pid=0x4b if idx%2==0 else 0xc3
        out(c,payload,pid)
        if idx==0:
            saved=(c.mem[MEM_INDEX],c.mem[MEM_REMAIN])
            out(c,payload,pid)
            assert (c.mem[MEM_INDEX],c.mem[MEM_REMAIN])==saved
    assert c.mem[MEM_STATE]==ST_FLASH_WAIT_PREP and c.mem[MEM_REMAIN]==0
    assert c.flash[0x100:0x140]==bytes([0xff]*64)  # No SPM in DATA stage.
    usb_status_and_spm(c,'write')
    assert c.flash[0x100:0x140]==data
    assert len([x for x in c.spm_oplog if x[0]=='erase'])==1
    assert len([x for x in c.spm_oplog if x[0]=='write'])==1
    assert len([x for x in c.spm_oplog if x[0]=='load'])==32
    assert not c.lpm_oplog # No MCU RMW anywhere in the Flash write sequence


def test_flash_64_byte_page_and_reset_protection(firmware):
    c=make(firmware)
    erase_flash(c,0)
    prepare(c,0,64,0)
    for i in range(8):out(c,bytes(range(i*8,i*8+8)),0x4b if i%2==0 else 0xc3)
    usb_status_and_spm(c,'write')
    expected=(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
    assert c.flash[:2]==expected
    assert c.flash[2:64]==bytes(range(2,64))
    assert [x[0] for x in c.spm_oplog].count('erase')==1


def test_write_eeprom_64_bytes_one_usb_transfer(firmware):
    eep=bytes([0xFF]*64);c=CPU(firmware,eep)
    prepare(c,0,64,1)
    for i in range(8):
        out(c,bytes([(i*8+j)*3&255 for j in range(8)]),0x4b if i%2==0 else 0xc3)
    assert c.mem[MEM_STATE]==ST_WRITE_EEPROM
    for step in range(65): service(c)
    assert c.mem[MEM_STATUS]==0 and c.mem[MEM_STATE]==ST_DONE
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
    assert firmware[BOOT+2:BOOT+8]==bytes([((BOOT-4)>>8),((BOOT-4)&255),64,64,0x33,0x03])
    assert firmware[BOOT+0x26:BOOT+0x28]==b'\x03\x03'
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


def test_randomized_flash_complete_page_write_without_rmw(firmware):
    rng=random.Random(6701)
    for _ in range(90):
        page=rng.randrange(0,BOOT//64); base=page*64
        initial=bytes(rng.randrange(256) for _ in range(64))
        incoming=bytes(rng.randrange(256) for _ in range(64))
        image=bytearray(firmware);image[base:base+64]=initial
        c=make(bytes(image))
        erase_flash(c,base)
        assert c.flash[base:base+64]==b'\xff'*64
        prepare(c,base,64,0)
        for packet_i in range(8):
            chunk=incoming[packet_i*8:(packet_i+1)*8]
            out(c,chunk,0x4b if packet_i%2==0 else 0xc3)
        usb_status_and_spm(c,'write')
        expected=bytearray(incoming)
        if page==0: expected[:2]=(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
        assert bytes(c.flash[base:base+64])==bytes(expected)
        assert len([x for x in c.spm_oplog if x[0]=='erase'])==1
        assert len([x for x in c.spm_oplog if x[0]=='write'])==1



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
    prepare(c,0x100,64,0)
    before=bytes(c.mem[MEM_BUFFER:MEM_BUFFER+64])
    out(c,bytes(range(8)),0x4b,corrupt=True)
    assert c.mem[MEM_REMAIN]==64 and c.mem[MEM_INDEX]==0
    assert c.mem[MEM_BUFFER:MEM_BUFFER+64]==before
    assert c.mem[MEM_STATE]==ST_RECEIVE
    for i in range(8):out(c,bytes(range(i*8,i*8+8)),0x4b if i%2==0 else 0xc3)
    assert c.mem[MEM_REMAIN]==0 and c.mem[MEM_STATE]==ST_FLASH_WAIT_PREP
    assert not c.spm_oplog  # No data written until USB status and quiet interval.



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
    c.run_from('startup',stop_at=['main'],count=500)
    c.mem[MEM_STATUS]=0
    c.mem[MEM_STATE]=ST_DONE
    c.set_setup(0x12,length=8,request_type=0xc0)
    c.run_from('block_vendor_dispatch',stop_at=['L1de2'],count=200)
    assert c.r[24]==8 and ((c.r[19]<<8)|c.r[18])==0x8138
    c.run_from('L1de2',stop_at=['L1dfc'],count=100)
    assert c.mem[0x0100]==8  # Single supported GET_STATUS frame
    c.mem[0x010f]=0x5a
    c.mem[0x0101]=0xc3
    c.run_from('L1dfc',stop_at=['L1e64'],count=900,execute_ret=True)
    assert c.mem[0x0102]==0
    c.run_from('block_run',stop_at=['L1de2'],count=100)
    assert c.mem[MEM_STATE]==ST_RUN and c.r[24]==0


@pytest.mark.parametrize('result,state',[(0,0),(0,1),(1,5),(1,6),(2,2),(3,2)])
@pytest.mark.parametrize('requested', [1,2,7,8,16,255])
def test_unified_get_status_usb_payload_and_bounds(firmware,result,state,requested):
    c=make(firmware)
    # Ensure no stale SRAM bytes survive an arbitrary power-on state.
    c.mem[0x0100:0x0140]=bytes(((i*13+3)%255+1) for i in range(0x40))
    c.run_from('startup',stop_at=['main'],count=500)
    c.mem[MEM_STATUS]=result
    c.mem[MEM_STATE]=state
    c.set_setup(0x12,length=requested,request_type=0xc0)
    c.run_from('block_vendor_dispatch',stop_at=['L1de2'],count=200)
    assert c.r[24]==8 and (c.r[19]<<8|c.r[18])==0x8138
    c.run_from('L1de2',stop_at=['L1dfc'],count=100)
    count=min(8,requested)  # EP0 clips malformed host wLength; supported host requests eight.
    assert c.mem[0x0100]==count
    c.mem[0x010f]=0x5a
    c.mem[0x0101]=0xc3
    c.run_from('L1dfc',stop_at=['L1e64'],count=900,execute_ret=True)
    expected=bytes([result,state,(BOOT-4)>>8,(BOOT-4)&255,64,64,0x33,0x03])
    assert c.mem[0x0102:0x0102+count]==expected[:count]
    # The packetizer itself advances FLASH_WAIT_PREP -> SPM_WAIT_SENT after
    # scheduling the outgoing status-stage packet; it must not change the
    # already snapshotted GET_STATUS payload.
    new_state=ST_SPM_WAIT_SENT if state==ST_FLASH_WAIT_PREP else state
    assert c.mem[MEM_STATUS]==result and c.mem[MEM_STATE]==new_state
    assert c.mem[0x013a:0x0140]==expected[2:]


def test_removed_legacy_info_request_is_rejected(firmware):
    c=make(firmware)
    c.r[28],c.r[29]=0,1
    c.set_setup(0x20,length=8,request_type=0xc0)
    c.run_from('block_vendor_dispatch',stop_at=['L1df8'],count=250)
    assert c.mem[0x0100]==0xff
    assert c.mem[MEM_STATUS]==2


def test_flash_rejects_partial_and_unaligned_without_touching_flash(firmware):
    for addr,length in [(0,1),(0,63),(1,64),(63,1),(65,64),(BOOT-32,64)]:
        c=make(firmware)
        c.set_setup(0x11,addr,length,0,0x40)
        c.run_from('block_write_setup',stop_at=['L1df8','block_reject'],execute_ret=True,count=500)
        assert c.mem[MEM_STATE]!=ST_RECEIVE,(addr,length)
        assert not c.spm_oplog


def test_flash_erase_command_range_and_zero_data(firmware):
    for addr,length,memtype,valid in [(0,0,0,True),(BOOT-64,0,0,True),
                                      (0x100,0,0,True),(1,0,0,False),
                                      (BOOT,0,0,False),(0,1,0,False),
                                      (0,0,1,False),(0x100,0,256,False)]:
        c=make(firmware)
        c.set_setup(0x14,addr,length,memtype,0x40)
        c.run_from('block_erase_setup',stop_at=['L1df8','block_reject'],execute_ret=True,count=500)
        assert (c.mem[MEM_STATE]==ST_FLASH_WAIT_PREP)==valid,(addr,length,memtype,c.mem[MEM_STATE])
        assert not c.spm_oplog


def test_spm_begins_only_after_status_sent_and_quiet_interval(firmware):
    c=make(firmware)
    c.set_setup(0x14,0x100,0,0,0x40)
    c.run_from('block_erase_setup',stop_at=['L1df8'],execute_ret=True,count=500)
    old=bytes(c.flash[0x100:0x140]);assert not c.spm_oplog
    # status queued but NOT transmitted
    c.mem[0x010f]=4
    prepare_status_zlp(c)
    assert c.mem[MEM_STATE]==ST_SPM_WAIT_SENT
    for _ in range(4):
        service(c)
        c.run_from('block_spm_after_quiet',execute_ret=True,count=300)
        assert not c.spm_oplog
    c.mem[0x010f]=0x5a
    c.run_from('block_spm_after_quiet',execute_ret=True,count=300)
    assert c.spm_oplog==[('erase',0x100)]
    assert c.flash[0x100:0x140]==b'\xff'*64


def test_rejected_request_does_not_cancel_pending_erase(firmware):
    c=make(firmware)
    c.set_setup(0x14,0x100,0,0,0x40)
    c.run_from('block_erase_setup',stop_at=['L1df8'],execute_ret=True,count=500)
    prepare_status_zlp(c)
    assert c.mem[MEM_STATE]==ST_SPM_WAIT_SENT
    c.run_from('block_reject',stop_at=['L1df8'],count=300)
    assert c.mem[MEM_STATE]==ST_SPM_WAIT_SENT
    assert c.mem[MEM_STATUS]==1


def test_all_101_page_erase_addresses_and_loader_boundary(firmware):
    for addr in range(0,BOOT,64):
        c=make(firmware)
        c.set_setup(0x14,addr,0,0,0x40)
        c.run_from('block_erase_setup',stop_at=['L1df8','block_reject'],count=350,execute_ret=True)
        assert c.mem[MEM_STATE]==ST_FLASH_WAIT_PREP,hex(addr)
        assert not c.spm_oplog
    for addr in [BOOT,BOOT+64,0x1fc0,0xffff]:
        c=make(firmware)
        c.set_setup(0x14,addr,0,0,0x40)
        c.run_from('block_erase_setup',stop_at=['L1df8','block_reject'],count=350,execute_ret=True)
        assert c.mem[MEM_STATE]!=ST_FLASH_WAIT_PREP,hex(addr)
        assert not c.spm_oplog


def test_cold_start_initializes_all_block64_state(firmware):
    """Real AVR SRAM is undefined after POR; the state machine cannot rely on zeros."""
    import random
    rng=random.Random(0x88)
    c=make(firmware)
    for addr in range(0x0100,0x0140):
        c.mem[addr]=rng.randrange(1,256)
    c.run_from('startup', stop_at=['main'], count=400)
    assert c.mem[0x0100:0x013a] == bytes(0x3a)
    assert c.mem[0x013a:0x0140] == bytes([((BOOT-4)>>8),((BOOT-4)&255),64,64,0x33,0x03])
    assert c.mem[MEM_STATE] == ST_IDLE
    assert c.mem[MEM_STATUS] == 0
    assert c.mem[MEM_EXPECT_PID] == 0


def test_page_zero_uses_app_supplied_interrupt_vectors(firmware):
    """RESET patched, all other vector bytes and page-zero contents untouched."""
    c=make(firmware)
    erase_flash(c,0)
    prepare(c,0,64,0)
    # Different jump destinations for all 19 interrupt vectors, no fixed ABI.
    page=bytearray((i*37+11)&0xff for i in range(64))
    for n in range(1,20):
        # Valid one-word RJMP encodings, all distinct.
        v=0xc000 | ((n*13+5)&0xfff)
        page[2*n:2*n+2]=v.to_bytes(2,'little')
    for i in range(8):
        out(c,bytes(page[i*8:(i+1)*8]),0x4b if i%2==0 else 0xc3)
    usb_status_and_spm(c,'write')
    reset=(0xc000|(((BOOT//2)-1)&0xfff)).to_bytes(2,'little')
    assert c.flash[:2]==reset
    assert c.flash[2:64]==page[2:]


@pytest.mark.parametrize('descriptor,offset',[('device',0x1a),('configuration',0x08)])
def test_usb_standard_descriptors_still_accessible_after_metadata_repack(firmware,descriptor,offset):
    """Two unneeded info/signature bytes were removed before the descriptors.

    Standard USB descriptor pointers must follow this two-byte relocation.
    """
    c=make(firmware)
    kind=1 if descriptor=='device' else 2
    c.set_setup(6,addr=kind<<8,length=18,memtype=0,request_type=0x80)
    c.run_from('old_vendor_dispatch',stop_at=['L1de2'],count=180)
    address=(c.r[19]<<8)|c.r[18]
    assert address==BOOT+offset
    assert c.r[24]==18
    raw=bytes(c.flash[address:address+18])
    assert raw[:2]==(bytes([18,kind]) if kind==1 else bytes([9,kind]))
    if kind==1:
        assert raw[12:14]==b'\x03\x03'  # bcdDevice=3.3
        assert raw[8:12]==b'\xd0\x16\x53\x07'  # VID:PID 16D0:0753
    else:
        assert raw[2:4]==b'\x12\x00'  # total length 18


def test_usb_standard_get_status_remains_distinct_from_vendor_get_status(firmware):
    c=make(firmware)
    c.set_setup(0x00,length=2,request_type=0x80)
    c.run_from('old_vendor_dispatch',stop_at=['L1de2'],count=150)
    assert c.r[24]==2  # USB standard GET_STATUS, not Block64 status
    assert (c.r[19]<<8)|c.r[18]==0x810a
    assert c.mem[0x0102:0x0104]==b'\x00\x00'
