// USB-only integration layer; all AVR opcodes execute in the shared MicroMusic CPU.
import {readFile} from 'node:fs/promises';
import {resolve, join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

export async function loadMicroMusic(root = process.env.MICROMUSIC_ROOT) {
    if (!root) throw new Error('Set MICROMUSIC_ROOT to the existing MicroMusic checkout.');
    root = resolve(root);
    const paths = ['web-player/lib/avr-reference.js', 'web-player/lib/avr-profiles.js',
        'web-player/lib/attiny88-registers.js'];
    const [reference, registers] = await Promise.all([
        import(pathToFileURL(join(root, paths[0])).href),
        import(pathToFileURL(join(root, paths[2])).href),
    ]);
    const hashes = {};
    for (const name of paths) hashes[name] = createHash('sha256').update(await readFile(join(root, name))).digest('hex');
    return {root, ReferenceCore: reference.AVRCore, ...registers, hashes};
}

export class USBWire {
    constructor(value = {}) {
        this.boundaries = value.boundaries ?? [];
        this.levels = value.levels ?? [];
        this.labels = value.labels ?? this.levels.map((_, index) => index);
        this.start = value.start ?? this.boundaries[0] ?? 0;
        this.end = value.end ?? this.boundaries.at(-1) ?? 0;
        if (this.boundaries.length !== this.levels.length) throw new Error('Wire arrays differ in length.');
        if (this.boundaries.some((n, i, a) => !Number.isFinite(n) || (i && n <= a[i-1])))
            throw new Error('Wire times must be finite and strictly increasing.');
        if (this.levels.some(n => ![0, 2, 4, 6].includes(n))) throw new Error('Invalid USB line value.');
    }
    index(time) {
        let left = 0, right = this.boundaries.length;
        while (left < right) {
            const mid = (left + right) >>> 1;
            if (this.boundaries[mid] <= time) left = mid + 1; else right = mid;
        }
        return left - 1;
    }
    level(time) { const n = this.index(time); return n < 0 ? 2 : this.levels[n]; }
    cell(time) { const n = this.index(time); return n < 0 ? 'pre' : this.labels[n]; }
}

export function usbCoreClass(library) {
    const {ReferenceCore, AT88_DATA: REG, AT88_MEMORY: MEMORY} = library;
    return class USBAVRCore extends ReferenceCore {
        constructor(binary, {wave, entry = 8, flagPriority = 'clear', aperture = -1e-7, flagDriver = 'external'} = {}) {
            super(binary, null, {target: 'attiny88', cpuHz: 16_000_000, fastIdle: false, fastBlocks: false});
            if (this.profile.flashBytes !== MEMORY.flashBytes || this.profile.sramStart !== MEMORY.ramStart ||
                this.profile.ramEnd !== MEMORY.ramEnd) throw new Error('ATtiny88 register/profile geometry mismatch.');
            if (!['clear', 'set'].includes(flagPriority)) throw new Error('Unknown simultaneous PCIF priority.');
            this.wire = wave instanceof USBWire ? wave : new USBWire(wave);
            this.cyc = entry; this.phase = entry - Math.floor(entry);
            if (!['external', 'combined'].includes(flagDriver)) throw new Error('Unknown PCINT input source.');
            this.flagPriority = flagPriority; this.aperture = aperture; this.flagDriver = flagDriver;
            this.events = []; this.gpioWrites = []; this.pinReads = []; this.flagWrites = []; this.outputHistory = [];
            this.clearAt = -Infinity; this.flagEvents = [];
            this.flagBegin = Math.floor((Math.min(this.wire.start, entry) - this.phase)) - 4;
            this.lastFlagClock = this.flagBegin;
            // A direct USB_handler probe assumes its caller initialized PD2 PCINT.
            // All register addresses come from MicroMusic's generated DFP map.
            this.data[REG.PCMSK2] = 4; this.data[REG.PCICR] = 4;
            this.instructionStart = entry; this.instructionPC = 0;
        }
        outputsAt(time) {
            let ddr = 0, port = 0;
            for (const event of this.outputHistory) {
                if (event.time > time) break;
                ddr = event.ddr; port = event.port;
            }
            return {ddr, port};
        }
        busLevel(time) {
            const {ddr, port} = this.outputsAt(time);
            return ((this.wire.level(time) & ~ddr) | (port & ddr)) & 6;
        }
        advanceFlags(to) {
            if (!(this.data[REG.PCMSK2] & 4)) return;
            const stop = Math.floor(to - this.phase + 1e-10);
            for (let n = this.lastFlagClock + 1; n <= stop; n++) {
                const time = this.phase + n;
                // Explicit three-stage digital PCINT model. This is not an
                // independent analog/metastability or same-edge-priority proof.
                const level = t => this.flagDriver === 'combined' ? this.busLevel(t) : this.wire.level(t);
                if ((level(time + this.aperture) ^ level(time - 1.5 + this.aperture)) & 4)
                    this.flagEvents.push(time + 2);
            }
            this.lastFlagClock = Math.max(this.lastFlagClock, stop);
        }
        pendingPCIF(time) {
            this.advanceFlags(time);
            return this.flagEvents.some(n => n <= time &&
                (this.flagPriority === 'set' ? n >= this.clearAt : n > this.clearAt));
        }
        readData(address) {
            if (address === REG.PIND) {
                // Microchip doc8008H Figure 10-4: the IN begins on the PIN
                // update edge. Retain the preceding falling-edge sample even
                // though MicroMusic invokes this hook after clock(1).
                const time = this.instructionStart - 0.5 + this.aperture;
                const value = this.busLevel(time);
                this.pinReads.push([time, this.instructionPC, value, this.wire.cell(time)]);
                return value;
            }
            if (address === REG.PCIFR)
                return (this.data[address] & ~4) | (this.pendingPCIF(this.instructionStart) ? 4 : 0);
            return super.readData(address);
        }
        writeIO(io, value, mask = 255) {
            const address = io + 32;
            value &= 255; mask &= 255;
            if (address === REG.PCIFR) {
                if (value & mask & 4) {
                    // Actual write bus cycle: OUT=one clock, SBI=two clocks.
                    this.advanceFlags(this.cyc);
                    this.clearAt = this.cyc;
                    this.flagWrites.push([this.cyc, value & 255]);
                }
                this.data[address] &= ~(value & mask & ~4);
                return 0;
            }
            if (address === REG.PCICR || address === REG.PCMSK2) {
                value = (this.data[address] & ~mask) | (value & mask);
                if (value & ~4) throw new Error('Only the USB PD2/PCINT18 group is modeled.');
                this.data[address] = value; return 0;
            }
            const old = this.data[address];
            const result = super.writeIO(io, value, mask);
            if (this.events && (address === REG.PORTD || address === REG.DDRD)) {
                this.gpioWrites.push([this.cyc, io, this.data[address]]);
                if (old !== this.data[address]) this.events.push([this.cyc, io, this.data[address]]);
                this.outputHistory.push({time: this.cyc, ddr: this.data[REG.DDRD], port: this.data[REG.PORTD]});
            }
            return result;
        }
        step() {
            this.instructionStart = this.cyc; this.instructionPC = this.pc*2;
            return super.step();
        }
        interrupt() {
            if (this.wire && this.i && (this.data[REG.PCICR] & 4) && this.pendingPCIF(this.cyc))
                throw new Error('PCINT ISR entry is unsupported; this adapter targets polled USB with I=0.');
            return super.interrupt();
        }
    };
}

export function localPath(value) {
    return process.platform === 'win32' && /^\/mnt\/[a-z]\//.test(value)
        ? value[5].toUpperCase() + ':/' + value.slice(7) : value;
}

export async function runRequest(request, library) {
    const artifact = request.artifact;
    const body = await readFile(localPath(artifact.bin));
    const sha256 = createHash('sha256').update(body).digest('hex');
    if (sha256 !== artifact.sha256) throw new Error('Firmware body hash mismatch.');
    const image = new Uint8Array(library.AT88_MEMORY.flashBytes).fill(255);
    if (artifact.boot + body.length > image.length) throw new Error('Firmware body exceeds ATtiny88 Flash.');
    image.set(body, artifact.boot);
    const Core = usbCoreClass(library), cpu = new Core(image, request);
    cpu.r.set([0,1,0,1],28); cpu.r[21] = 0xa0; cpu.r[8] = cpu.r[10] = 0x10;
    cpu.data[0x10f] = 0x5a;
    for (const [key, value] of Object.entries(request.memory ?? {})) cpu.data[Number(key)] = value;
    for (const [key, value] of Object.entries(request.registers ?? {})) cpu.r[Number(key)] = value;
    cpu.sreg = request.sreg ?? 0;
    cpu.pushPC(0); cpu.pc = artifact.symbols[request.entryLabel ?? 'USB_handler']/2;
    const labels = new Map((request.checkpoints ?? []).map(name => [artifact.symbols[name], name]));
    const checkpoints = [];
    let instructions = 0;
    while (cpu.pc !== 0) {
        if (++instructions > (request.limit ?? 30000)) throw new Error('USB instruction limit exceeded.');
        if (labels.has(cpu.pc*2)) checkpoints.push({label: labels.get(cpu.pc*2), time: cpu.cyc,
            count: cpu.r[23], Y: cpu.r[28] | (cpu.r[29]<<8)});
        cpu.step();
    }
    if (cpu.sp !== cpu.profile.ramEnd) throw new Error('Unbalanced AVR stack after handler return.');
    return {sha256, engine: 'MicroMusic AVR reference + USB adapter', cpuHz: cpu.cpuHz,
        flagPriority: cpu.flagPriority, flagDriver: cpu.flagDriver, cycles: cpu.cyc, instructions,
        registers: Array.from(cpu.r), sreg: cpu.sreg, memory: Array.from(cpu.data.slice(0x100,0x12c)),
        checkpoints, events: cpu.events, gpioWrites: cpu.gpioWrites,
        pinReads: cpu.pinReads, flagWrites: cpu.flagWrites,
        sourceHashes: library.hashes};
}
