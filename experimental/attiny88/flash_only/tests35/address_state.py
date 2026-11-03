"""Pending-address ABI adapter for current and frozen historical AVR images.

The zero-byte symbol describes storage only; observable address/token CRC
expectations remain independent of this helper and of the image hash.
"""


def register_pending(cpu):
    if isinstance(cpu, dict):
        symbols = cpu['symbols']
    elif hasattr(cpu, 'labels'):
        symbols = cpu.labels
    elif hasattr(cpu, 'sym'):
        symbols = cpu.sym
    else:
        symbols = cpu.a['symbols']
    return 'usb_pending_address_r12' in symbols


def memory(cpu):
    return cpu.m if hasattr(cpu, 'm') else cpu.mem


def seed_pending(cpu, address):
    """Seed a synthetic eligible SET_ADDRESS, not an ordinary read/write."""
    if register_pending(cpu):
        cpu.r[11], cpu.r[12] = 0x75, address
    else:
        memory(cpu)[0x113] = address
    value = address
    crc = 31
    for _ in range(11):
        crc = (crc >> 1) ^ (20 if (crc ^ value) & 1 else 0)
        value >>= 1
    cpu.r[10] = (crc ^ 31) << 3


def pending(cpu):
    """Return logical pending address, or active address for ordinary replies."""
    ram = memory(cpu)
    if not register_pending(cpu):
        return ram[0x113]
    if cpu.r[11] & 0x20 and ram[0x10f] != 0x1e:
        return cpu.r[12]
    return ram[0x10c]


def reset_offsets(cpu):
    # SRAM19 was pending-address storage in historical images, now dead.
    return (12, 20, 21) if register_pending(cpu) else (12, 19, 20, 21)
