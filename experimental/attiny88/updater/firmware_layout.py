"""Expected ATtiny88 layout for opt-in physical verification tools."""
import json
from pathlib import Path


def firmware_layout(manifest=None):
    boot=0x1ac0
    if manifest is not None:
        data=json.loads(Path(manifest).read_text())
        assert data['target']=='attiny88','Wrong firmware target'
        boot=data['image_address']
        assert data['application_bytes']==boot-4,'Invalid application capacity'
    assert 0x1800<=boot<=0x1b00 and boot%64==0,'Invalid boot boundary'
    reset=0xc000|((boot//2-1)&0xfff)
    return boot,boot-4,reset
