// Execute the real updater opcodes using MicroMusic's CPU, with a local
// ATtiny88 Flash shim. MicroMusic itself is imported read-only and unchanged.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const music = process.env.MICROMUSIC_ROOT || 'C:/Work/MicroMusic';
const {AVRCore} = await import(pathToFileURL(path.join(music, 'web-player/lib/avr-reference.js')).href);
const build=path.resolve(process.argv[2]||path.join(root,'build'));
const metadata = JSON.parse(fs.readFileSync(path.join(build, 'manifest.json')));
const original = new Uint8Array(fs.readFileSync(path.join(build, 'updater.flash.bin')));
const expected = new Uint8Array(fs.readFileSync(path.join(build, metadata.image_file)));
const boot=metadata.image_address,postscript=boot-64;
const entry = metadata.symbols;

class UpdaterCPU extends AVRCore {
  constructor(image, options={}) {
    super(image, null, {target:'attiny88', cpuHz:16000000, fastIdle:false, fastBlocks:false});
    this.pc=0x80/2; this.command=0; this.until=0;
    this.buffer=new Uint8Array(64).fill(255); this.loaded=new Set();
    this.operations=[]; this.extended=options.disabled?255:254;
    this.corruptReadback=!!options.corruptReadback;
  }
  writeIO(address,value) {
    if (address===0x37) {
      assert.ok([1,3,5,9,17].includes(value));
      this.command=value; this.until=this.cyc+4;
      this.data[0x57]=value; return 0;
    }
    return super.writeIO(address,value);
  }
  step() {
    const at=this.pc*2, w=this.rom[at]|this.rom[at+1]<<8;
    if (w===0x95e8) {
      assert.ok(this.until>this.cyc,'SPM command expired');
      assert.equal(this.i,0,'Interrupts enabled during SPM');
      const z=this.r[30]|this.r[31]<<8, base=z&~63, cmd=this.command;
      if (cmd===17) {this.buffer.fill(255);this.loaded.clear();}
      else if (cmd===1) {
        const offset=z&63;
        assert.equal(offset&1,0); assert.ok(!this.loaded.has(offset));
        this.loaded.add(offset);this.buffer[offset]=this.r[0];this.buffer[offset+1]=this.r[1];
      } else {
        assert.ok(base===0 || base===postscript || (base>=boot&&base<8192));
        assert.ok(at<base || at>=base+64,'Updater erases executing code');
        if(cmd===3)this.rom.fill(255,base,base+64);
        else {
          assert.equal(cmd,5);assert.equal(z,base,'PGWRT is not page-aligned');
          assert.equal(this.loaded.size,32);assert.ok(this.rom.slice(base,base+64).every(x=>x===255));
          this.rom.set(this.buffer,base);this.buffer.fill(255);this.loaded.clear();
          if(this.corruptReadback&&base===boot){this.rom[base]^=1;this.corruptReadback=false;}
        }
        this.operations.push({command:cmd,address:base});
        // Flash erase/write halts this MCU. Only functional order is asserted;
        // the 4.5 ms bound is an explicit test parameter, not an analog model.
        this.clock(72000);
        for(let p=base/2;p<(base+64)/2;p++)this.decode(p);
      }
      this.command=0;this.data[0x57]=0;this.pc++;this.clock(4);return;
    }
    if(this.command===9&&(w&0xfe0f)===0x9004) {
      assert.ok(this.cyc<this.until-1,'Fuse LPM window expired');
      const z=this.r[30]|this.r[31]<<8;
      assert.equal(z,2);this.r[(w>>4)&31]=this.extended;
      this.command=0;this.data[0x57]=0;this.pc++;this.clock(3);return;
    }
    // MicroMusic does not implement CBI or SBIC/SBIS; supply those opcodes
    // explicitly here, retaining its CPU for arithmetic, control flow, LPM,
    // stack, SRAM and all other executed instructions.
    if((w&0xff00)===0x9800) {
      const io=(w>>3)&31;this.clock(2);this.writeIO(io,this.io[io]&~(1<<(w&7)));this.pc++;return;
    }
    if([0x9900,0x9b00].includes(w&0xff00)) {
      const bit=(this.io[(w>>3)&31]>>(w&7))&1;
      this.pc++;let cycles=1;
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

function run(image, options={}) {
  const cpu=new UpdaterCPU(image,options);
  let restarted=false;
  for(let i=0;i<2000000;i++) {
    if(cpu.pc*2===entry.updater_complete)return {cpu,result:'complete'};
    if(cpu.pc*2===entry.updater_abort)return {cpu,result:'abort',code:cpu.r[24]};
    cpu.step();
    if(options.restartAt && !restarted && cpu.operations.length===options.restartAt) {
      assert.equal(cpu.rom[0]|cpu.rom[1]<<8,0xc03f,'Temporary RESET is not installed');
      const next=new UpdaterCPU(cpu.rom,options);
      // Restart execution with persisted Flash and reset CPU/SRAM state.
      Object.assign(cpu,next);restarted=true;
    }
  }
  throw new Error('Updater did not finish');
}

function verifySuccess(test) {
  assert.equal(test.result,'complete');
  assert.deepEqual(test.cpu.rom.slice(boot),expected);
  assert.ok(test.cpu.rom.slice(postscript,boot).every(x=>x===255));
  assert.equal(test.cpu.rom[0]|test.cpu.rom[1]<<8,0xc000|((boot/2-1)&0xfff));
  assert.deepEqual(test.cpu.rom.slice(0x80,metadata.updater_end),original.slice(0x80,metadata.updater_end));
}
verifySuccess(run(original));
let test=run(original,{disabled:true});assert.equal(test.code,1);assert.equal(test.cpu.operations.length,0);
const damaged=original.slice();damaged[entry.bootloader_image+17]^=1;
test=run(damaged);assert.equal(test.code,2);assert.equal(test.cpu.operations.length,0);
test=run(original,{corruptReadback:true});assert.equal(test.code,4);
assert.equal(test.cpu.rom[0]|test.cpu.rom[1]<<8,0xc03f);
// Two operations install temporary RESET; each payload page adds erase/write.
// Restart after payload erases and the postscript erase, before the final
// RESET-page replacement. Derive positions from the selected image size.
const imagePages=expected.length/64;
const restartAfter=[3,9,2+2*Math.floor(imagePages/2)+1,2+2*(imagePages-1)+1,2+2*imagePages+1];
for(const at of restartAfter)verifySuccess(run(original,{restartAt:at}));
console.log('PASS: MicroMusic CPU + explicit ATtiny88 NVM shim: successful byte-exact update,');
console.log('      disabled SELFPRGEN, corrupt payload, failed page readback, and five interrupted-operation restarts.');
console.log('LIMIT: interrupted first-page erase/write can lose RESET; ISP may still be necessary.');
