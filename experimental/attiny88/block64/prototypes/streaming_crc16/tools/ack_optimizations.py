"""Opt-in ACK-path experiments; keep the validated V2 source unchanged."""
MODES = ('immediate', 'context', 'deferred', 'eop')
FROZEN_V2 = 'fcc0ad6f463dd0e133808065e8db3d1aa2e4a1762158666dadfc2231205dbd2c'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('ACK experiment source anchor changed: '+old.splitlines()[0])
    return text.replace(old, new)


def transform(sampler, phy, empty, mode):
    if mode not in MODES:
        raise ValueError('Unknown ACK experiment')
    if mode == 'immediate':
        return sampler, phy, empty
    # RX starts at 0116 and contains <=11 bytes; YH remains one.
    old = '    sub     r28, r19\n'
    if sampler.count(old) != 4:
        raise ValueError('Expected four completed-EOP context prefixes')
    sampler = sampler.replace(old, '    ldi     r28, 0\n')
    for target, label in (('L1bf6', 'data'), ('stream_nondata_dispatch', 'token')):
        sampler = once(sampler,
            '    ldi     r30, 0\n    ldi     r31, 1\n    rjmp    '+target,
            'stream_restore_'+label+'_context:\n    movw    r30, r28\n    rjmp    '+target)
    # Early drops still use explicit Z=0100: Y can be an unfinished cursor.
    for register, offset in (('r16', 0), ('r17', 1), ('r17', 2)):
        phy = once(phy, f'    ldd     {register}, Y+{offset}\n',
                        f'    ldd     {register}, Y+{22+offset}\n')
    if mode == 'context':
        return sampler, phy, empty
    # Replace an inert PID-init padding clock, without moving any IN sample.
    sampler = once(sampler,
        '    clr     r21\n    nop\n    ldi     r30, 0x54',
        '    clr     r21\n    ldi     r27, 0\n    ldi     r30, 0x54')
    publication = '    std     Z+18, r19\n    std     Z+13, r18\n'
    stage = '    movw    r24, r18\n    ldi     r27, 1\n'
    phy = once(phy, publication, 'stream_publication_reserve_data:\n'+stage)
    # Empty DATA keeps its DATA1/OUT gates, and stages only validated bytes.
    empty_publication = ('    std     Z+18, r19            /* Publish three decoded bytes, no payload. */\n'
                         '    std     Z+13, r18            /* Foreground sees a valid status OUT. */\n')
    empty = once(empty, empty_publication, 'stream_publication_reserve_empty:\n'+stage)
    if mode == 'deferred':
        phy = once(phy, 'L1be8:\n', 'L1be8:\n#include "streaming_ack_publish.inc"\n')
    else:
        old_delay = '''    ldi     r21, 0x04

L1cc2:
    dec     r21
    brbc    1, L1cc2
'''
        phy = once(phy, old_delay, '#include "streaming_ack_eop.inc"\n')
    return sampler, phy, empty
