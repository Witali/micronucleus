"""Pending-address ABI adapter for current and frozen historical AVR images.

The zero-byte symbol describes storage only; observable address/token CRC
expectations remain independent of this helper and of the image hash.
"""


def symbols(cpu):
    if isinstance(cpu, dict):
        symbols = cpu['symbols']
    elif hasattr(cpu, 'labels'):
        symbols = cpu.labels
    elif hasattr(cpu, 'sym'):
        symbols = cpu.sym
    else:
        symbols = cpu.a['symbols']
    return symbols


def register_pending(cpu):
    return 'usb_pending_address_r12' in symbols(cpu)


def paired(cpu):
    return 'usb_active_address_r8r9' in symbols(cpu)


def initialize_registers(artifact, registers):
    """Explicit cold address-zero fixture state; no AVR execution is changed."""
    if paired(artifact):
        registers[8:11] = [0, 0x10, 0]
    else:
        registers[8] = registers[10] = 0x10


def crc5_byte(address):
    value = address
    crc = 31
    for _ in range(11):
        crc = (crc >> 1) ^ (20 if (crc ^ value) & 1 else 0)
        value >>= 1
    return (crc ^ 31) << 3


def active(cpu):
    return cpu.r[8] if paired(cpu) else memory(cpu)[0x10c]


def active_crc(cpu):
    return cpu.r[9 if paired(cpu) else 8]


def seed_active(cpu, address, cache=None):
    """Seed logical address/cache, including intentionally malformed cache cases."""
    if paired(cpu):
        cpu.r[8] = address
    else:
        memory(cpu)[0x10c] = address
    cpu.r[9 if paired(cpu) else 8] = crc5_byte(address) if cache is None else cache


def pending_crc(cpu):
    return cpu.r[13 if paired(cpu) else 10]


def seed_tx_pid(cpu, value):
    cpu.r[10 if paired(cpu) else 9] = value


def seed_ordinary(cpu, address):
    """An ordinary reply owns no address change, including in older layouts."""
    seed_active(cpu,address)
    if register_pending(cpu):
        cpu.r[11] &= ~0x20
    else:
        memory(cpu)[0x113] = address
        cpu.r[10] = crc5_byte(address)


def memory(cpu):
    return cpu.m if hasattr(cpu, 'm') else cpu.mem


def seed_pending(cpu, address):
    """Seed a synthetic eligible SET_ADDRESS, not an ordinary read/write."""
    if register_pending(cpu):
        cpu.r[11], cpu.r[12] = 0x75, address
    else:
        memory(cpu)[0x113] = address
    cpu.r[13 if paired(cpu) else 10] = crc5_byte(address)


def pending(cpu):
    """Return logical pending address, or active address for ordinary replies."""
    ram = memory(cpu)
    if not register_pending(cpu):
        return ram[0x113]
    if cpu.r[11] & 0x20 and ram[0x10f] != 0x1e:
        return cpu.r[12]
    return active(cpu)


def reset_offsets(cpu):
    # SRAM19 was pending-address storage in historical images, now dead.
    if paired(cpu):
        return (20, 21)
    return (12, 20, 21) if register_pending(cpu) else (12, 19, 20, 21)
