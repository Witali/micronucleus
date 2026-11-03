"""Generate the F0 byte-publication scheduling fixture; no USB device code."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'build/raw_publication_probe'


def generate():
    """Retire two history tests after F0 admission and keep every capture clock."""
    order = (0, 2, 1)
    cells = []
    for byte in order:
        for bit in range(8):
            phase = (byte + bit) % 3
            name = f'byte{byte}_bit{bit}'
            cells.append(dict(byte=byte, bit=bit, phase=phase, name=name))
    for index, cell in enumerate(cells):
        cell['next'] = cells[(index + 1) % len(cells)]['name']
        cell['falls'] = cell['bit'] == 0 or (cell['bit'] == 1 and cell['phase'] == 0) or cell['phase'] == 0

    # Collapse forced fallthrough edges. Every group then ends in a short branch.
    groups = []
    group = []
    for cell in cells:
        group.append(cell)
        if not cell['falls']:
            groups.append(group)
            group = []
    assert not group and groups[0][0]['name'] == 'byte0_bit0'
    assert all(len(g) <= 3 for g in groups)

    blocks = {}
    for gi in range(len(groups)):
        lines = []
        cold = f'cold_group{gi}'
        for cell in groups[gi]:
            phase, bit = cell['phase'], cell['bit']
            previous, first, second = ((16, 17, 19), (19, 16, 17), (17, 19, 16))[phase]
            if cell['name'] == 'byte0_bit0':
                lines += ['bootloader_start:', 'USB_handler:']
            lines += [cell['name'] + ':', f'    in r{first}, 9', f'    andi r{first}, 6',
                      f'    in r{second}, 9', f'    breq {cold}']
            if bit == 0:
                lines += ['    st Y+, r18']
                if phase == 1:
                    lines += ['    nop']
                elif phase == 2:
                    lines += ['    dec r23']
            lines += [f'    eor r{previous}, r{first}', f'    andi r{previous}, 6',
                      f'    subi r{previous}, 1', '    ror r18']
            if bit == 0:
                continue
            if bit == 1:
                if phase == 0:
                    lines += ['    sbrs r23, 7', '    rjmp full_validate']
                else:
                    lines += ['    dec r23', f'    brmi {cell["next"]}', '    rjmp full_validate']
                continue
            threshold = '0xf0' if bit == 7 else '0xfc'
            lines += [f'    cpi r18, {threshold}']
            if phase == 0:
                lines += [f'    brcc {cold}']
            else:
                lines += [f'    brcs {cell["next"]}']
        lines += [cold + ':', '    ret']
        blocks[gi] = lines

    footer = ['full_validate:', '    cpi r18, 0xc0', '    brlo full_tail_invalid',
              'full_tail_ones:', '    ret', 'full_tail_invalid:', '    ret',
              'usb_control_process_received_packet:', 'bootloader_poll_begin:',
              'bootloader_start_application:', '    ret']

    labels = {}
    branches = []
    sizes = {}
    for gi, block in blocks.items():
        pc = 0
        for line in block:
            if line.endswith(':'):
                labels[line[:-1]] = (gi, pc)
            elif line.startswith('    '):
                operation, *operands = line.strip().split()
                if operation.startswith('br'):
                    branches.append((gi, pc, operands[-1]))
                pc += 1
        sizes[gi] = pc


    def spans(layout):
        starts = {}
        pc = 0
        for gi in layout:
            starts[gi] = pc
            pc += sizes[gi]
        result = []
        for gi, offset, target in branches:
            tg, to = labels[target]
            result.append(starts[tg] + to - starts[gi] - offset - 1)
        return result


    # Retained fourteen-group fold: all emitted BRxx edges fit -64..63 words.
    layout = (0, 12, 13, 1, 11, 2, 3, 10, 9, 4, 8, 5, 7, 6)
    assert all(-64 <= offset <= 63 for offset in spans(layout))
    lines = ['/* Component only: no acquisition, cold stuffing or EOP qualifier. */',
             '    .text', '    .org BOOT_AT', '    .global bootloader_start']
    for gi in layout:
        lines += blocks[gi]
    lines += footer
    meta = dict(cells=cells, groups=[[c['name'] for c in g] for g in groups],
                layout=list(layout), normal_branch_word_spans=spans(layout))
    return '\n'.join(lines) + '\n', meta


def write_probe(directory=OUTPUT):
    """Keep generated assembly and layout metadata in ignored build output."""
    source, schedule = generate()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'publication_probe.S'
    path.write_text(source)
    (directory / 'schedule.json').write_text(json.dumps(schedule, indent=2) + '\n')
    return path


if __name__ == '__main__':
    print(write_probe())
