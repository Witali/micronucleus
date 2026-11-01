"""Prove the emitted loader disables its watchdog and never enables it again.

X/Y store bounds and legal RESET entry are checked by the existing context,
packet and startup models. Here Z writes are closed explicitly, including the
PHY's immutable context base; direct WDTCSR writes are rejected everywhere.
"""
from tests27.startup_init import check_startup
from tests27.waveform_model import dec


def instructions(artifact):
    """Walk real instruction boundaries, excluding the descriptor data block."""
    original = dec.START, dec.raw
    decoder = getattr(dec.decode, '__wrapped__', dec.decode)
    dec.START, dec.raw = artifact['boot'], artifact['body']
    try:
        entry = decoder(artifact['symbols']['bootloader_start'])
        assert entry.op == 'rjmp' and entry.target == artifact['symbols']['startup'], \
            'Boot entry must reach the checked RESET startup'
        pc = artifact['symbols']['USB_handler']
        end = artifact['boot'] + len(artifact['body'])
        result = []
        while pc < end:
            instruction = decoder(pc)
            assert not instruction.unknown, ('Unknown emitted instruction', hex(pc))
            result.append(instruction)
            pc += instruction.size
        assert pc == end
        return result
    finally:
        dec.START, dec.raw = original


def check_watchdog_lifetime(artifact):
    code, labels = instructions(artifact), artifact['symbols']
    assert [i.address for i in code if i.op == 'wdr'] == [labels['main']], \
        'Exactly the initial startup WDR must remain'
    assert not [i for i in code if i.op == 'sts' and i.words[1] == 0x60], \
        'No direct WDTCSR write is permitted'
    startup = [i for i in code if labels['main'] <= i.address < labels['bootloader_poll_begin']]
    assert [(i.op, i.operands) for i in startup if i.operands.split(',')[0] in ('r30', 'r31')] == [
        ('ldi', 'r30, 0x60'), ('mov', 'r31, r1')], 'Startup Z must remain the watchdog base'
    z_stores = lambda rows: [i for i in rows if i.op in ('st', 'std', 'xch')
                            and i.operands.startswith(('Z', '-Z'))]
    expected = [('std', 'Z+0, r24'), ('std', 'Z+0, r1'),
                ('std', 'Z+13, r24'), ('std', 'Z+8, r24')]
    assert [(i.op, i.operands) for i in z_stores(startup)] == expected, \
        'Startup Z stores must be exactly WDT disable and PCINT enables'
    allowed = {i.address for i in z_stores(startup)}
    phy = [i for i in code if labels['USB_handler'] <= i.address < labels['flash_buffer_append_word']]
    # Z is copied from the proven context base at entry and never modified.
    writes_z = [i for i in phy if i.operands.split(',')[0] in ('r30', 'r31')
                and i.op not in ('cp', 'cpc', 'cpi', 'sbrc', 'sbrs', 'bst')]
    assert [(i.address, i.op, i.operands) for i in writes_z] == [
        (labels['USB_handler'], 'movw', 'r30, r28')]
    assert not any('Z+' in i.operands and i.op not in ('std', 'ldd') or '-Z' in i.operands for i in phy), \
        'PHY must not increment/decrement its context Z pointer'
    for instruction in z_stores(phy):
        assert instruction.op == 'std'
        offset = int(instruction.operands.split(',')[0][2:])
        assert 0 <= offset < 44
        allowed.add(instruction.address)
    assert {i.address for i in z_stores(code)} == allowed, \
        'Unexpected non-context indirect Z store could reach WDTCSR'
    # Execute the startup words to prove the initial WDR, reset-cause ordering,
    # exact 0x18/0 timed pair, base=0x60, and disable before the 301 ms delay.
    check_startup(artifact)
    print('PASS', artifact['mode'], 'watchdog lifetime: one startup WDR, timed disable, closed direct/Z stores')
