// Functional execution of actual loader opcodes. The explicit NVM shim is
// not an electrical USB, power-failure or EEPROM-endurance model.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const music=process.env.MICROMUSIC_ROOT||'C:/Work/MicroMusic';
const {AVRCore}=await import(pathToFileURL(path.join(music,'web-player/lib/avr-reference.js')).href);
const names={setup:['usb_control_process_received_packet','L1d9c'],
  tx:['usb_tx_prepare_pending_reply','L1dfc'],idle:['bootloader_check_idle_timeout','L1e64'],
  command:['bootloader_process_pending_command','L1d5e']};

function crc16(data) {
  let crc=0xffff;
  for(const value of data) {
    crc^=value;
    for(let bit=0;bit<8;bit++)crc=(crc>>1)^((crc&1)?0xa001:0);
  }
  return crc^0xffff;
}

class LoaderCPU extends AVRCore {
  constructor(meta,body) {
    const flash=new Uint8Array(8192).fill(255);flash.set(body,meta.image_address);
    super(flash,null,{target:'attiny88',cpuHz:16000000,fastIdle:false,fastBlocks:false});
    this.boot=meta.image_address;this.appBytes=meta.application_bytes;
    this.entries=Object.fromEntries(Object.entries(names).map(([key,choices])=> {
      const found=choices.map(name=>meta.symbols[name]).find(Number.isInteger);
      assert.ok(Number.isInteger(found),`Missing entry ${key}`);return [key,found];
    }));
    this.eeprom=new Uint8Array(64).fill(255);
    this.buffer=new Uint8Array(64).fill(255);this.loaded=new Set();this.operations=[];
    this.nvm=0;this.until=0;this.eempeAt=-100;
    this.data[0x5d]=255;this.data[0x5e]=2; // Tiny88 SRAM stack top.
  }
  writeIO(io,value) {
    if(io===0x48) {
      // PCICR sources are polled, never dispatched as interrupts. The
      // reference CPU rejects source enables even with global IRQs off.
      assert.equal(this.i,0);this.data[0x68]=value;return 0;
    }
    if(io===0x37) {
      this.nvm=value;this.until=this.cyc+4;this.data[0x57]=value;return 0;
    }
    if(io===0x1f) {
      if((value&4)&&!(value&2))this.eempeAt=this.cyc;
      if(value&1)this.data[0x40]=this.eeprom[this.data[0x41]];
      if((value&6)===6) {
        assert.ok(this.cyc-this.eempeAt<=4,'EEPROM master-enable window expired');
        assert.ok(this.data[0x41]<64);this.eeprom[this.data[0x41]]=this.data[0x40];
      }
      this.data[0x3f]=value&~3;return 0;
    }
    return super.writeIO(io,value);
  }
  step() {
    const at=this.pc*2,w=this.rom[at]|this.rom[at+1]<<8;
    if(w===0x95e8) {
      assert.ok(this.cyc<this.until,'SPM enable window expired');
      const z=this.r[30]|this.r[31]<<8,base=z&~63,cmd=this.nvm;
      assert.equal(this.i,0);
      if(cmd===17){this.buffer.fill(255);this.loaded.clear();}
      else if(cmd===1) {
        assert.equal(z&1,0);assert.ok(!this.loaded.has(z&63));
        this.loaded.add(z&63);this.buffer[z&63]=this.r[0];this.buffer[(z&63)+1]=this.r[1];
      } else {
        assert.ok(base<this.boot,'Loader tried to erase/write its own Flash');
        assert.ok(at<base||at>=base+64,'Loader touched executing code');
        assert.equal(z,base,'SPM page address is not aligned');
        if(cmd===3)this.rom.fill(255,base,base+64);
        else {
          assert.equal(cmd,5);assert.equal(this.loaded.size,32);
          assert.ok(this.rom.slice(base,base+64).every(value=>value===255));
          this.rom.set(this.buffer,base);this.buffer.fill(255);this.loaded.clear();
        }
        this.operations.push([cmd,base]);this.clock(72000);
        for(let word=base/2;word<(base+64)/2;word++)this.decode(word);
      }
      // Classic AVR SPM does not change SREG. This is required by the
      // erase-loop flag optimization and checked through every erased page.
      this.nvm=0;this.data[0x57]=0;this.pc++;this.clock(4);return;
    }
    if((w&0xff00)===0x9800) {
      const io=(w>>3)&31;this.writeIO(io,this.io[io]&~(1<<(w&7)));
      this.pc++;this.clock(2);return;
    }
    if([0x9900,0x9b00].includes(w&0xff00)) {
      const bit=(this.io[(w>>3)&31]>>(w&7))&1;this.pc++;let cycles=1;
      if(bit===Number((w&0xff00)===0x9b00)) {
        const next=this.rom[this.pc*2]|this.rom[this.pc*2+1]<<8;
        const size=((next&0xfe0f)===0x9000||(next&0xfe0f)===0x9200)?2:1;
        this.pc+=size;cycles+=size;
      }
      this.clock(cycles);return;
    }
    super.step();
  }
  untilPC(address) {
    for(let step=0;step<10000;step++) {
      if(this.pc*2===address)return;
      this.step();
    }
    throw new Error(`No checkpoint at 0x${address.toString(16)}`);
  }
  request(type,request,value=0,index=0,length=1) {
    this.data[0x112]=11;this.data[0x10d]=0x2d;
    this.data.set([type,request,value&255,value>>8,index&255,index>>8,length&255,length>>8],0x117);
    this.pc=this.entries.setup/2;
    const payload=[];
    for(let block=0;block<33;block++) {
      this.untilPC(this.entries.idle);
      const bytes=this.data[0x10f]-4;
      assert.ok(bytes>=0&&bytes<=8);
      const packet=this.data.slice(0x102,0x102+bytes),crc=crc16(packet);
      assert.equal(this.data[0x102+bytes]|this.data[0x103+bytes]<<8,crc,'USB CRC mismatch');
      payload.push(...packet);
      if(this.data[0x100]===255)return payload;
      this.data[0x10f]=0x5a;this.pc=this.entries.tx/2;
    }
    throw new Error(`Control reply did not finish: type=${type} request=${request} length=${length} remaining=${this.data[0x100]} tx=${this.data[0x10f]} pc=${this.pc*2}`);
  }
  command(value) {
    this.r[3]=value;this.pc=this.entries.command/2;
    this.untilPC(this.entries.setup);assert.equal(this.r[1],0);
  }
}

for(const file of process.argv.slice(2)) {
  const meta=JSON.parse(fs.readFileSync(file));
  const body=fs.readFileSync(path.join(path.dirname(file),meta.body_file));
  const reset=new LoaderCPU(meta,body);
  reset.data.fill(0x55,0x100);reset.r[1]=0xa5;
  reset.data[0x5d]=0x10;reset.data[0x5e]=1;reset.pc=reset.boot/2;
  reset.untilPC(meta.symbols.main);
  assert.ok(reset.data.slice(0x100,0x12c).every(value=>value===0));
  assert.equal(reset.data[0x12c],0x55);assert.equal(reset.r[1],0);
  assert.equal(reset.data[0x5d]|reset.data[0x5e]<<8,0x2ff);
  // Execute the final disconnect-delay iteration instead of millions of
  // identical countdown steps. Its zero pair must initialize R4:R5 even
  // when command/pointer registers contain arbitrary values at entry.
  for(const pattern of [0,255,0x55,0xaa]) {
    const startup=new LoaderCPU(meta,body);
    startup.r.fill(pattern);startup.r[1]=0;
    startup.r[24]=1;startup.r[25]=0;startup.r[18]=1;
    startup.pc=meta.symbols.usb_disconnect_delay_inner/2;
    startup.untilPC(meta.symbols.bootloader_poll_begin);
    for(const reg of [3,4,5,7])assert.equal(startup.r[reg],0,`Startup R${reg}`);
    assert.equal(startup.data[0x10f],0x5a);assert.equal(startup.data[0x100],255);
    assert.equal(startup.data[0x68],4);assert.equal(startup.data[0x6d],4);
    assert.equal(startup.data[0x2a]&2,0,'USB disconnect output was not released');
  }
  const cpu=new LoaderCPU(meta,body);
  // Every standard request byte, directions and short/long reply limits.
  const baselineBody=fs.readFileSync(path.join(root,'../variants/strict_usb_verified/BOOTLOADER_BODY_1AC0_VERIFIED.bin'));
  const old=new LoaderCPU({image_address:0x1ac0,application_bytes:6844,symbols:meta.baseline_symbols},baselineBody);
  for(const type of [0,0x80])for(let request=0;request<256;request++)for(const length of [0,1,2,8,18,256]) {
    assert.deepEqual(cpu.request(type,request,0,0,length),old.request(type,request,0,0,length));
  }
  for(const descriptor of [1,2])for(const length of [1,8,9,18,255]) {
    assert.deepEqual(cpu.request(0x80,6,descriptor<<8,0,length),old.request(0x80,6,descriptor<<8,0,length));
  }
  for(let address=0;address<64;address++) {
    assert.deepEqual(cpu.request(0xc0,0xc0,address,(address*37+19)&255),[0]);
    assert.deepEqual(cpu.request(0xc0,0xa0,address),[(address*37+19)&255]);
    assert.deepEqual(cpu.request(0xc0,0xc0,address,255),[0]);
  }
  assert.ok(cpu.eeprom.every(value=>value===255));
  for(const address of [64,255,256,65535]) {
    assert.deepEqual(cpu.request(0xc0,0xc0,address,0x55),[2]);
    assert.deepEqual(cpu.request(0xc0,0xa0,address),[]);
  }
  assert.deepEqual(cpu.request(0xc0,0xc0,0,0x100),[2]);
  cpu.data[0x3f]|=2;
  assert.deepEqual(cpu.request(0xc0,0xf0),[1]);
  assert.deepEqual(cpu.request(0xc0,0xa0),[]);
  assert.deepEqual(cpu.request(0xc0,0xc0),[1]);
  cpu.data[0x3f]&=~2;
  assert.deepEqual(cpu.request(0xc0,0xf0),[0]);
  // Erase/write/read the whole application reservation using real SPM code.
  cpu.rom.fill(0x55,0,cpu.boot);cpu.command(2);
  assert.ok(cpu.rom.slice(0,cpu.boot).every(value=>value===255));
  assert.equal(cpu.operations.length,cpu.boot/64);
  assert.deepEqual(cpu.operations.map(([,address])=>address),Array.from({length:cpu.boot/64},(_,i)=>cpu.boot-64-i*64));
  for(let page=0;page<cpu.boot;page+=64) {
    assert.deepEqual(cpu.request(0xc0,1,0,page,0),[]);
    for(let at=page;at<page+64;at+=4) {
      const bytes=Array.from({length:4},(_,i)=>((at+i)*17+31)&255);
      assert.deepEqual(cpu.request(0xc0,3,bytes[0]|bytes[1]<<8,bytes[2]|bytes[3]<<8,0),[]);
    }
    assert.equal(cpu.r[3],64);cpu.command(64);
  }
  assert.equal(cpu.rom[0]|cpu.rom[1]<<8,0xc000|((cpu.boot/2-1)&0xfff));
  for(let at=2;at<cpu.boot;at++)assert.equal(cpu.rom[at],(at*17+31)&255);
  for(let at=0;at<cpu.appBytes;at+=8) {
    const length=Math.min(8,cpu.appBytes-at);
    assert.deepEqual(cpu.request(0xc0,0xb0,at,0,length),Array.from(cpu.rom.slice(at,at+length)));
  }
  for(const [address,length,index] of [[cpu.appBytes,1,0],[cpu.appBytes-1,2,0],[65535,8,0],[0,0,0],[0,9,0],[0,8,1]]) {
    assert.deepEqual(cpu.request(0xc0,0xb0,address,index,length),[]);
  }
  const operationCount=cpu.operations.length;
  for(const pointer of [0,cpu.boot+2,65535]) {
    cpu.r[4]=pointer&255;cpu.r[5]=pointer>>8;cpu.command(64);
  }
  assert.equal(cpu.operations.length,operationCount,'Invalid page write was accepted');
  cpu.r[4]=4;cpu.r[5]=0;
  assert.deepEqual(cpu.request(0xc0,0xc0,0,0x55),[2]);
  assert.ok(cpu.eeprom.every(value=>value===255));
  cpu.command(2);
  assert.ok(cpu.rom.slice(0,cpu.boot).every(value=>value===255));
  assert.deepEqual(cpu.rom.slice(cpu.boot,cpu.boot+body.length),new Uint8Array(body));
  const cfg=meta.led,bit=1<<cfg.pin,ddr=cfg.ddr_io+32,port=cfg.port_io+32;
  // LED init/ticks isolate the configured bit. At application handover,
  // the existing DDRD cleanup releases both USB and any Port-D LED.
  for(const pattern of [0,255,0x55,0xaa]) {
    cpu.data[ddr]=pattern;cpu.data[port]=pattern;
    cpu.pc=meta.symbols.led_init/2;cpu.untilPC(meta.symbols.led_init_done);
    assert.equal(cpu.data[ddr],cfg.mode===0?pattern:cfg.mode===1?pattern|bit:pattern&~bit);
    assert.equal(cpu.data[port],cfg.mode===0?pattern:pattern&~bit);
    for(let tick=0;tick<256;tick++) {
      const beforeDDR=cpu.data[ddr],beforePORT=cpu.data[port];cpu.r[6]=tick;cpu.r[7]=0x55;
      cpu.pc=meta.symbols.led_tick/2;cpu.untilPC(meta.symbols.led_tick_done);
      const on=(tick&cfg.blink_mask)===0;
      assert.equal(cpu.data[ddr],cfg.mode===2?(on?beforeDDR|bit:beforeDDR&~bit):beforeDDR);
      assert.equal(cpu.data[port],cfg.mode===1?(on?beforePORT|bit:beforePORT&~bit):beforePORT);
      assert.equal(cpu.r[6],tick);assert.equal(cpu.r[7],0x55);
    }
    cpu.data[ddr]=pattern;cpu.data[port]=pattern;cpu.data[0x2a]=pattern;
    cpu.pc=meta.symbols.bootloader_start_application/2;cpu.untilPC(meta.symbols.app_jump);
    assert.equal(cpu.data[0x2a],0,'Application entered with DDRD outputs still active');
    assert.equal(cpu.data[ddr],cfg.ddr_io===0xa?0:cfg.mode===0?pattern:pattern&~bit);
    assert.equal(cpu.data[port],cfg.mode===1?pattern&~bit:pattern);
    assert.equal(cpu.data[0x68],0);assert.equal(cpu.data[0x6d],0);
  }
  console.log(`PASS: ${path.basename(path.dirname(file))}: 3072 standard-request comparisons, multi-packet descriptors/CRC, full Flash write/read/erase, all EEPROM bytes and memory guards`);
  console.log('PASS: stack/SRAM startup, final disconnect initialization, 1024 LED ticks, GPIO isolation and application handover');
}
