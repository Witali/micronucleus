// Regression check from a complete received SETUP packet through TX payload
// copying. Unlike the historical unit tests, do not start at the extension.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const music=process.env.MICROMUSIC_ROOT||'C:/Work/MicroMusic';
const {AVRCore}=await import(pathToFileURL(path.join(music,'web-player/lib/avr-reference.js')).href);
const manifestPath=path.resolve(process.argv[2]||path.join(root,'build/verified/firmware.json'));
const manifest=JSON.parse(fs.readFileSync(manifestPath));
const symbols=manifest.symbols,boot=manifest.image_address,appBytes=manifest.application_bytes;
const body=fs.readFileSync(path.join(path.dirname(manifestPath),manifest.body_file));
class PacketCPU extends AVRCore {
  constructor(type,request,address,length,index=0) {
    const flash=Uint8Array.from({length:8192},(_,i)=>(i*17+31)&255);flash.set(body,boot);
    super(flash,null,{target:'attiny88',cpuHz:16000000,fastIdle:false,fastBlocks:false});
    this.eeprom=Uint8Array.from({length:64},(_,i)=>0x80+i);
    this.pc=symbols.L1d9c/2;this.data[0x112]=11;this.data[0x10d]=0x2d;
    this.data.set([type,request,address&255,address>>8,index&255,index>>8,length&255,length>>8],0x117);
  }
  writeIO(io,value) {
    if(io===0x1f) {
      if(value&1)this.data[0x40]=this.eeprom[this.data[0x41]];
      if((value&6)===6)this.eeprom[this.data[0x41]]=this.data[0x40];
      this.data[0x3f]=value&~3;return 0;
    }
    return super.writeIO(io,value);
  }
  packet() {
    for(let i=0;i<1000;i++) {
      if(this.pc*2===symbols.L1e4c)return Array.from(this.data.slice(0x102,0x102+this.r[23]));
      this.step();
    }
    throw new Error('No TX payload prepared');
  }
  step() {
    const at=this.pc*2,w=this.rom[at]|this.rom[at+1]<<8;
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
}
for(const address of [0,8,255,256,appBytes-44,appBytes-8]) {
  const cpu=new PacketCPU(0xc0,0xb0,address,8);
  assert.deepEqual(cpu.packet(),Array.from(cpu.rom.slice(address,address+8)));
}
let cpu=new PacketCPU(0xc0,0,0,8);assert.deepEqual(cpu.packet(),Array.from(body.slice(2,10)));
cpu=new PacketCPU(0x80,0,0,2);assert.deepEqual(cpu.packet(),[0,0]);
cpu=new PacketCPU(0x80,8,0,1);cpu.data[0x115]=1;assert.deepEqual(cpu.packet(),[1]);
cpu=new PacketCPU(0xc0,0xa0,17,1);assert.deepEqual(cpu.packet(),[0x91]);
cpu=new PacketCPU(0xc0,0xf0,0,1);assert.deepEqual(cpu.packet(),[0]);
cpu=new PacketCPU(0xc0,0xc0,17,1,0x55);assert.deepEqual(cpu.packet(),[0]);assert.equal(cpu.eeprom[17],0x55);
cpu=new PacketCPU(0xc0,0xc0,64,1,0x55);assert.deepEqual(cpu.packet(),[2]);
for(const [address,length,index] of [[appBytes,1,0],[appBytes-1,2,0],[65535,8,0],[0,9,0],[0,8,1]]) {
  cpu=new PacketCPU(0xc0,0xb0,address,length,index);assert.deepEqual(cpu.packet(),[]);
}
console.log('PASS: 18 complete SETUP-to-TX cases: vendor routing, Flash/SRAM data, EEPROM status, standard requests and bounds');
for(const flags of [1,2,4,8,15]) {
  const flash=new Uint8Array(8192).fill(255);flash.set(body,boot);
  const cpu=new AVRCore(flash,null,{target:'attiny88',cpuHz:16000000,fastIdle:false,fastBlocks:false});
  cpu.pc=symbols.main/2;cpu.data[0x54]=flags;cpu.data[0x60]=(flags&8)?8:0;
  let finished=false;
  for(let step=0;step<12;step++) {
    cpu.step();
    if(cpu.data[0x54]===0&&cpu.data[0x1e+32]===flags&&cpu.data[0x60]===0) {
      finished=true;break;
    }
  }
  assert.ok(finished,'Reset flags/watchdog were not cleared in the required order');
}
console.log('PASS: POR/EXTR/BOR/WDR/mixed reset flags preserved and cleared before watchdog disable');
