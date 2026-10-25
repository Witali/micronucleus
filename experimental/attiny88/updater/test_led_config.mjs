// Execute the emitted LED instructions; the sibling CPU is imported read-only.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const music=process.env.MICROMUSIC_ROOT||'C:/Work/MicroMusic';
const {AVRCore}=await import(pathToFileURL(path.join(music,'web-player/lib/avr-reference.js')).href);

class LEDCPU extends AVRCore {
  // MicroMusic lacks CBI. Keep its CPU for every other instruction.
  step() {
    const at=this.pc*2,w=this.rom[at]|this.rom[at+1]<<8;
    if((w&0xff00)===0x9800) {
      const io=(w>>3)&31;
      this.writeIO(io,this.io[io]&~(1<<(w&7)));this.pc++;this.clock(2);return;
    }
    super.step();
  }
}

const profiles=process.argv.slice(2);
if(!profiles.length)profiles.push(...['verified','led-on','led-active-low','led-custom-high','led-custom-low']
  .map(name=>path.join(root,'build',name,'firmware.json')));
for(const file of profiles) {
  const meta=JSON.parse(fs.readFileSync(file)),s=meta.symbols,cfg=meta.led,bit=1<<cfg.pin;
  const flash=new Uint8Array(8192).fill(255);
  flash.set(fs.readFileSync(path.join(path.dirname(file),meta.body_file)),meta.image_address);
  const cpu=new LEDCPU(flash,null,{target:'attiny88',cpuHz:16000000,fastIdle:false,fastBlocks:false});
  function execute(hook) {
    cpu.pc=s[hook]/2;
    for(let i=0;cpu.pc*2!==s[hook+'_done'];i++) {
      assert.ok(i<10,`${hook} did not finish`);cpu.step();
    }
  }
  function check(hook,on,ddrBefore,portBefore) {
    cpu.io[cfg.ddr_io]=ddrBefore;cpu.io[cfg.port_io]=portBefore;
    const before=cpu.io.slice();execute(hook);
    let ddr=ddrBefore,port=portBefore;
    if(cfg.mode!==0) {
      if(hook==='led_init') {port&=~bit;ddr=cfg.mode===1?ddr|bit:ddr&~bit;}
      if(hook==='led_tick') {
        if(cfg.mode===1)port=on?port|bit:port&~bit;
        else ddr=on?ddr|bit:ddr&~bit;
      }
      if(hook==='led_exit') {ddr&=~bit;if(cfg.mode===1)port&=~bit;}
    }
    const expected=before.slice();expected[cfg.ddr_io]=ddr;expected[cfg.port_io]=port;
    // Arithmetic flags are intentionally disposable in the main loop.
    expected[0x3f]=cpu.io[0x3f];
    assert.deepEqual(cpu.io,expected,`${hook}: unrelated GPIO/register changed`);
    assert.equal(cpu.r[1],0,'Zero register changed');
  }
  for(const pattern of [0,0xff,0x55,0xaa]) {
    check('led_init',false,pattern,pattern);
    for(let tick=0;tick<256;tick++) {
      cpu.r[6]=tick;cpu.r[7]=0x55;
      check('led_tick',(tick&cfg.blink_mask)===0,pattern,pattern);
      assert.equal(cpu.r[6],tick);assert.equal(cpu.r[7],0x55);
    }
    check('led_exit',false,pattern,pattern);
  }
  if(cfg.mode===0)for(const hook of ['led_init','led_tick','led_exit'])assert.equal(s[hook],s[hook+'_done']);
  console.log(`PASS: LED mode ${cfg.mode}, DDR 0x${cfg.ddr_io.toString(16)}, bit ${cfg.pin}, mask 0x${cfg.blink_mask.toString(16)}: init, 1024 ticks, exit and GPIO isolation`);
}
