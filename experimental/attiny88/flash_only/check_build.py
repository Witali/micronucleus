from build import build as b

def build(source=None, mode='NONE', boot=0x1c00):
    import re
    from pathlib import Path
    variant=(str(Path(source).parent) if source is not None else 'source')
    x=b(where=variant,led=mode,boot=boot)
    symbols={}
    for line in x['symbols'].splitlines():
        fields=line.split()
        if len(fields)>=5 and fields[2]=='.text':
            symbols[fields[-1]]=int(fields[0],16)
    return {'body':Path(x['bin']).read_bytes()[boot:], 'boot':boot,'obj':Path(x['obj']), 'symbols':symbols}
